from monitor.adsbfi import Aircraft, Snapshot
from monitor.zone import Zone

NOW = 1_791_602_276.0
CNA = Zone(name="ALERTA CNA 10KM", lat=-35.111944, lon=-58.726111, radius_nm=5.4, floor_m=0, ceiling_m=4400)
QUERY = (CNA.lat, CNA.lon, 50.0)


def make_aircraft(hex_code="e0b390", *, dst=20.0, alt=3000, now=NOW, seen_pos=0.5, **extra):
    fields = dict(
        hex=hex_code, flight="ARG1309", registration="LV-KNP", type="B38M",
        lat=-35.0, lon=-58.7, alt_baro=alt, gs=142.0, track=126.7, true_heading=None,
        dst=dst, seen_pos=seen_pos, timestamp=now - seen_pos,
    )
    fields.update(extra)
    return Aircraft(**fields)


def make_snapshot(*aircraft, now=NOW, skipped=None):
    return Snapshot(now=now, aircraft=list(aircraft), skipped=skipped or {}, msg="No error")
