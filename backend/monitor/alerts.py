"""Contenido de una alerta de ingreso a la zona (Telegram y web)."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings

from .zone import feet_to_meters


def build_alert(aircraft, zone):
    """Datos de la alerta. Se envían tal cual al navegador."""
    alt_ft = aircraft.alt_baro if isinstance(aircraft.alt_baro, (int, float)) else None
    return {
        "hex": aircraft.hex,
        "label": aircraft.label,
        "flight": aircraft.flight,
        "registration": aircraft.registration,
        "type": aircraft.type,
        "alt_ft": alt_ft,
        "alt_m": feet_to_meters(alt_ft) if alt_ft is not None else None,
        "gs": aircraft.gs,
        "track": aircraft.track,
        "true_heading": aircraft.true_heading,  # solo para orientar el avión en el mapa
        "dst": aircraft.dst,
        "lat": aircraft.lat,
        "lon": aircraft.lon,
        "zone": zone.name,
        "time": aircraft.timestamp,
    }


FR24_URL = "https://www.flightradar24.com"
_CALLSIGN = re.compile(r"^[A-Z0-9]{2,8}$")


def flightradar_url(alert):
    """Enlace a Flightradar24: el vuelo en vivo por indicativo; si no hay, la
    ficha de la aeronave por matrícula; si tampoco, el mapa en su posición."""
    flight = (alert.get("flight") or "").upper()
    if _CALLSIGN.match(flight):
        return f"{FR24_URL}/{flight}"
    if alert.get("registration"):
        return f"{FR24_URL}/data/aircraft/{alert['registration'].lower()}"
    return f"{FR24_URL}/{alert['lat']:.2f},{alert['lon']:.2f}/12"


def _integer(value):
    return f"{value:,.0f}".replace(",", ".")


def _decimal(value, digits=1):
    return f"{value:.{digits}f}".replace(".", ",")


def format_alert_message(alert):
    """Texto plano (sin Markdown/HTML, para no tener que escapar nada)."""
    ident = " · ".join(
        part for part in (alert["flight"], alert["registration"], alert["type"]) if part
    ) or alert["hex"].upper()
    if alert["alt_ft"] is not None:
        altitude = f"{_integer(alert['alt_ft'])} ft ({_integer(alert['alt_m'])} m)"
    else:
        altitude = "sin dato"
    speed = f"{_integer(alert['gs'])} kt" if alert["gs"] is not None else "sin dato"
    track = f"{alert['track']:03.0f}°" if alert["track"] is not None else "sin dato"
    when = datetime.fromtimestamp(alert["time"], ZoneInfo(settings.TIME_ZONE)).strftime("%H:%M:%S")
    return "\n".join(
        [
            f"✈️ Ingreso a {alert['zone']}",
            ident,
            f"Altitud: {altitude}",
            f"Velocidad: {speed}",
            f"Rumbo: {track}",
            f"Distancia al centro: {_decimal(alert['dst'])} NM",
            f"Hora: {when}",
            f"Flightradar24: {flightradar_url(alert)}",
        ]
    )
