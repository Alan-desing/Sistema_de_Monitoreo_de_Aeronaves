"""Estado en memoria del monitor. No se guarda nada en la base de datos.

- ``aircraft``: hex -> última posición conocida (``Aircraft``).
- ``inside``: hex -> hora (s Unix, del servidor de adsb.fi) en que ingresó a la zona.

Una alerta se genera solo en la transición de afuera a adentro. Una aeronave
que falta en una respuesta puntual conserva su estado; se purga recién cuando
su última posición es más vieja que ``max_age_s``.
"""

from dataclasses import dataclass, field

# adsb.fi deja de informar lat/lon cuando la posición tiene más de 60 s.
POSITION_MAX_AGE_S = 60.0


@dataclass
class UpdateResult:
    entered: list = field(default_factory=list)  # Aircraft que ingresaron
    exited: list = field(default_factory=list)  # hex que salieron
    purged: list = field(default_factory=list)  # hex purgados por antigüedad
    newly_incomplete: dict = field(default_factory=dict)  # hex -> campos faltantes
    all_incomplete_started: bool = False
    all_incomplete_ended: bool = False


class AircraftState:
    def __init__(self, max_age_s=POSITION_MAX_AGE_S):
        self.max_age_s = max_age_s
        self.aircraft = {}
        self.inside = {}
        self.incomplete = set()
        self.all_incomplete = False
        self.query_key = None

    def update(self, snapshot, zone, query_key):
        """Aplica una respuesta de adsb.fi. ``query_key`` = (lat, lon, radio) consultados."""
        result = UpdateResult()

        if self.query_key is not None and query_key != self.query_key:
            # Cambió el centro o el radio de la consulta: lo que no vino en la
            # nueva respuesta ya no corresponde al área consultada.
            current = {ac.hex for ac in snapshot.aircraft}
            for hex_code in [h for h in self.aircraft if h not in current]:
                self._remove(hex_code)
                result.purged.append(hex_code)
        self.query_key = query_key

        for ac in snapshot.aircraft:
            previous = self.aircraft.get(ac.hex)
            if previous is not None and previous.timestamp > ac.timestamp:
                continue  # la respuesta trae una posición más vieja que la guardada
            self.aircraft[ac.hex] = ac
            if zone.contains(ac):
                if ac.hex not in self.inside:
                    self.inside[ac.hex] = snapshot.now
                    result.entered.append(ac)
            elif self.inside.pop(ac.hex, None) is not None:
                result.exited.append(ac.hex)

        result.purged.extend(self.purge(snapshot.now))

        result.newly_incomplete = {
            h: missing for h, missing in snapshot.skipped.items() if h not in self.incomplete
        }
        self.incomplete = set(snapshot.skipped)
        if snapshot.all_incomplete != self.all_incomplete:
            result.all_incomplete_started = snapshot.all_incomplete
            result.all_incomplete_ended = not snapshot.all_incomplete
            self.all_incomplete = snapshot.all_incomplete
        return result

    def purge(self, now):
        """Quita las aeronaves cuya última posición es más vieja que ``max_age_s``."""
        stale = [h for h, ac in self.aircraft.items() if now - ac.timestamp > self.max_age_s]
        for hex_code in stale:
            self._remove(hex_code)
        return stale

    def _remove(self, hex_code):
        self.aircraft.pop(hex_code, None)
        self.inside.pop(hex_code, None)

    def payload(self):
        """Lista de aeronaves para enviar al navegador."""
        return [
            {**ac.to_dict(), "inside": hex_code in self.inside}
            for hex_code, ac in sorted(self.aircraft.items())
        ]
