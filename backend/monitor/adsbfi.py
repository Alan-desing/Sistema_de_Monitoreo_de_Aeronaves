"""Cliente de adsb.fi: consulta de aeronaves por punto y radio (endpoint v3).

Documentación de la API: https://github.com/adsbfi/opendata
    GET /api/v3/lat/{lat}/lon/{lon}/dist/{dist}   (dist en NM, máximo 250)
    Límite: 1 consulta por segundo. Los pedidos con respuesta 400, 401, 403,
    404 o 429 cuentan para una restricción temporal por IP, así que los
    parámetros se validan antes de enviar nada.

Formato de la respuesta (readsb ``jv2``, compatible con ADSBexchange v2):
https://github.com/wiedehopf/readsb/blob/dev/README-json.md
    now       hora del servidor, en MILISEGUNDOS desde la época Unix
    total     cantidad de aeronaves en ``ac``
    ac[]      aeronaves; los campos sin dato se omiten
      hex       dirección ICAO de 24 bits (puede empezar con "~" si no es ICAO)
      flight    indicativo, 8 caracteres rellenos con espacios
      r, t      matrícula y tipo, desde la base de datos de adsb.fi
      lat, lon  posición en grados decimales; se omiten si tiene más de 60 s
                (en ese caso aparece ``lastPosition``)
      alt_baro  altitud barométrica en pies, o el texto "ground"
      gs        velocidad respecto al suelo, en nudos
      track     rumbo verdadero sobre el suelo, en grados
      true_heading  proa verdadera; en tierra suele venir en lugar de track
      dst      distancia al punto consultado, en NM
      seen_pos  segundos transcurridos desde la última posición, antes de ``now``
"""

import math
from dataclasses import asdict, dataclass, field

import httpx

BASE_URL = "https://opendata.adsb.fi/api/v3"
# Máximo documentado; verificado: 250 NM responde 200 y 251 NM responde 400.
MAX_RADIUS_NM = 250
REQUEST_TIMEOUT_S = 10.0

# Sin estos campos una aeronave no se puede ubicar ni evaluar contra la zona.
REQUIRED_FIELDS = ("lat", "lon", "dst", "seen_pos")


class AdsbFiError(Exception):
    """Fallo de la consulta: red, HTTP distinto de 200 o respuesta inesperada."""


