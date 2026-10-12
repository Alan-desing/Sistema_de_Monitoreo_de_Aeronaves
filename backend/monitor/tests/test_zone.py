from types import SimpleNamespace

from django.test import SimpleTestCase

from monitor.zone import Zone, feet_to_meters, meters_to_feet

CNA = Zone(name="ALERTA CNA 10KM", lat=-35.111944, lon=-58.726111, radius_nm=5.4, floor_m=0, ceiling_m=4400)


def ac(dst=1.0, alt=1000):
    return SimpleNamespace(dst=dst, alt_baro=alt)


class ConversionTests(SimpleTestCase):
    def test_meters_feet(self):
        self.assertAlmostEqual(meters_to_feet(4400), 14435.6955, places=3)
        self.assertAlmostEqual(feet_to_meters(1), 0.3048)
        self.assertAlmostEqual(CNA.ceiling_ft, 14435.6955, places=3)


class ContainsTests(SimpleTestCase):
    def test_inside(self):
        self.assertTrue(CNA.contains(ac(dst=0.0, alt=0)))
        self.assertTrue(CNA.contains(ac(dst=5.39, alt=14435)))

    def test_radius_is_strict(self):
        self.assertFalse(CNA.contains(ac(dst=5.4)))
        self.assertFalse(CNA.contains(ac(dst=5.41)))

    def test_ceiling_is_strict_and_in_feet(self):
        # 4400 m = 14435.7 ft
        self.assertTrue(CNA.contains(ac(alt=14435)))
        self.assertFalse(CNA.contains(ac(alt=14436)))
        # Si se olvidara convertir y se comparara contra 4400 (metros), 4401 ft
        # quedaría afuera; en realidad está muy por debajo del techo.
        self.assertTrue(CNA.contains(ac(alt=4401)))

    def test_surface_has_no_lower_limit(self):
        self.assertTrue(CNA.is_surface)
        self.assertTrue(CNA.contains(ac(alt=-250)))

    def test_ground_or_missing_altitude_is_never_inside(self):
        self.assertFalse(CNA.contains(ac(alt="ground")))
        self.assertFalse(CNA.contains(ac(alt=None)))
        self.assertFalse(CNA.contains(ac(alt=True)))

    def test_missing_dst_is_never_inside(self):
        self.assertFalse(CNA.contains(ac(dst=None)))

    def test_floor_above_surface(self):
        zone = Zone(name="z", lat=0, lon=0, radius_nm=5, floor_m=300, ceiling_m=1000)  # 984.25 ft
        self.assertFalse(zone.is_surface)
        self.assertFalse(zone.contains(ac(alt=984)))
        self.assertTrue(zone.contains(ac(alt=985)))
        self.assertTrue(zone.contains(ac(alt=meters_to_feet(300))))  # base inclusiva
        self.assertFalse(zone.contains(ac(alt=-10)))

    def test_from_config(self):
        cfg = SimpleNamespace(zone_name="Z", zone_lat=1.0, zone_lon=2.0, zone_radius_nm=3.0,
                              zone_floor_m=0.0, zone_ceiling_m=500.0)
        self.assertEqual(Zone.from_config(cfg), Zone("Z", 1.0, 2.0, 3.0, 0.0, 500.0))
