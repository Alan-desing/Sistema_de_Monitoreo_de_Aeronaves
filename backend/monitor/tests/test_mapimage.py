import io
import json

import httpx
from django.test import SimpleTestCase
from PIL import Image

from monitor import mapimage
from monitor.alerts import build_alert
from monitor.mapimage import (
    HEIGHT, WIDTH, MapImageError, TileCache, choose_zoom, demo_position, meters_per_pixel, render_alert_map,
    world_pixel,
)
from monitor.telegram import TelegramNotifier, send_alert

from .helpers import CNA, make_aircraft
from .test_telegram import config, mock_client

TOKEN = "123456789:AAH-secreto_del_bot"


def png_tile(color=(200, 220, 200)):
    out = io.BytesIO()
    Image.new("RGB", (256, 256), color).save(out, format="PNG")
    return out.getvalue()


class ProjectionTests(SimpleTestCase):
    def test_world_pixel(self):
        self.assertEqual(world_pixel(0, 0, 0), (128.0, 128.0))
        x, y = world_pixel(CNA.lat, CNA.lon, 11)
        self.assertEqual((int(x // 256), int(y // 256)), (689, 1237))  # tesela que contiene Cañuelas

    def test_zoom_fits_zone(self):
        zoom = choose_zoom(CNA.lat, CNA.radius_nm * 1852)
        diameter_px = 2 * CNA.radius_nm * 1852 / meters_per_pixel(CNA.lat, zoom)
        self.assertLessEqual(diameter_px * 1.35, min(WIDTH, HEIGHT))
        self.assertGreater(diameter_px * 1.35 * 2, min(WIDTH, HEIGHT))  # el siguiente zoom ya no entra

    def test_demo_position_is_inside_zone(self):
        lat, lon = demo_position(CNA)
        dx = (lon - CNA.lon) * 111_320 * 0.818
        dy = (lat - CNA.lat) * 111_320
        self.assertLess((dx * dx + dy * dy) ** 0.5, CNA.radius_nm * 1852)


class TileCacheTests(SimpleTestCase):
    def test_ttl_and_size(self):
        now = [0.0]
        cache = TileCache(ttl_s=10, max_items=2, clock=lambda: now[0])
        cache.put("a", b"1")
        cache.put("b", b"2")
        cache.put("c", b"3")
        self.assertIsNone(cache.get("a"))  # expulsado por tamaño
        self.assertEqual(cache.get("c"), b"3")
        now[0] = 11
        self.assertIsNone(cache.get("c"))  # vencido


class RenderTests(SimpleTestCase):
    def alert(self, **extra):
        lat, lon = demo_position(CNA)
        return build_alert(make_aircraft(lat=lat, lon=lon, dst=3, alt=2375, **extra), CNA)

    async def test_renders_jpeg_with_cached_tiles(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, content=png_tile())

        cache = TileCache()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                     headers={"User-Agent": "avion-test/1.0"}) as client:
            jpeg = await render_alert_map(self.alert(), CNA, client=client, cache=cache)
            first = len(requests)
            await render_alert_map(self.alert(track=None, true_heading=None), CNA, client=client, cache=cache)
        image = Image.open(io.BytesIO(jpeg))
        self.assertEqual((image.format, image.size), ("JPEG", (WIDTH, HEIGHT)))
        self.assertTrue(4 <= first <= 12, first)
        self.assertEqual(len(requests), first)  # la segunda imagen sale toda de la caché
        self.assertTrue(all(r.url.host == "tile.openstreetmap.org" for r in requests))
        self.assertEqual(requests[0].headers["User-Agent"], "avion-test/1.0")
        # El círculo rojo de la zona está dibujado en el centro de la imagen.
        r, g, b = image.convert("RGB").getpixel((WIDTH // 2, HEIGHT // 2 - 1))
        self.assertGreater(r, g)

    async def test_tile_error_raises(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(429))) as client:
            with self.assertRaises(MapImageError):
                await render_alert_map(self.alert(), CNA, client=client, cache=TileCache())


class SendAlertTests(SimpleTestCase):
    async def test_photo_with_caption(self):
        seen = {}

        def handler(request):
            seen["path"] = request.url.path
            seen["body"] = request.content
            return httpx.Response(200, json={"ok": True, "result": {"photo": [{}], "chat": {"title": "avion"}}})

        async with mock_client(handler) as client:
            await send_alert(client, TOKEN, "-100", "texto de la alerta", b"\xff\xd8JPEG")
        self.assertTrue(seen["path"].endswith("/sendPhoto"))
        self.assertIn(b'name="caption"', seen["body"])
        self.assertIn("texto de la alerta".encode(), seen["body"])
        self.assertIn(b"\xff\xd8JPEG", seen["body"])

    async def test_rejected_photo_falls_back_to_text(self):
        paths = []

        def handler(request):
            paths.append(request.url.path.rsplit("/", 1)[1])
            if paths[-1] == "sendPhoto":
                return httpx.Response(400, json={"ok": False, "description": "Bad Request: PHOTO_INVALID_DIMENSIONS"})
            return httpx.Response(200, json={"ok": True, "result": {}})

        async with mock_client(handler) as client:
            with self.assertLogs("monitor.telegram", "WARNING"):
                await send_alert(client, TOKEN, "-100", "texto", b"jpeg")
        self.assertEqual(paths, ["sendPhoto", "sendMessage"])

    async def test_without_photo_sends_text(self):
        paths = []
        async with mock_client(lambda r: paths.append(r.url.path) or httpx.Response(200, json={"ok": True})) as client:
            await send_alert(client, TOKEN, "-100", "texto", None)
        self.assertTrue(paths[0].endswith("/sendMessage"))


class NotifierMapTests(SimpleTestCase):
    async def test_map_failure_still_sends_text(self):
        async def broken_render(alert, zone):
            raise MapImageError("sin teselas")

        async def load():
            return config()

        async def no_sleep(_):
            pass

        paths = []
        notifier = TelegramNotifier(load, render_map=broken_render, sleep=no_sleep)
        async with mock_client(lambda r: paths.append(r.url.path) or httpx.Response(200, json={"ok": True})) as client:
            with self.assertLogs("monitor.telegram", "INFO") as logs:
                sent = await notifier.deliver(client, build_alert(make_aircraft(), CNA), CNA)
        self.assertTrue(sent)
        self.assertTrue(paths[0].endswith("/sendMessage"))
        self.assertTrue(any("sin teselas" in line for line in logs.output))

    async def test_map_is_sent_as_photo(self):
        async def render(alert, zone):
            self.assertEqual(zone, CNA)
            return b"jpeg"

        async def load():
            return config()

        paths = []
        notifier = TelegramNotifier(load, render_map=render)
        async with mock_client(lambda r: paths.append(r.url.path) or httpx.Response(200, json={"ok": True})) as client:
            with self.assertLogs("monitor.telegram", "INFO") as logs:
                await notifier.deliver(client, build_alert(make_aircraft(), CNA), CNA)
        self.assertTrue(paths[0].endswith("/sendPhoto"))
        self.assertIn("con mapa", logs.output[-1])
        json.dumps(build_alert(make_aircraft(), CNA))  # la alerta sigue siendo JSON para el navegador
        self.assertTrue(mapimage.TILE_URL.startswith("https://tile.openstreetmap.org/"))
