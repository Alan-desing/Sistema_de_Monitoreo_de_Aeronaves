"""Zona de alerta: cilindro vertical centrado en el punto de consulta.

La consulta a adsb.fi siempre se centra en el centro de la zona, así que la
distancia horizontal es directamente ``dst`` (NM). Las alturas de la zona se
configuran en metros y ``alt_baro`` llega en pies: se compara en pies.
"""

from dataclasses import asdict, dataclass

METERS_PER_FOOT = 0.3048


def meters_to_feet(meters):
    return meters / METERS_PER_FOOT


def feet_to_meters(feet):
    return feet * METERS_PER_FOOT


@dataclass(frozen=True)
class Zone:
    name: str
    lat: float
    lon: float
    radius_nm: float
    floor_m: float  # 0 = superficie, sin límite inferior
    ceiling_m: float

    @classmethod
    def from_config(cls, config):
        return cls(
            name=config.zone_name,
            lat=config.zone_lat,
            lon=config.zone_lon,
            radius_nm=config.zone_radius_nm,
            floor_m=config.zone_floor_m,
            ceiling_m=config.zone_ceiling_m,
        )

    @property
    def is_surface(self):
        return self.floor_m <= 0

    @property
    def floor_ft(self):
        return meters_to_feet(self.floor_m)

    @property
    def ceiling_ft(self):
        return meters_to_feet(self.ceiling_m)

    def contains(self, aircraft):
        """True si la aeronave está dentro del cilindro.

        - Horizontal: ``dst`` estrictamente menor que el radio.
        - Vertical: altitud estrictamente menor que el techo y, si la base no
          es superficie, mayor o igual que la base. Con base en superficie no
          hay límite inferior (la altitud puede ser negativa).
        - ``alt_baro`` no numérico ("ground" o ausente) nunca está dentro.
        """
        dst = aircraft.dst
        if dst is None or not dst < self.radius_nm:
            return False
        alt = aircraft.alt_baro
        if isinstance(alt, bool) or not isinstance(alt, (int, float)):
            return False
        if not alt < self.ceiling_ft:
            return False
        if not self.is_surface and not alt >= self.floor_ft:
            return False
        return True

    def to_dict(self):
        return asdict(self)
