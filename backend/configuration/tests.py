from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import TestCase, override_settings

from .models import SystemConfig

VALID = {
    "zone_name": "ALERTA CNA 10KM",
    "zone_lat": -35.111944,
    "zone_lon": -58.726111,
    "zone_radius_nm": 5.4,
    "zone_floor_m": 0.0,
    "zone_ceiling_m": 4400.0,
    "poll_interval_s": 5,
    "query_radius_nm": 50.0,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
}


def make(**overrides):
    return SystemConfig(**{**VALID, **overrides})


class ValidationTests(TestCase):
    def assertInvalid(self, field, **overrides):
        with self.assertRaises(ValidationError) as ctx:
            make(**overrides).full_clean()
        self.assertIn(field, ctx.exception.message_dict)

    def test_valid_defaults(self):
        make().full_clean()

    def test_coordinates_range(self):
        self.assertInvalid("zone_lat", zone_lat=-90.1)
        self.assertInvalid("zone_lat", zone_lat=90.1)
        self.assertInvalid("zone_lon", zone_lon=-180.1)
        self.assertInvalid("zone_lon", zone_lon=180.1)
        make(zone_lat=-90, zone_lon=180).full_clean()

    def test_zone_radius_must_be_positive(self):
        self.assertInvalid("zone_radius_nm", zone_radius_nm=0)
        self.assertInvalid("zone_radius_nm", zone_radius_nm=-1)

    def test_ceiling_above_floor(self):
        self.assertInvalid("zone_ceiling_m", zone_floor_m=500, zone_ceiling_m=500)
        self.assertInvalid("zone_ceiling_m", zone_floor_m=500, zone_ceiling_m=400)
        make(zone_floor_m=500, zone_ceiling_m=501).full_clean()

    def test_floor_not_negative(self):
        self.assertInvalid("zone_floor_m", zone_floor_m=-1)

    def test_poll_interval_minimum(self):
        self.assertInvalid("poll_interval_s", poll_interval_s=1)
        self.assertInvalid("poll_interval_s", poll_interval_s=0)
        make(poll_interval_s=2).full_clean()

    def test_query_radius_limits(self):
        self.assertInvalid("query_radius_nm", query_radius_nm=5.3)
        self.assertInvalid("query_radius_nm", query_radius_nm=250.1)
        make(query_radius_nm=5.4).full_clean()
        make(query_radius_nm=250).full_clean()

    def test_telegram_token_and_chat_go_together(self):
        self.assertInvalid("telegram_chat_id", telegram_bot_token="123456:ABC-def_ghi")
        self.assertInvalid("telegram_bot_token", telegram_chat_id="-1001234567890")
        make(telegram_bot_token="123456:ABC-def_ghi", telegram_chat_id="-1001234567890").full_clean()

    def test_telegram_formats(self):
        self.assertInvalid(
            "telegram_bot_token", telegram_bot_token="sin-dos-puntos", telegram_chat_id="-100123"
        )
        self.assertInvalid(
            "telegram_chat_id", telegram_bot_token="123456:ABC", telegram_chat_id="grupo"
        )

    def test_surface_flag(self):
        self.assertTrue(make(zone_floor_m=0).zone_is_surface)
        self.assertFalse(make(zone_floor_m=10).zone_is_surface)


class SingletonTests(TestCase):
    @override_settings(INITIAL_CONFIG=VALID)
    def test_load_creates_from_initial_config_once(self):
        self.assertFalse(SystemConfig.objects.exists())
        cfg = SystemConfig.load()
        self.assertEqual(cfg.pk, SystemConfig.SINGLETON_PK)
        self.assertEqual(cfg.zone_name, "ALERTA CNA 10KM")
        self.assertEqual(cfg.query_radius_nm, 50.0)

        cfg.poll_interval_s = 30
        cfg.save()
        with override_settings(INITIAL_CONFIG={**VALID, "poll_interval_s": 10}):
            self.assertEqual(SystemConfig.load().poll_interval_s, 30)
        self.assertEqual(SystemConfig.objects.count(), 1)

    def test_save_always_uses_singleton_pk(self):
        make().save()
        make(zone_name="OTRA").save()
        self.assertEqual(SystemConfig.objects.count(), 1)
        self.assertEqual(SystemConfig.objects.get().zone_name, "OTRA")

    @override_settings(INITIAL_CONFIG={**VALID, "poll_interval_s": 1})
    def test_invalid_initial_config_fails_loudly(self):
        with self.assertRaises(ImproperlyConfigured):
            SystemConfig.load()
        self.assertFalse(SystemConfig.objects.exists())
