"""Imagen del mapa que acompaña la alerta de Telegram.

Se arma en el servidor, sin navegador: se bajan las teselas de OpenStreetMap
que cubren la zona, se dibujan el círculo de la zona y la aeronave orientada
según su rumbo, y se devuelve un JPEG.

Política de uso de las teselas: https://operations.osmfoundation.org/policies/tiles/
  - User-Agent propio e identificable (settings.ADSBFI_USER_AGENT).
  - Cada tesela se guarda en memoria al menos 7 días: como la zona es fija,
    después de la primera alerta casi no se piden teselas nuevas.
  - Atribución «© OpenStreetMap» visible en la imagen.
  - Sin descargas masivas: solo las teselas de esta imagen, de a dos a la vez.
"""

import asyncio
import io
import math
import time
from collections import OrderedDict

import httpx
from PIL import Image, ImageDraw, ImageFont

from .zone import Zone

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE_SIZE = 256
WIDTH, HEIGHT = 800, 560
MAX_ZOOM = 16
MIN_ZOOM = 5
TILE_CACHE_TTL_S = 7 * 24 * 3600
TILE_CACHE_MAX = 400
TILE_TIMEOUT_S = 8.0
MAX_PARALLEL_TILES = 2
M_PER_NM = 1852.0
EARTH_CIRCUMFERENCE_M = 40075016.686

RED = (220, 53, 69)
WHITE = (255, 255, 255)
DARK = (33, 37, 41)

# Silueta de avión apuntando al norte, en coordenadas de -1 a 1 (y hacia abajo).
# Fuselaje más largo que las alas y alas con flecha, para que se lea la nariz.
PLANE_SHAPE = [
    (0.0, -1.0), (0.1, -0.88), (0.11, -0.3), (0.82, 0.12), (0.82, 0.27), (0.11, 0.1),
    (0.08, 0.68), (0.32, 0.86), (0.32, 0.97), (0.0, 0.91), (-0.32, 0.97), (-0.32, 0.86),
    (-0.08, 0.68), (-0.11, 0.1), (-0.82, 0.27), (-0.82, 0.12), (-0.11, -0.3), (-0.1, -0.88),
]


class MapImageError(Exception):
    pass


class TileCache:
    """Caché en memoria (no se escribe en disco). Clave: (z, x, y)."""

    def __init__(self, ttl_s=TILE_CACHE_TTL_S, max_items=TILE_CACHE_MAX, clock=time.monotonic):
        self._items = OrderedDict()
        self._ttl_s = ttl_s
        self._max = max_items
        self._clock = clock

    def get(self, key):
        item = self._items.get(key)
        if item is None:
            return None
        stored_at, data = item
        if self._clock() - stored_at > self._ttl_s:
            del self._items[key]
            return None
        self._items.move_to_end(key)
        return data

    def put(self, key, data):
        self._items[key] = (self._clock(), data)
        self._items.move_to_end(key)
        while len(self._items) > self._max:
            self._items.popitem(last=False)

    def __len__(self):
        return len(self._items)


tile_cache = TileCache()


# --- proyección Web Mercator --------------------------------------------------

def world_pixel(lat, lon, zoom):
    scale = TILE_SIZE * 2 ** zoom
    x = (lon + 180.0) / 360.0 * scale
    lat_r = math.radians(max(min(lat, 85.0511), -85.0511))
    y = (1 - math.asinh(math.tan(lat_r)) / math.pi) / 2 * scale
    return x, y


def meters_per_pixel(lat, zoom):
    return EARTH_CIRCUMFERENCE_M * math.cos(math.radians(lat)) / (TILE_SIZE * 2 ** zoom)


def choose_zoom(lat, radius_m, margin=1.35):
    """El zoom más cercano en el que entra el círculo de la zona con margen."""
    for zoom in range(MAX_ZOOM, MIN_ZOOM - 1, -1):
        if 2 * radius_m * margin / meters_per_pixel(lat, zoom) <= min(WIDTH, HEIGHT):
            return zoom
    return MIN_ZOOM


# --- teselas ------------------------------------------------------------------

async def fetch_tiles(client, zoom, keys, cache=tile_cache):
    semaphore = asyncio.Semaphore(MAX_PARALLEL_TILES)
    limit = 2 ** zoom

    async def one(x, y):
        key = (zoom, x % limit, y)
        cached = cache.get(key)
        if cached is not None:
            return (x, y), cached
        async with semaphore:
            url = TILE_URL.format(z=zoom, x=x % limit, y=y)
            try:
                response = await client.get(url, timeout=TILE_TIMEOUT_S)
            except httpx.HTTPError as exc:
                raise MapImageError(f"No se pudo bajar la tesela {key} ({exc.__class__.__name__}).") from None
        if response.status_code != 200:
            raise MapImageError(f"La tesela {key} respondió HTTP {response.status_code}.")
        cache.put(key, response.content)
        return (x, y), response.content

    results = await asyncio.gather(*(one(x, y) for x, y in keys if 0 <= y < limit))
    return dict(results)


# --- dibujo -------------------------------------------------------------------

def _font(size):
    return ImageFont.load_default(size=size)


