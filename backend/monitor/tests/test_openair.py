from django.test import SimpleTestCase

from monitor.openair import OpenAirError, decode_openair_bytes, parse_altitude, parse_openair, parse_point
from monitor.zone import feet_to_meters

CNA_FILE = """\
* Alerta Cañuelas CNA
AC R
AY ALERT
AN ALERTA CNA 10KM
AL PISO
AH 4400m
V X=35:06:43 S 058:43:34 W
DC 5.4
*
"""


class CnaFileTests(SimpleTestCase):
    def test_current_file(self):
        zone = parse_openair(CNA_FILE)
        self.assertEqual(zone.name, "ALERTA CNA 10KM")
        self.assertAlmostEqual(zone.lat, -(35 + 6 / 60 + 43 / 3600))
        self.assertAlmostEqual(zone.lon, -(58 + 43 / 60 + 34 / 3600))
        self.assertAlmostEqual(zone.lat, -35.111944, places=6)
        self.assertAlmostEqual(zone.lon, -58.726111, places=6)
        self.assertEqual(zone.radius_nm, 5.4)
        self.assertEqual(zone.floor_m, 0.0)
        self.assertEqual(zone.ceiling_m, 4400.0)
        self.assertEqual(zone.airspace_class, "R")
        self.assertEqual(zone.airspace_type, "ALERT")
        self.assertEqual(
            set(zone.as_config_fields()),
            {"zone_name", "zone_lat", "zone_lon", "zone_radius_nm", "zone_floor_m", "zone_ceiling_m"},
        )

    def test_latin1_upload(self):
        text = decode_openair_bytes(CNA_FILE.encode("latin-1"))
        self.assertEqual(parse_openair(text).name, "ALERTA CNA 10KM")
        self.assertEqual(decode_openair_bytes("﻿AC R".encode("utf-8")), "AC R")


class AltitudeTests(SimpleTestCase):
    def test_ground_words(self):
        for text in ("GND", "SFC", "PISO", "piso", "0", "0ft AGL"):
            with self.subTest(text=text):
                self.assertEqual(parse_altitude(text, upper=False), 0.0)

    def test_units(self):
        self.assertEqual(parse_altitude("4400m", upper=True), 4400.0)
        self.assertEqual(parse_altitude("4400 M", upper=True), 4400.0)
        self.assertAlmostEqual(parse_altitude("14436ft", upper=True), feet_to_meters(14436))
        self.assertAlmostEqual(parse_altitude("1000ft AMSL", upper=True), 304.8)
        self.assertAlmostEqual(parse_altitude("1000 ft MSL", upper=True), 304.8)
        self.assertAlmostEqual(parse_altitude("1000", upper=True), 304.8)  # sin unidad: pies
        self.assertAlmostEqual(parse_altitude("1500m AMSL", upper=True), 1500.0)

    def test_flight_level(self):
        self.assertAlmostEqual(parse_altitude("FL145", upper=True), feet_to_meters(14500))
        self.assertAlmostEqual(parse_altitude("FL 95", upper=True), feet_to_meters(9500))

    def test_unsupported(self):
        for text, upper in (("UNL", True), ("1000ft AGL", True), ("500m AGL", False), ("GND", True),
                            ("", True), ("alto", True), ("-100m", False)):
            with self.subTest(text=text), self.assertRaises(OpenAirError):
                parse_altitude(text, upper=upper)


class PointTests(SimpleTestCase):
    def test_dms_and_ddm(self):
        lat, lon = parse_point("35:06:43 S 058:43:34 W")
        self.assertAlmostEqual(lat, -35.111944, places=6)
        self.assertAlmostEqual(lon, -58.726111, places=6)
        self.assertEqual(parse_point("35:06:43S 058:43:34W"), (lat, lon))
        lat2, lon2 = parse_point("45:15.531N 014:18.333E")
        self.assertAlmostEqual(lat2, 45 + 15.531 / 60)
        self.assertAlmostEqual(lon2, 14 + 18.333 / 60)

    def test_invalid(self):
        for text in ("35:60:00 S 058:00:00 W", "91:00:00 N 000:00:00 E", "35:06:43 058:43:34",
                     "35:06:43 W 058:43:34 S", "35.5:06 S 058:43 W", "basura"):
            with self.subTest(text=text), self.assertRaises(OpenAirError):
                parse_point(text)


class FileStructureTests(SimpleTestCase):
    def zone_text(self, **replace):
        lines = {"AC": "AC R", "AN": "AN Z", "AL": "AL GND", "AH": "AH FL100", "V": "V X=35:00:00 S 058:00:00 W",
                 "DC": "DC 2.00"}
        lines.update(replace)
        return "\n".join(v for v in lines.values() if v)

    def test_inline_comments_and_ignored_commands(self):
        text = "AC R * clase\nAN Z * nombre\nAF 123.500\nAL GND\nAH 3000ft AMSL\nV D=+\nV X=35:00:00S 058:00:00W\nDC 2"
        zone = parse_openair(text)
        self.assertEqual(zone.name, "Z")
        self.assertEqual(zone.radius_nm, 2.0)

    def test_errors(self):
        cases = {
            "sin AC": "AN Z\nDC 1",
            "dos zonas": self.zone_text() + "\n" + self.zone_text(),
            "vacío": "* solo comentarios\n",
            "polígono": self.zone_text(DC="DP 35:00:00 S 058:00:00 W"),
            "sin DC": self.zone_text(DC=""),
            "DC sin centro": self.zone_text(V=""),
            "sin AN": self.zone_text(AN=""),
            "techo bajo base": self.zone_text(AL="AL 2000m", AH="AH 1000m"),
            "radio cero": self.zone_text(DC="DC 0"),
            "radio con unidad": self.zone_text(DC="DC 5km"),
            "comando raro": self.zone_text() + "\nXX algo",
        }
        for name, text in cases.items():
            with self.subTest(case=name), self.assertRaises(OpenAirError):
                parse_openair(text)

    def test_error_message_includes_line_number(self):
        with self.assertRaisesMessage(OpenAirError, "Línea 4"):
            parse_openair("AC R\nAN Z\nAL GND\nAH 1000ft AGL\n")
