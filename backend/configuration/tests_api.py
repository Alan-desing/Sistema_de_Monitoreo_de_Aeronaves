from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.roles import ADMIN_GROUP, USER_GROUP
from monitor.telegram import TelegramError

from .models import SystemConfig
from .tests import VALID

TOKEN = "123456789:AAH-secreto_del_bot_abcd"

CNA_FILE = b"""* Alerta Ca\xf1uelas CNA
AC R
AY ALERT
AN ALERTA CNA 10KM
AL PISO
AH 4400m
V X=35:06:43 S 058:43:34 W
DC 5.4
*
"""


@override_settings(INITIAL_CONFIG={**VALID, "telegram_bot_token": TOKEN, "telegram_chat_id": "-1001234567890"})
class ConfigApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("jefe", password="x")
        self.admin.groups.add(Group.objects.get(name=ADMIN_GROUP))
        self.user = User.objects.create_user("piloto", password="x")
        self.user.groups.add(Group.objects.get(name=USER_GROUP))
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        patcher = mock.patch("configuration.views.send_config_sync")
        self.send_config = patcher.start()
        self.addCleanup(patcher.stop)

    def test_registered_user_is_rejected(self):
        client = APIClient()
        client.force_authenticate(self.user)
        for method, url in (("get", "/api/config/"), ("patch", "/api/config/"), ("put", "/api/config/"),
                            ("post", "/api/config/openair/"), ("post", "/api/config/telegram-test/")):
            with self.subTest(method=method, url=url):
                self.assertEqual(getattr(client, method)(url, {}).status_code, 403)

    def test_get_masks_token(self):
        data = self.client.get("/api/config/").json()
        self.assertEqual(data["zone_name"], "ALERTA CNA 10KM")
        self.assertEqual(data["telegram_bot_token_masked"], "••••••••abcd")
        self.assertNotIn("secreto", str(data))
        self.assertNotIn("telegram_bot_token", data)
        self.assertTrue(data["telegram_enabled"])

    def test_patch_updates_broadcasts_and_refreshes(self):
        with mock.patch("configuration.views.monitor") as monitor:
            response = self.client.patch("/api/config/", {"poll_interval_s": 10, "zone_name": " NUEVA "}, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        config = SystemConfig.load()
        self.assertEqual(config.poll_interval_s, 10)
        self.assertEqual(config.zone_name, "NUEVA")
        self.assertEqual(config.telegram_bot_token, TOKEN)  # sin enviar el token, se conserva
        self.send_config.assert_called_once()
        monitor.request_refresh.assert_called_once()

    def test_validation_errors(self):
        cases = {
            "zone_lat": {"zone_lat": -95},
            "zone_lon": {"zone_lon": 200},
            "zone_radius_nm": {"zone_radius_nm": 0},
            "zone_ceiling_m": {"zone_floor_m": 5000},
            "poll_interval_s": {"poll_interval_s": 1},
            "query_radius_nm": {"query_radius_nm": 300},
            "telegram_chat_id": {"telegram_chat_id": "grupo"},
            "telegram_bot_token": {"telegram_bot_token": "no-es-token"},
        }
        for field, payload in cases.items():
            with self.subTest(field=field):
                response = self.client.patch("/api/config/", payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        query = self.client.patch("/api/config/", {"zone_radius_nm": 60}, format="json")
        self.assertIn("query_radius_nm", query.json())
        self.send_config.assert_not_called()
        self.assertEqual(SystemConfig.load().poll_interval_s, 5)

    def test_replace_and_clear_telegram(self):
        self.client.patch("/api/config/", {"telegram_bot_token": "999:NUEVO_token-wxyz"}, format="json")
        self.assertEqual(SystemConfig.load().telegram_bot_token, "999:NUEVO_token-wxyz")
        response = self.client.patch("/api/config/", {"telegram_bot_token": "", "telegram_chat_id": ""}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["telegram_enabled"])
        response = self.client.patch("/api/config/", {"telegram_chat_id": "-100123"}, format="json")
        self.assertIn("telegram_bot_token", response.json())

    def test_openair_parses_without_saving(self):
        self.client.patch("/api/config/", {"zone_name": "OTRA", "zone_radius_nm": 2}, format="json")
        upload = SimpleUploadedFile("cna.txt", CNA_FILE, content_type="text/plain")
        response = self.client.post("/api/config/openair/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, 200, response.json())
        data = response.json()
        self.assertEqual(data["zone_name"], "ALERTA CNA 10KM")
        self.assertEqual(data["zone_lat"], -35.111944)  # redondeado a 6 decimales
        self.assertEqual(data["zone_lon"], -58.726111)
        self.assertEqual(data["zone_ceiling_m"], 4400.0)
        self.assertEqual(SystemConfig.load().zone_name, "OTRA")

    def test_openair_errors(self):
        upload = SimpleUploadedFile("mal.txt", b"AC R\nDP 35:00:00 S 058:00:00 W\n")
        response = self.client.post("/api/config/openair/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Línea 2", response.json()["file"][0])
        big = SimpleUploadedFile("grande.txt", b"*" * (65 * 1024))
        self.assertEqual(self.client.post("/api/config/openair/", {"file": big}, format="multipart").status_code, 400)

    def test_telegram_test_endpoint(self):
        with mock.patch("configuration.views.send_test_message", mock.AsyncMock(return_value=("avion", True))):
            response = self.client.post("/api/config/telegram-test/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("avion", response.json()["detail"])
        self.assertIn("con el mapa", response.json()["detail"])
        with mock.patch("configuration.views.send_test_message", mock.AsyncMock(return_value=("avion", False))):
            response = self.client.post("/api/config/telegram-test/")
        self.assertIn("sin mapa", response.json()["detail"])
        error = TelegramError("Telegram rechazó el mensaje: Unauthorized — el token del bot no es válido.")
        with mock.patch("configuration.views.send_test_message", mock.AsyncMock(side_effect=error)):
            response = self.client.post("/api/config/telegram-test/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("token", response.json()["detail"])
