"""Lectura de una zona de alerta desde un archivo OpenAir.

Referencia: Extended OpenAir file format specification v2.1.2 (Naviter),
https://github.com/naviter/seeyou_file_formats/blob/main/OpenAir_File_Format_Support.md

Solo se admite UNA zona circular por archivo (el sistema tiene una sola zona):
    AC  clase (se acepta cualquier valor; inicia la definición)
    AY  tipo (opcional)
    AN  nombre
    AL  altura inferior: GND / SFC / PISO, o altura AMSL / FL
    AH  altura superior: altura AMSL / FL
    V X=  centro, en DMS (35:06:43 S) o DDM (35:06.716 S)
    DC  radio en NM, sin unidad

Las alturas sin unidad se toman en pies (convención OpenAir) y las que
tienen ``m`` en metros. AGL y UNL no se pueden representar con la altitud
barométrica que informan las aeronaves, así que se rechazan con un mensaje.
Los comentarios empiezan con ``*`` y llegan hasta el fin de la línea.
"""

import re
from dataclasses import dataclass

from .zone import feet_to_meters

GROUND_WORDS = {"GND", "SFC", "PISO", "SUELO", "SUPERFICIE"}
IGNORED_COMMANDS = {"AF", "AG", "AA", "AX", "AT", "SP", "SB"}
SHAPE_COMMANDS = {"DP", "DA", "DB", "DY"}
MAX_NAME_LENGTH = 100

_NUMBER = r"\d+(?:[.,]\d+)?"
_ALTITUDE_RE = re.compile(
    rf"^(?P<value>-?{_NUMBER})\s*(?P<unit>FT|F|M)?\s*(?P<ref>AMSL|MSL|ALT|STD|AGL|AAL|SFC|GND)?$"
)
_FLIGHT_LEVEL_RE = re.compile(rf"^FL\s*(?P<value>{_NUMBER})$")
_POINT_RE = re.compile(
    r"^(?P<lat>[\d:.,]+)\s*(?P<ns>[NS])\s*,?\s*(?P<lon>[\d:.,]+)\s*(?P<ew>[EW])$"
)


class OpenAirError(ValueError):
    """Archivo OpenAir no válido o no soportado. El mensaje es para el usuario."""


@dataclass(frozen=True)
class OpenAirZone:
    name: str
    lat: float
    lon: float
    radius_nm: float
    floor_m: float
    ceiling_m: float
    airspace_class: str | None = None
    airspace_type: str | None = None

    def as_config_fields(self):
        """Campos de ``configuration.SystemConfig`` que define el archivo.

        Las coordenadas se redondean a 6 decimales (~0,1 m), más que la
        precisión de un segundo de arco (~30 m) con que vienen en el archivo.
        """
        return {
            "zone_name": self.name,
            "zone_lat": round(self.lat, 6),
            "zone_lon": round(self.lon, 6),
            "zone_radius_nm": self.radius_nm,
            "zone_floor_m": self.floor_m,
            "zone_ceiling_m": self.ceiling_m,
        }


def _to_float(text):
    return float(text.replace(",", "."))


def parse_altitude(text, *, upper):
    """Convierte una altura OpenAir a metros. ``upper`` indica si es AH."""
    original = text.strip()
    s = re.sub(r"\s+", " ", original.upper())
    if not s:
        raise OpenAirError("Falta el valor de altura.")
    if s in GROUND_WORDS:
        if upper:
            raise OpenAirError(f"La altura superior no puede ser '{original}'.")
        return 0.0
    if s in {"UNL", "UNLIM", "UNLIMITED"}:
        raise OpenAirError("La altura superior ilimitada (UNL) no está soportada: indicar un valor numérico.")

    match = _FLIGHT_LEVEL_RE.match(s)
    if match:
        return feet_to_meters(_to_float(match["value"]) * 100)

    match = _ALTITUDE_RE.match(s)
    if not match:
        raise OpenAirError(f"Altura no reconocida: '{original}'.")
    value = _to_float(match["value"])
    ref = match["ref"]
    if ref in {"AGL", "AAL", "SFC", "GND"}:
        if value == 0 and not upper:
            return 0.0
        raise OpenAirError(
            f"Altura sobre el terreno no soportada: '{original}'. "
            "Las aeronaves informan altitud barométrica: usar AMSL o FL."
        )
    meters = value if match["unit"] == "M" else feet_to_meters(value)
    if meters < 0:
        raise OpenAirError(f"La altura no puede ser negativa: '{original}'.")
    return meters


