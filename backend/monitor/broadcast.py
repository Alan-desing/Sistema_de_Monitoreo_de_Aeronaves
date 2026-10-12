"""Mensajes hacia los navegadores conectados por WebSocket.

Todos los mensajes son JSON con un campo ``type``:
    snapshot  al conectarse: aeronaves, configuración pública y estado
    aircraft  en cada ciclo del monitor: lista completa de aeronaves y estado
    alert     una aeronave ingresó a la zona
    config    el administrador cambió la configuración
"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

GROUP = "aircraft"


def user_group(user_id):
    return f"user-{user_id}"


def public_config(config):
    """Configuración que puede ver cualquier usuario registrado (sin el token)."""
    return {
        "zone": {
            "name": config.zone_name,
            "lat": config.zone_lat,
            "lon": config.zone_lon,
            "radius_nm": config.zone_radius_nm,
            "floor_m": config.zone_floor_m,
            "ceiling_m": config.zone_ceiling_m,
        },
        "poll_interval_s": config.poll_interval_s,
        "query_radius_nm": config.query_radius_nm,
        "telegram_enabled": config.telegram_enabled,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


async def send(event):
    await get_channel_layer().group_send(GROUP, {"type": "monitor.event", "event": event})


async def send_aircraft(aircraft, status):
    await send({"type": "aircraft", "aircraft": aircraft, "status": status})


async def send_alert(alert):
    await send({"type": "alert", "alert": alert})


async def send_config(config):
    await send({"type": "config", "config": public_config(config)})


def send_config_sync(config):
    """Para las vistas (síncronas) que guardan la configuración."""
    async_to_sync(send_config)(config)


def disconnect_user_sync(user_id):
    """Cierra los WebSocket abiertos de un usuario (p. ej. al desactivarlo)."""
    async_to_sync(get_channel_layer().group_send)(user_group(user_id), {"type": "session.close"})
