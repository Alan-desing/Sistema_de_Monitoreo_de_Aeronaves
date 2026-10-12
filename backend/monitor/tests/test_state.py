from django.test import SimpleTestCase

from monitor.state import AircraftState

from .helpers import CNA, NOW, QUERY, make_aircraft, make_snapshot


class TransitionTests(SimpleTestCase):
    def setUp(self):
        self.state = AircraftState()

    def update(self, *aircraft, now=NOW, query=QUERY, skipped=None):
        return self.state.update(make_snapshot(*aircraft, now=now, skipped=skipped), CNA, query)

    def test_alert_only_on_entry(self):
        r = self.update(make_aircraft(dst=10))
        self.assertEqual(r.entered, [])
        r = self.update(make_aircraft(dst=5, now=NOW + 5), now=NOW + 5)
        self.assertEqual([a.hex for a in r.entered], ["e0b390"])
        self.assertIn("e0b390", self.state.inside)
        # Sigue adentro: no se repite la alerta.
        r = self.update(make_aircraft(dst=4, now=NOW + 10), now=NOW + 10)
        self.assertEqual(r.entered, [])

    def test_already_inside_on_first_sight_alerts(self):
        r = self.update(make_aircraft(dst=1))
        self.assertEqual(len(r.entered), 1)

    def test_exit_and_reentry_alerts_again(self):
        self.update(make_aircraft(dst=1))
        r = self.update(make_aircraft(dst=6, now=NOW + 5), now=NOW + 5)
        self.assertEqual(r.exited, ["e0b390"])
        self.assertNotIn("e0b390", self.state.inside)
        r = self.update(make_aircraft(dst=1, now=NOW + 10), now=NOW + 10)
        self.assertEqual(len(r.entered), 1)

    def test_leaving_through_ceiling_or_landing(self):
        self.update(make_aircraft(dst=1, alt=14000))
        r = self.update(make_aircraft(dst=1, alt=14500, now=NOW + 5), now=NOW + 5)
        self.assertEqual(r.exited, ["e0b390"])
        self.update(make_aircraft(dst=1, alt=500, now=NOW + 10), now=NOW + 10)
        r = self.update(make_aircraft(dst=1, alt="ground", now=NOW + 15), now=NOW + 15)
        self.assertEqual(r.exited, ["e0b390"])

    def test_missing_from_one_response_keeps_state(self):
        self.update(make_aircraft(dst=1))
        r = self.update(now=NOW + 5)
        self.assertEqual(r.purged, [])
        self.assertIn("e0b390", self.state.aircraft)
        self.assertIn("e0b390", self.state.inside)
        r = self.update(make_aircraft(dst=1, now=NOW + 10), now=NOW + 10)
        self.assertEqual(r.entered, [])

    def test_purge_by_position_age(self):
        self.update(make_aircraft(dst=1, seen_pos=0))
        r = self.update(now=NOW + 60)
        self.assertEqual(r.purged, [])
        r = self.update(now=NOW + 60.5)
        self.assertEqual(r.purged, ["e0b390"])
        self.assertEqual(self.state.aircraft, {})
        self.assertEqual(self.state.inside, {})

    def test_older_position_does_not_overwrite_newer(self):
        self.update(make_aircraft(dst=10, now=NOW))
        self.update(make_aircraft(dst=1, now=NOW - 3), now=NOW + 5)
        self.assertEqual(self.state.aircraft["e0b390"].dst, 10)

    def test_query_change_drops_aircraft_not_in_new_area(self):
        self.update(make_aircraft("aaa111", dst=1), make_aircraft("bbb222", dst=30))
        r = self.update(make_aircraft("aaa111", dst=1, now=NOW + 5), now=NOW + 5, query=(QUERY[0], QUERY[1], 20.0))
        self.assertEqual(r.purged, ["bbb222"])
        self.assertEqual(set(self.state.aircraft), {"aaa111"})
        self.assertEqual(r.entered, [])

    def test_incomplete_reported_once(self):
        r = self.update(make_aircraft(), skipped={"ccc333": ("lat", "lon")})
        self.assertEqual(r.newly_incomplete, {"ccc333": ("lat", "lon")})
        r = self.update(make_aircraft(now=NOW + 5), now=NOW + 5, skipped={"ccc333": ("lat", "lon")})
        self.assertEqual(r.newly_incomplete, {})
        self.update(make_aircraft(now=NOW + 10), now=NOW + 10)
        r = self.update(make_aircraft(now=NOW + 15), now=NOW + 15, skipped={"ccc333": ("dst",)})
        self.assertEqual(r.newly_incomplete, {"ccc333": ("dst",)})

    def test_all_incomplete_transitions(self):
        r = self.update(skipped={"a": ("lat",), "b": ("dst",)})
        self.assertTrue(r.all_incomplete_started)
        r = self.update(now=NOW + 5, skipped={"a": ("lat",)})
        self.assertFalse(r.all_incomplete_started)
        r = self.update(make_aircraft(now=NOW + 10), now=NOW + 10)
        self.assertTrue(r.all_incomplete_ended)

    def test_payload_marks_inside(self):
        self.update(make_aircraft("aaa111", dst=1), make_aircraft("bbb222", dst=30))
        payload = {p["hex"]: p for p in self.state.payload()}
        self.assertTrue(payload["aaa111"]["inside"])
        self.assertFalse(payload["bbb222"]["inside"])
        self.assertEqual(payload["aaa111"]["flight"], "ARG1309")