def _plane_polygon(cx, cy, size, heading_deg):
    theta = math.radians(heading_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    return [
        (cx + size * (x * cos_t - y * sin_t), cy + size * (x * sin_t + y * cos_t))
        for x, y in PLANE_SHAPE
    ]


def _draw_plane(overlay, cx, cy, heading, size=26, scale=4):
    """Avión rojo con borde blanco y sombra, dibujado a 4x y reducido (antialias)."""
    box = int(size * 2.6) * scale
    layer = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    c = box / 2
    draw.polygon(_plane_polygon(c + 2 * scale, c + 2 * scale, size * scale, heading), fill=(0, 0, 0, 80))
    shape = _plane_polygon(c, c, size * scale, heading)
    # Borde blanco: línea centrada en el contorno (el outline de polygon se
    # dibuja hacia adentro y el relleno lo taparía).
    draw.line(shape + shape[:1], fill=WHITE + (255,), width=6 * scale, joint="curve")
    draw.polygon(shape, fill=RED + (255,))
    layer = layer.resize((box // scale, box // scale), Image.LANCZOS)
    half = box // scale // 2
    overlay.paste(layer, (round(cx) - half, round(cy) - half), layer)


def _km(nm):
    value = nm * 1.852
    return f"{value:.0f}" if value >= 20 else f"{value:.1f}".replace(".", ",").removesuffix(",0")


def _label(draw, xy, text, font, *, fill=DARK, background=(255, 255, 255, 225), padding=5):
    left, top, right, bottom = draw.textbbox(xy, text, font=font)
    draw.rounded_rectangle(
        (left - padding, top - padding, right + padding, bottom + padding), radius=4, fill=background
    )
    draw.text(xy, text, font=font, fill=fill)


def compose(tiles, zoom, origin, zone, alert):
    """Arma la imagen. ``origin`` = píxel mundial de la esquina superior izquierda."""
    left, top = origin
    image = Image.new("RGB", (WIDTH, HEIGHT), (232, 232, 232))
    for (x, y), data in tiles.items():
        try:
            tile = Image.open(io.BytesIO(data)).convert("RGB")
        except OSError as exc:
            raise MapImageError("Tesela con formato inválido.") from exc
        image.paste(tile, (round(x * TILE_SIZE - left), round(y * TILE_SIZE - top)))

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Zona de alerta
    zx, zy = world_pixel(zone.lat, zone.lon, zoom)
    zx, zy = zx - left, zy - top
    r = zone.radius_nm * M_PER_NM / meters_per_pixel(zone.lat, zoom)
    draw.ellipse((zx - r, zy - r, zx + r, zy + r), fill=RED + (38,), outline=RED + (255,), width=4)

    # Aeronave
    ax, ay = world_pixel(alert["lat"], alert["lon"], zoom)
    ax, ay = ax - left, ay - top
    heading = alert.get("track")
    if heading is None:
        heading = alert.get("true_heading")
    if heading is None:
        draw.ellipse((ax - 10, ay - 10, ax + 10, ay + 10), fill=RED + (255,), outline=WHITE + (255,), width=3)
    else:
        _draw_plane(overlay, ax, ay, heading)

    altitude = f"{alert['alt_ft']:,.0f} ft".replace(",", ".") if alert.get("alt_ft") is not None else ""
    text = " · ".join(part for part in (alert["label"], altitude) if part)
    label_x = ax + 34 if ax < WIDTH - 230 else ax - 34 - draw.textlength(text, font=_font(18))
    _label(draw, (label_x, ay - 11), text, _font(18))

    # Referencia y atribuciones
    _label(draw, (12, 12), f"Zona de alerta · radio {_km(zone.radius_nm)} km", _font(16), fill=RED)
    credit = "© colaboradores de OpenStreetMap · Aeronaves: adsb.fi"
    credit_font = _font(13)
    width = draw.textlength(credit, font=credit_font)
    _label(draw, (WIDTH - width - 10, HEIGHT - 22), credit, credit_font, padding=4)

    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue()


async def render_alert_map(alert, zone, *, client, cache=tile_cache):
    """Devuelve el JPEG del mapa para una alerta. Lanza ``MapImageError`` si falla."""
    if not isinstance(zone, Zone):
        raise MapImageError("Zona inválida.")
    zoom = choose_zoom(zone.lat, zone.radius_nm * M_PER_NM)
    cx, cy = world_pixel(zone.lat, zone.lon, zoom)
    left, top = cx - WIDTH / 2, cy - HEIGHT / 2
    first_x, first_y = math.floor(left / TILE_SIZE), math.floor(top / TILE_SIZE)
    last_x, last_y = math.floor((left + WIDTH - 1) / TILE_SIZE), math.floor((top + HEIGHT - 1) / TILE_SIZE)
    keys = [(x, y) for x in range(first_x, last_x + 1) for y in range(first_y, last_y + 1)]
    tiles = await fetch_tiles(client, zoom, keys, cache)
    return await asyncio.to_thread(compose, tiles, zoom, (left, top), zone, alert)


def demo_position(zone, distance_fraction=0.55, bearing_deg=60):
    """Un punto dentro de la zona, para el mensaje de prueba."""
    d = zone.radius_nm * M_PER_NM * distance_fraction
    lat = zone.lat + (d * math.cos(math.radians(bearing_deg))) / 111_320
    lon = zone.lon + (d * math.sin(math.radians(bearing_deg))) / (111_320 * math.cos(math.radians(zone.lat)))
    return lat, lon