class AdsbFiRateLimited(AdsbFiError):
    """adsb.fi respondió 429. ``retry_after`` viene del encabezado, si lo hay."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class Aircraft:
    hex: str
    flight: str | None
    registration: str | None
    type: str | None
    lat: float
    lon: float
    alt_baro: float | str | None  # pies, "ground" o None si no se informa
    gs: float | None  # nudos
    track: float | None  # grados
    true_heading: float | None  # grados; solo para orientar el ícono si falta track
    dst: float  # NM al centro de la zona
    seen_pos: float  # segundos
    timestamp: float  # hora de la posición, en segundos Unix (now - seen_pos)

    @property
    def label(self):
        return self.flight or self.registration or self.hex

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Snapshot:
    now: float  # hora del servidor, en segundos Unix
    aircraft: list[Aircraft]
    # hex -> campos obligatorios ausentes, de las aeronaves que se descartaron
    skipped: dict[str, tuple[str, ...]] = field(default_factory=dict)
    msg: str | None = None

    @property
    def all_incomplete(self):
        """True si la respuesta trajo aeronaves pero ninguna utilizable."""
        return bool(self.skipped) and not self.aircraft


def _number(value):
    # bool es subclase de int: no es un número válido acá.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _text(value):
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _altitude(value):
    if value == "ground":
        return "ground"
    return _number(value)


def _format_radius(radius_nm):
    return f"{radius_nm:.3f}".rstrip("0").rstrip(".")


def build_url(lat, lon, radius_nm):
    """Arma la URL de consulta. Rechaza valores que adsb.fi respondería con 400."""
    lat, lon, radius_nm = _number(lat), _number(lon), _number(radius_nm)
    if lat is None or not -90 <= lat <= 90:
        raise ValueError(f"Latitud inválida: {lat!r}")
    if lon is None or not -180 <= lon <= 180:
        raise ValueError(f"Longitud inválida: {lon!r}")
    if radius_nm is None or not 0 < radius_nm <= MAX_RADIUS_NM:
        raise ValueError(f"Radio inválido: {radius_nm!r} (debe estar entre 0 y {MAX_RADIUS_NM} NM)")
    if _format_radius(radius_nm) == "0":
        raise ValueError(f"Radio demasiado chico: {radius_nm!r}")
    return f"{BASE_URL}/lat/{lat:.6f}/lon/{lon:.6f}/dist/{_format_radius(radius_nm)}"


def parse_aircraft(raw, now):
    """Convierte una aeronave de la respuesta.

    Devuelve ``(Aircraft, ())`` si se puede usar, o ``(None, faltantes)``.
    Nunca lanza excepción por datos incompletos o de tipo inesperado.
    """
    if not isinstance(raw, dict):
        return None, ("hex",)
    hex_code = _text(raw.get("hex"))
    values = {name: _number(raw.get(name)) for name in REQUIRED_FIELDS}
    missing = tuple(name for name, value in values.items() if value is None)
    if hex_code is None:
        missing = ("hex",) + missing
    if missing:
        return None, missing
    return (
        Aircraft(
            hex=hex_code.lower(),
            flight=_text(raw.get("flight")),
            registration=_text(raw.get("r")),
            type=_text(raw.get("t")),
            lat=values["lat"],
            lon=values["lon"],
            alt_baro=_altitude(raw.get("alt_baro")),
            gs=_number(raw.get("gs")),
            track=_number(raw.get("track")),
            true_heading=_number(raw.get("true_heading")),
            dst=values["dst"],
            seen_pos=values["seen_pos"],
            timestamp=now - values["seen_pos"],
        ),
        (),
    )


def parse_response(data):
    """Convierte la respuesta JSON de v3 en un ``Snapshot``."""
    if not isinstance(data, dict):
        raise AdsbFiError("Respuesta inesperada: no es un objeto JSON.")
    now_ms = _number(data.get("now"))
    if now_ms is None:
        raise AdsbFiError("Respuesta inesperada: falta 'now'.")
    raw_list = data.get("ac")
    if not isinstance(raw_list, list):
        raise AdsbFiError("Respuesta inesperada: falta la lista 'ac'.")

    now = now_ms / 1000.0
    aircraft = []
    skipped = {}
    for index, raw in enumerate(raw_list):
        ac, missing = parse_aircraft(raw, now)
        if ac is not None:
            aircraft.append(ac)
        else:
            hex_code = _text(raw.get("hex")) if isinstance(raw, dict) else None
            skipped[(hex_code or f"#{index}").lower()] = missing
    return Snapshot(now=now, aircraft=aircraft, skipped=skipped, msg=_text(data.get("msg")))


def make_client(user_agent):
    return httpx.AsyncClient(
        headers={"User-Agent": user_agent, "Accept": "application/json"},
        timeout=REQUEST_TIMEOUT_S,
        follow_redirects=False,
    )


def _retry_after(response):
    value = response.headers.get("Retry-After", "").strip()
    return float(value) if value.isdigit() else None


async def fetch_snapshot(client, lat, lon, radius_nm):
    """Hace UNA consulta a adsb.fi y devuelve el ``Snapshot``."""
    url = build_url(lat, lon, radius_nm)
    try:
        response = await client.get(url)
    except httpx.TimeoutException as exc:
        raise AdsbFiError(f"Tiempo de espera agotado consultando adsb.fi ({exc.__class__.__name__}).") from exc
    except httpx.HTTPError as exc:
        raise AdsbFiError(f"Error de red consultando adsb.fi: {exc}") from exc

    if response.status_code == 429:
        raise AdsbFiRateLimited("adsb.fi limitó las consultas (HTTP 429).", _retry_after(response))
    if response.status_code != 200:
        raise AdsbFiError(f"adsb.fi respondió HTTP {response.status_code}.")
    try:
        data = response.json()
    except ValueError as exc:
        raise AdsbFiError("La respuesta de adsb.fi no es JSON válido.") from exc
    return parse_response(data)
