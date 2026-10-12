import json
from pathlib import Path

import httpx
from django.test import SimpleTestCase

from monitor import adsbfi
from monitor.adsbfi import AdsbFiError, AdsbFiRateLimited, build_url, parse_aircraft, parse_response

FIXTURE = Path(__file__).parent / "fixtures" / "v3_sample.json"
NOW_MS = 1_791_602_276_000
NOW_S = NOW_MS / 1000


def raw(**overrides):
    base = {
        "hex": "E8061D",
        "flight": "JES3021 ",
        "r": "CC-DIH",
        "t": "A20N",
        "alt_baro": 7900,
        "gs": 293.5,
        "track": 134.31,
        "lat": -34.577419,
        "lon": -59.123383,
        "seen_pos": 0.371,
        "dst": 37.6,
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not ...}


class BuildUrlTests(SimpleTestCase):
    def test_v3_point_radius(self):
        self.assertEqual(
            build_url(-35.111944, -58.726111, 50),
            "https://opendata.adsb.fi/api/v3/lat/-35.111944/lon/-58.726111/dist/50",
        )

    def test_decimal_radius(self):
        self.assertTrue(build_url(0, 0, 5.4).endswith("/dist/5.4"))
        self.assertTrue(build_url(0, 0, 50.25).endswith("/dist/50.25"))

    def test_rejects_values_that_adsbfi_would_answer_400(self):
        for args in [(91, 0, 10), (0, -181, 10), (0, 0, 0), (0, 0, 250.1), (0, 0, -5), (0, 0, 0.0001),
                     (None, 0, 10), (True, 0, 10)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                build_url(*args)
        build_url(0, 0, 250)


class ParseAircraftTests(SimpleTestCase):
    def test_complete_aircraft(self):
        ac, missing = parse_aircraft(raw(), NOW_S)
        self.assertEqual(missing, ())
        self.assertEqual(ac.hex, "e8061d")
        self.assertEqual(ac.flight, "JES3021")
        self.assertEqual(ac.registration, "CC-DIH")
        self.assertEqual(ac.type, "A20N")
        self.assertEqual(ac.alt_baro, 7900)
        self.assertEqual(ac.dst, 37.6)
        self.assertAlmostEqual(ac.timestamp, NOW_S - 0.371)
        self.assertEqual(ac.label, "JES3021")

    def test_optional_fields_may_be_missing(self):
        ac, _ = parse_aircraft(raw(flight=..., r=..., t=..., gs=..., track=..., alt_baro=...), NOW_S)
        self.assertIsNone(ac.flight)
        self.assertIsNone(ac.registration)
        self.assertIsNone(ac.type)
        self.assertIsNone(ac.gs)
        self.assertIsNone(ac.track)
        self.assertIsNone(ac.alt_baro)
        self.assertEqual(ac.label, "e8061d")

    def test_label_falls_back_to_registration(self):
        ac, _ = parse_aircraft(raw(flight="        "), NOW_S)
        self.assertIsNone(ac.flight)
        self.assertEqual(ac.label, "CC-DIH")

    def test_alt_baro_ground_and_negative(self):
        self.assertEqual(parse_aircraft(raw(alt_baro="ground"), NOW_S)[0].alt_baro, "ground")
        self.assertEqual(parse_aircraft(raw(alt_baro=-75), NOW_S)[0].alt_baro, -75)
        self.assertIsNone(parse_aircraft(raw(alt_baro="7900"), NOW_S)[0].alt_baro)

    def test_missing_required_fields_are_reported(self):
        for name in ("lat", "lon", "dst", "seen_pos"):
            with self.subTest(field=name):
                ac, missing = parse_aircraft(raw(**{name: ...}), NOW_S)
                self.assertIsNone(ac)
                self.assertEqual(missing, (name,))

    def test_stale_position_uses_last_position_and_is_skipped(self):
        # Con la posición vencida (>60 s) adsb.fi omite lat/lon y manda lastPosition.
        data = raw(lat=..., lon=..., dst=..., seen_pos=...)
        data["lastPosition"] = {"lat": -34.5, "lon": -58.4, "seen_pos": 75.0}
        ac, missing = parse_aircraft(data, NOW_S)
        self.assertIsNone(ac)
        self.assertEqual(set(missing), {"lat", "lon", "dst", "seen_pos"})

    def test_wrong_types_never_raise(self):
        for bad in ({"hex": 123}, {"hex": "abc", "lat": "x", "lon": [], "dst": {}, "seen_pos": True},
                    "no-es-dict", None, {"hex": "abc", "lat": float("nan"), "lon": 1, "dst": 1, "seen_pos": 0}):
            with self.subTest(bad=bad):
                ac, missing = parse_aircraft(bad, NOW_S)
                self.assertIsNone(ac)
                self.assertTrue(missing)

    def test_non_icao_hex_is_kept(self):
        self.assertEqual(parse_aircraft(raw(hex="~2A0F1B"), NOW_S)[0].hex, "~2a0f1b")


class ParseResponseTests(SimpleTestCase):
    def test_real_v3_response(self):
        data = json.loads(FIXTURE.read_text())
        snap = parse_response(data)
        self.assertEqual(snap.now, data["now"] / 1000)  # v3: now en milisegundos
        self.assertEqual(len(snap.aircraft), data["total"])
        self.assertEqual(snap.skipped, {})
        self.assertEqual(snap.msg, "No error")
        for ac in snap.aircraft:
            self.assertEqual(ac.flight, ac.flight.strip())
            self.assertLess(ac.dst, 50.5)

    def test_incomplete_aircraft_do_not_break_the_cycle(self):
        snap = parse_response({"now": NOW_MS, "ac": [raw(), raw(hex="aaa111", lat=...), "basura", {}]})
        self.assertEqual([a.hex for a in snap.aircraft], ["e8061d"])
        self.assertEqual(snap.skipped["aaa111"], ("lat",))
        self.assertIn("#2", snap.skipped)
        self.assertIn("#3", snap.skipped)
        self.assertFalse(snap.all_incomplete)

    def test_all_incomplete(self):
        snap = parse_response({"now": NOW_MS, "ac": [raw(dst=...), raw(hex="b", lat=...)]})
        self.assertTrue(snap.all_incomplete)
        self.assertFalse(parse_response({"now": NOW_MS, "ac": []}).all_incomplete)

    def test_unexpected_responses(self):
        for data in ([], {"ac": []}, {"now": "x", "ac": []}, {"now": NOW_MS}, {"now": NOW_MS, "ac": {}},
                     {"now": NOW_MS, "aircraft": []}):
            with self.subTest(data=data), self.assertRaises(AdsbFiError):
                parse_response(data)


class FetchTests(SimpleTestCase):
    def client_for(self, handler):
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers={"User-Agent": "avion-test/1.0"},
        )

    async def test_success_sends_user_agent_and_v3_url(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["ua"] = request.headers["User-Agent"]
            return httpx.Response(200, json={"now": NOW_MS, "total": 1, "ac": [raw()]})

        async with self.client_for(handler) as client:
            snap = await adsbfi.fetch_snapshot(client, -35.111944, -58.726111, 50)
        self.assertEqual(seen["url"], "https://opendata.adsb.fi/api/v3/lat/-35.111944/lon/-58.726111/dist/50")
        self.assertEqual(seen["ua"], "avion-test/1.0")
        self.assertEqual(len(snap.aircraft), 1)

    async def test_rate_limited(self):
        async with self.client_for(lambda r: httpx.Response(429, headers={"Retry-After": "7"})) as client:
            with self.assertRaises(AdsbFiRateLimited) as ctx:
                await adsbfi.fetch_snapshot(client, 0, 0, 10)
        self.assertEqual(ctx.exception.retry_after, 7)

    async def test_http_error(self):
        async with self.client_for(lambda r: httpx.Response(503)) as client:
            with self.assertRaisesMessage(AdsbFiError, "HTTP 503"):
                await adsbfi.fetch_snapshot(client, 0, 0, 10)

    async def test_invalid_json(self):
        async with self.client_for(lambda r: httpx.Response(200, text="<html>")) as client:
            with self.assertRaisesMessage(AdsbFiError, "JSON"):
                await adsbfi.fetch_snapshot(client, 0, 0, 10)

    async def test_network_error_and_timeout(self):
        for exc in (httpx.ConnectError("sin red"), httpx.ReadTimeout("lento")):
            def handler(request, exc=exc):
                raise exc

            with self.subTest(exc=exc):
                async with self.client_for(handler) as client:
                    with self.assertRaises(AdsbFiError):
                        await adsbfi.fetch_snapshot(client, 0, 0, 10)

    async def test_invalid_parameters_are_not_sent(self):
        calls = []
        async with self.client_for(lambda r: calls.append(r) or httpx.Response(200)) as client:
            with self.assertRaises(ValueError):
                await adsbfi.fetch_snapshot(client, 0, 0, 300)
        self.assertEqual(calls, [])

    def test_make_client_sets_identifiable_user_agent(self):
        client = adsbfi.make_client("avion-monitor/0.1 (monitor privado de aeronaves)")
        self.assertEqual(client.headers["User-Agent"], "avion-monitor/0.1 (monitor privado de aeronaves)")
