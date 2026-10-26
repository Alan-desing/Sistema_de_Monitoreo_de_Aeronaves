import json
from types import SimpleNamespace

import httpx
from django.test import SimpleTestCase, override_settings

from monitor.alerts import build_alert, flightradar_url, format_alert_message
from monitor.telegram import MAX_ATTEMPTS, TelegramError, TelegramNotifier, send_message

from .helpers import CNA, NOW, make_aircraft

TOKEN = "123456789:AAH-secreto_del_bot"


def config(token=TOKEN, chat="-1001234567890"):
    return SimpleNamespace(telegram_bot_token=token, telegram_chat_id=chat,
                           telegram_enabled=bool(token and chat))


def mock_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@override_settings(TIME_ZONE="America/Argentina/Buenos_Aires")
class MessageTests(SimpleTestCase):
    def test_message_content(self):
        alert = build_alert(make_aircraft(dst=3.25, alt=2375, gs=142.2, track=6.7), CNA)
        text = format_alert_message(alert)
        self.assertIn("Ingreso a ALERTA CNA 10KM", text)
        self.assertIn("ARG1309 · LV-KNP · B38M", text)
        self.assertIn("Altitud: 2.375 ft (724 m)", text)
        self.assertIn("Velocidad: 142 kt", text)
        self.assertIn("Rumbo: 007°", text)
        self.assertIn("Distancia al centro: 3,2 NM", text)
        self.assertRegex(text, r"Hora: \d\d:\d\d:\d\d")
        self.assertIn("Flightradar24: https://www.flightradar24.com/ARG1309", text)

    def test_flightradar_url_falls_back_to_registration_then_position(self):
        by_reg = build_alert(make_aircraft(flight=None), CNA)
        self.assertEqual(flightradar_url(by_reg), "https://www.flightradar24.com/data/aircraft/lv-knp")
        # Indicativo inválido (adsb.fi a veces manda basura): no sirve para buscar el vuelo.
        garbage = build_alert(make_aircraft(flight="@@@@@@@@"), CNA)
        self.assertEqual(flightradar_url(garbage), "https://www.flightradar24.com/data/aircraft/lv-knp")
        by_pos = build_alert(make_aircraft(flight=None, registration=None), CNA)
        self.assertRegex(flightradar_url(by_pos), r"^https://www\.flightradar24\.com/-?\d+\.\d\d,-?\d+\.\d\d/12$")

    def test_missing_optional_data(self):
        alert = build_alert(make_aircraft(flight=None, registration=None, type=None, gs=None, track=None), CNA)
        text = format_alert_message(alert)
        self.assertIn("E0B390", text)
        self.assertIn("Velocidad: sin dato", text)
        self.assertIn("Rumbo: sin dato", text)
        self.assertEqual(alert["label"], "e0b390")

    def test_alert_identification_prefers_callsign_then_registration(self):
        self.assertEqual(build_alert(make_aircraft(), CNA)["label"], "ARG1309")
        self.assertEqual(build_alert(make_aircraft(flight=None), CNA)["label"], "LV-KNP")


class SendMessageTests(SimpleTestCase):
    async def test_success(self):
        seen = {}

        def handler(request):
            seen["path"] = request.url.path
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

        async with mock_client(handler) as client:
            await send_message(client, TOKEN, "-100123", "hola")
        self.assertEqual(seen["path"], f"/bot{TOKEN}/sendMessage")
        self.assertEqual(seen["body"]["chat_id"], "-100123")
        self.assertEqual(seen["body"]["text"], "hola")

    async def test_errors_are_classified(self):
        cases = [
            (429, {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 9}}, True),
            (502, {}, True),
            (401, {"ok": False, "description": "Unauthorized"}, False),
            (400, {"ok": False, "description": "Bad Request: chat not found"}, False),
        ]
        for status, body, retryable in cases:
            with self.subTest(status=status):
                async with mock_client(lambda r, s=status, b=body: httpx.Response(s, json=b)) as client:
                    with self.assertRaises(TelegramError) as ctx:
                        await send_message(client, TOKEN, "-100123", "x")
                self.assertEqual(ctx.exception.retryable, retryable)
                self.assertEqual(ctx.exception.status, status)
        self.assertEqual(ctx.exception.retry_after, None)

    async def test_token_never_in_error(self):
        def handler(request):
            raise httpx.ConnectError(f"fallo conectando a {request.url}")

        async with mock_client(handler) as client:
            with self.assertRaises(TelegramError) as ctx:
                await send_message(client, TOKEN, "-100123", "x")
        self.assertNotIn("secreto", str(ctx.exception))
        self.assertIsNone(ctx.exception.__cause__)
        self.assertTrue(ctx.exception.__suppress_context__)


class NotifierTests(SimpleTestCase):
    def setUp(self):
        self.sleeps = []
        self.alert = build_alert(make_aircraft(), CNA)

    async def fake_sleep(self, seconds):
        self.sleeps.append(seconds)

    def notifier(self, configs):
        configs = list(configs)

        async def load():
            return configs.pop(0) if len(configs) > 1 else configs[0]

        return TelegramNotifier(load, sleep=self.fake_sleep)

    async def test_retries_then_succeeds_using_latest_config(self):
        tokens = []
        responses = [httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 7}}),
                     httpx.Response(200, json={"ok": True, "result": {}})]

        def handler(request):
            tokens.append(request.url.path.split("/")[1])
            return responses.pop(0)

        notifier = self.notifier([config(token="1:viejo"), config(token="2:nuevo")])
        async with mock_client(handler) as client:
            with self.assertLogs("monitor.telegram", "INFO"):
                self.assertTrue(await notifier.deliver(client, self.alert))
        self.assertEqual(tokens, ["bot1:viejo", "bot2:nuevo"])
        self.assertEqual(self.sleeps, [7])

    async def test_gives_up_after_max_attempts(self):
        async with mock_client(lambda r: httpx.Response(503)) as client:
            with self.assertLogs("monitor.telegram", "ERROR"):
                self.assertFalse(await self.notifier([config()]).deliver(client, self.alert))
        self.assertEqual(len(self.sleeps), MAX_ATTEMPTS - 1)
        self.assertEqual(self.sleeps, sorted(self.sleeps))  # espera creciente

    async def test_permanent_error_is_not_retried(self):
        calls = []
        body = {"ok": False, "description": "Bad Request: group chat was upgraded to a supergroup chat",
                "parameters": {"migrate_to_chat_id": -1009999}}
        async with mock_client(lambda r: calls.append(r) or httpx.Response(400, json=body)) as client:
            with self.assertLogs("monitor.telegram", "ERROR") as logs:
                self.assertFalse(await self.notifier([config()]).deliver(client, self.alert))
        self.assertEqual(len(calls), 1)
        self.assertIn("-1009999", logs.output[0])
        self.assertNotIn("secreto", "".join(logs.output))

    async def test_not_configured_skips(self):
        calls = []
        async with mock_client(lambda r: calls.append(r)) as client:
            with self.assertLogs("monitor.telegram", "INFO"):
                self.assertFalse(await self.notifier([config(token="", chat="")]).deliver(client, self.alert))
        self.assertEqual(calls, [])