def _parse_angle(text, *, max_degrees, what):
    parts = text.split(":")
    if not 1 <= len(parts) <= 3 or any(not p for p in parts):
        raise OpenAirError(f"{what} no reconocida: '{text}'.")
    try:
        numbers = [_to_float(p) for p in parts]
    except ValueError:
        raise OpenAirError(f"{what} no reconocida: '{text}'.") from None
    # Solo el último componente puede tener decimales (DMS o DDM).
    if any(n != int(n) for n in numbers[:-1]):
        raise OpenAirError(f"{what} no reconocida: '{text}'.")
    degrees = numbers[0]
    minutes = numbers[1] if len(numbers) > 1 else 0.0
    seconds = numbers[2] if len(numbers) > 2 else 0.0
    if minutes >= 60 or seconds >= 60:
        raise OpenAirError(f"{what} fuera de rango: '{text}' (minutos y segundos deben ser menores a 60).")
    value = degrees + minutes / 60 + seconds / 3600
    if value > max_degrees:
        raise OpenAirError(f"{what} fuera de rango: '{text}'.")
    return value


def parse_point(text):
    """Convierte '35:06:43 S 058:43:34 W' (DMS o DDM) a (lat, lon) decimales."""
    match = _POINT_RE.match(text.strip().upper())
    if not match:
        raise OpenAirError(f"Coordenada no reconocida: '{text.strip()}'.")
    lat = _parse_angle(match["lat"], max_degrees=90, what="Latitud")
    lon = _parse_angle(match["lon"], max_degrees=180, what="Longitud")
    if match["ns"] == "S":
        lat = -lat
    if match["ew"] == "W":
        lon = -lon
    return lat, lon


def _new_block(lineno, airspace_class):
    return {"line": lineno, "class": airspace_class, "type": None, "name": None,
            "floor": None, "ceiling": None, "center": None, "radius": None}


def _apply_command(block, command, arg):
    if command == "AY":
        block["type"] = arg or None
    elif command == "AN":
        if not arg:
            raise OpenAirError("AN sin nombre.")
        block["name"] = arg
    elif command in {"AL", "AH"}:
        key = "floor" if command == "AL" else "ceiling"
        if block[key] is not None:
            raise OpenAirError(f"{command} repetido en la misma zona.")
        block[key] = parse_altitude(arg, upper=command == "AH")
    elif command == "V":
        var, _, value = arg.partition("=")
        var = var.strip().upper()
        if var == "X":
            block["center"] = parse_point(value)
        elif var not in {"D", "W", "Z"}:
            raise OpenAirError(f"Variable 'V {var}=' no reconocida.")
    elif command == "DC":
        if block["center"] is None:
            raise OpenAirError("DC sin centro: falta 'V X=' antes.")
        if block["radius"] is not None:
            raise OpenAirError("La zona tiene más de un círculo (DC).")
        try:
            radius = _to_float(arg)
        except ValueError:
            raise OpenAirError(f"Radio no reconocido: '{arg}' (en NM, sin unidad).") from None
        if radius <= 0:
            raise OpenAirError("El radio debe ser mayor que 0.")
        block["radius"] = radius
    elif command in SHAPE_COMMANDS:
        raise OpenAirError(f"'{command}' no está soportado: la zona debe ser un círculo (V X= y DC).")
    elif command not in IGNORED_COMMANDS:
        raise OpenAirError(f"Comando '{command}' no reconocido.")


def parse_openair(text):
    """Lee el texto de un archivo OpenAir y devuelve la única zona circular."""
    text = text.lstrip("﻿")
    blocks = []
    block = None

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("*", 1)[0].strip()
        if not line:
            continue
        command, _, arg = line.partition(" ")
        command = command.upper()
        arg = arg.strip()

        if command == "AC":
            block = _new_block(lineno, arg or None)
            blocks.append(block)
            continue
        try:
            if block is None:
                raise OpenAirError(f"'{command}' aparece antes de 'AC'; cada zona debe empezar con AC.")
            _apply_command(block, command, arg)
        except OpenAirError as exc:
            raise OpenAirError(f"Línea {lineno}: {exc}") from None

    if not blocks:
        raise OpenAirError("El archivo no contiene ninguna zona (falta 'AC').")
    if len(blocks) > 1:
        raise OpenAirError(f"El archivo contiene {len(blocks)} zonas; debe contener una sola.")

    block = blocks[0]
    missing = [label for key, label in (("name", "AN"), ("floor", "AL"), ("ceiling", "AH"),
                                         ("center", "V X="), ("radius", "DC")) if block[key] is None]
    if missing:
        raise OpenAirError(f"A la zona le falta: {', '.join(missing)}.")
    if len(block["name"]) > MAX_NAME_LENGTH:
        raise OpenAirError(f"El nombre de la zona supera los {MAX_NAME_LENGTH} caracteres.")
    if block["ceiling"] <= block["floor"]:
        raise OpenAirError("La altura superior (AH) debe ser mayor que la inferior (AL).")

    lat, lon = block["center"]
    return OpenAirZone(
        name=block["name"],
        lat=lat,
        lon=lon,
        radius_nm=block["radius"],
        floor_m=block["floor"],
        ceiling_m=block["ceiling"],
        airspace_class=block["class"],
        airspace_type=block["type"],
    )


def decode_openair_bytes(data):
    """Decodifica un archivo subido: UTF-8 (lo que pide la especificación) o Latin-1."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")
