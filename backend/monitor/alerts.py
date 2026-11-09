"""Contenido de una alerta de ingreso a la zona (Telegram y web)."""

import re
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from django.conf import settings

from .zone import feet_to_meters

ARGENTINA_TZ = "America/Argentina/Buenos_Aires"


def alert_clock(epoch):
    """Hora de la zona; si la zona no está en Argentina, también la hora argentina."""
    def hhmmss(tz):
        return datetime.fromtimestamp(epoch, ZoneInfo(tz)).strftime("%H:%M:%S")

    if settings.TIME_ZONE == ARGENTINA_TZ:
        return hhmmss(ARGENTINA_TZ)
    return f"{hhmmss(settings.TIME_ZONE)} (hora local) · {hhmmss(ARGENTINA_TZ)} en Argentina"


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
        "true_heading": aircraft.true_heading,
        "dst": aircraft.dst,
        "lat": aircraft.lat,
        "lon": aircraft.lon,
        "zone": zone.name,
        "time": aircraft.timestamp,
    }


FR24_URL = "https://www.flightradar24.com"
_CALLSIGN = re.compile(r"^[A-Z0-9]{2,8}$")


def flightradar_url(alert):
    """Enlace a Flightradar24: vuelo, ficha de aeronave o mapa en su posición."""
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
    """Genera el mensaje HTML de una alerta para Telegram."""
    ident = " · ".join(
        str(part) for part in (alert["flight"], alert["registration"], alert["type"]) if part
    ) or str(alert["hex"]).upper()

    if alert["alt_ft"] is not None:
        altitude = f"{_integer(alert['alt_ft'])} ft ({_integer(alert['alt_m'])} m)"
    else:
        altitude = "sin dato"

    speed = f"{_integer(alert['gs'])} kt" if alert["gs"] is not None else "sin dato"
    track = f"{alert['track']:03.0f}°" if alert["track"] is not None else "sin dato"
    distance = f"{_decimal(alert['dst'])} NM" if alert["dst"] is not None else "sin dato"
    when = alert_clock(alert["time"])

    zone = escape(str(alert["zone"]))
    ident = escape(ident)
    url = escape(flightradar_url(alert), quote=True)

    return "\n".join([
        "<b>✈️ INGRESO A ZONA DE ALERTA</b>",
        "",
        f"<b>Zona:</b> {zone}",
        "",
        f"<b>{ident}</b>",
        "",
        "━━━━━━━━━━━━━━━━",
        "",
        f"<b>ALTITUD</b> · {altitude}",
        "",
        f"<b>VELOCIDAD</b> · {speed}",
        "",
        f"<b>RUMBO</b> · {track}",
        "",
        f"<b>DISTANCIA AL CENTRO</b> · {distance}",
        "",
        "━━━━━━━━━━━━━━━━",
        "",
        f"<b>Hora:</b> {when}",
        "",
        f'🔗 <a href="{url}">Ver aeronave en Flightradar24</a>',
    ])
