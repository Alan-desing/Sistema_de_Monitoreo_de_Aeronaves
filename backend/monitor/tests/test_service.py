from types import SimpleNamespace

from django.test import SimpleTestCase

from monitor import service
from monitor.adsbfi import AdsbFiError, AdsbFiRateLimited
from monitor.service import MAX_BACKOFF_S, Monitor, backoff_delay

from .helpers import NOW, make_aircraft, make_snapshot

CONFIG = SimpleNamespace(
    zone_name="ALERTA CNA 10KM", zone_lat=-35.111944, zone_lon=-58.726111, zone_radius_nm=5.4,
    zone_floor_m=0.0, zone_ceiling_m=4400.0, poll_interval_s=5, query_radius_nm=50.0,
    telegram_bot_token="", telegram_chat_id="", telegram_enabled=False,
)


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class FakePublisher:
    def __init__(self):
        self.alerts, self.updates = [], []

    async def send_alert(self, alert):
        self.alerts.append(alert)

    async def send_aircraft(self, aircraft, status):
        self.updates.append((aircraft, dict(status)))


class FakeNotifier:
    def __init__(self):
        self.queued = []

    def start(self):
        pass

    def enqueue(self, alert, zone=None):
        self.queued.append(alert)
        self.zones = getattr(self, "zones", []) + [zone]


class BackoffTests(SimpleTestCase):
    def test_growing_delay(self):
        self.assertEqual([backoff_delay(5, n) for n in range(1, 8)], [10, 20, 40, 80, 160, 300, 300])
        self.assertEqual(backoff_delay(5, 1, retry_after=60), 60)
        self.assertEqual(backoff_delay(60, 10), MAX_BACKOFF_S)


class CycleTests(SimpleTestCase):
    def setUp(self):
        self.responses = []
        self.queries = []
        self.config = SimpleNamespace(**vars(CONFIG))
        self.clock = FakeClock()
        self.publisher = FakePublisher()
        self.notifier = FakeNotifier()

        async def fetch(client, lat, lon, radius):
            self.queries.append((lat, lon, radius))
            item = self.responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        async def load_config():
            return self.config

        self.monitor = Monitor(fetch=fetch, load_config=load_config, notifier=self.notifier,
                               publisher=self.publisher, clock=self.clock)

    async def cycle(self, response):
        self.responses.append(response)
        self.clock.t += 5
        return await self.monitor.run_cycle(client=None)

    async def test_entry_alerts_once_on_both_channels(self):
        with self.assertLogs("monitor.service", "INFO") as logs:
            await self.cycle(make_snapshot(make_aircraft(dst=10)))
            await self.cycle(make_snapshot(make_aircraft(dst=3, now=NOW + 5), now=NOW + 5))
            delay = await self.cycle(make_snapshot(make_aircraft(dst=2, now=NOW + 10), now=NOW + 10))
        self.assertEqual(len(self.notifier.queued), 1)
        self.assertEqual(self.notifier.zones[0].radius_nm, 5.4)  # la zona viaja con la alerta (para el mapa)
        self.assertEqual(len(self.publisher.alerts), 1)
        self.assertEqual(self.publisher.alerts[0]["label"], "ARG1309")
        self.assertEqual(self.publisher.alerts[0]["zone"], "ALERTA CNA 10KM")
        self.assertEqual(len(self.publisher.updates), 3)
        self.assertEqual(delay, 5)
        self.assertTrue(any("ALERTA" in line for line in logs.output))

    async def test_query_follows_saved_config_each_cycle(self):
        await self.cycle(make_snapshot())
        self.config.zone_lat, self.config.zone_lon, self.config.query_radius_nm = -34.0, -58.0, 80.0
        self.config.poll_interval_s = 30
        delay = await self.cycle(make_snapshot(now=NOW + 5))
        self.assertEqual(self.queries, [(-35.111944, -58.726111, 50.0), (-34.0, -58.0, 80.0)])
        self.assertEqual(delay, 30)

    async def test_failures_back_off_and_recover(self):
        with self.assertLogs("monitor.service", "WARNING"):
            d1 = await self.cycle(AdsbFiError("caído"))
            d2 = await self.cycle(AdsbFiError("caído"))
            d3 = await self.cycle(AdsbFiRateLimited("429", retry_after=120))
        self.assertEqual((d1, d2, d3), (10, 20, 120))
        status = self.publisher.updates[-1][1]
        self.assertFalse(status["ok"])
        self.assertEqual(status["failures"], 3)
        with self.assertLogs("monitor.service", "INFO"):
            d4 = await self.cycle(make_snapshot())
        self.assertEqual(d4, 5)
        self.assertTrue(self.monitor.status["ok"])
        self.assertEqual(self.monitor.status["failures"], 0)

    async def test_purges_stale_aircraft_while_source_is_down(self):
        await self.cycle(make_snapshot(make_aircraft(seen_pos=0)))
        with self.assertLogs("monitor.service", "WARNING"):
            for _ in range(15):  # 15 ciclos de 5 s = 75 s sin respuesta
                await self.cycle(AdsbFiError("caído"))
        self.assertEqual(self.monitor.state.aircraft, {})
        self.assertEqual(self.publisher.updates[-1][0], [])

    async def test_incomplete_aircraft_logged_once(self):
        snap = lambda now: make_snapshot(make_aircraft(now=now), now=now, skipped={"abc123": ("lat", "lon", "dst")})  # noqa: E731
        with self.assertLogs("monitor.service", "WARNING") as logs:
            await self.cycle(snap(NOW))
            await self.cycle(snap(NOW + 5))
            await self.cycle(snap(NOW + 10))
        self.assertEqual(len([line for line in logs.output if "abc123" in line]), 1)

    async def test_all_incomplete_logs_error(self):
        with self.assertLogs("monitor.service", "ERROR") as logs:
            await self.cycle(make_snapshot(skipped={"a": ("lat",), "b": ("dst",)}))
        self.assertIn("Ninguna aeronave", logs.output[0])

    async def test_requests_are_spaced(self):
        slept = []

        async def fake_sleep(seconds):
            slept.append(seconds)

        original = service.asyncio.sleep
        service.asyncio.sleep = fake_sleep
        try:
            self.responses += [make_snapshot(), make_snapshot()]
            await self.monitor.run_cycle(None)
            self.clock.t += 0.5  # refresco pedido medio segundo después
            await self.monitor.run_cycle(None)
        finally:
            service.asyncio.sleep = original
        self.assertEqual(slept, [service.MIN_REQUEST_GAP_S - 0.5])
