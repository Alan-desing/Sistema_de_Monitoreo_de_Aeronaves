<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AircraftMap from '../components/AircraftMap.vue'
import { live } from '../live'
import {
  altitude,
  altitudeShort,
  clock,
  dec1,
  distance,
  flightradarUrl,
  heading,
  identification,
  int,
  speed,
} from '../format'

const mapRef = ref(null)
const listRef = ref(null)

const sorted = computed(() => [...live.aircraft].sort((a, b) => a.dst - b.dst))
const insideCount = computed(() => live.aircraft.filter((a) => a.inside).length)
const selected = computed(() => live.aircraft.find((a) => a.hex === live.selectedHex) || null)
const zone = computed(() => live.config?.zone)

// NM → km, redondeado para leer de un vistazo: "10 km", "5,5 km", "93 km".
function km(nm) {
  const value = nm * 1.852
  return value >= 20 ? int(value) : dec1(value).replace(/,0$/, '')
}

const heightRange = computed(() => {
  const { floor_m, ceiling_m } = zone.value
  return floor_m > 0 ? `de ${int(floor_m)} a ${int(ceiling_m)} m` : `hasta ${int(ceiling_m)} m`
})

function select(hex) {
  live.selectedHex = hex
  if (hex) tourTouched(hex)
}

function selectAndFocus(hex) {
  live.selectedHex = hex
  mapRef.value?.focus(hex)
}

function pick(hex) {
  selectAndFocus(hex)
  tourTouched(hex)
}

// Recorrido automático: selecciona las aeronaves de la lista una por una, igual
// que un clic en la lista. La lista se reordena por distancia en cada
// actualización, así que se recuerda cuáles ya se mostraron en esta vuelta.
const TOUR_INTERVAL_MS = 6000
const tour = ref(savedTour())
let tourTimer = null
let tourSeen = new Set()

function savedTour() {
  try {
    return localStorage.getItem('avion.tour') === 'on'
  } catch {
    return false
  }
}

function tourStep() {
  const list = sorted.value
  if (!list.length) return
  let next = list.find((ac) => !tourSeen.has(ac.hex))
  if (!next) {
    // Vuelta nueva, sin repetir la que está en pantalla.
    tourSeen = new Set()
    next = list.find((ac) => ac.hex !== live.selectedHex) || list[0]
  }
  tourSeen.add(next.hex)
  selectAndFocus(next.hex)
  nextTick(scrollListToActive)
}

// Solo desplaza la lista: en pantallas chicas la página entera se desplaza y
// scrollIntoView movería también la página, sacando el mapa de la vista.
function scrollListToActive() {
  const list = listRef.value
  const item = list?.querySelector('.active')
  if (!item) return
  const top = item.offsetTop
  const bottom = top + item.offsetHeight
  if (top < list.scrollTop) list.scrollTo({ top, behavior: 'smooth' })
  else if (bottom > list.scrollTop + list.clientHeight) {
    list.scrollTo({ top: bottom - list.clientHeight, behavior: 'smooth' })
  }
}

function startTourTimer() {
  clearInterval(tourTimer)
  tourTimer = tour.value ? setInterval(tourStep, TOUR_INTERVAL_MS) : null
}

// Si el usuario elige una aeronave a mano, el recorrido sigue desde ahí y le
// deja el intervalo completo para mirarla.
function tourTouched(hex) {
  if (!tour.value) return
  tourSeen.add(hex)
  startTourTimer()
}

watch(
  tour,
  (on) => {
    try {
      localStorage.setItem('avion.tour', on ? 'on' : 'off')
    } catch {
      /* sin almacenamiento */
    }
    tourSeen = new Set()
    if (on) tourStep()
    startTourTimer()
  },
)
// Si quedó activado de la vez anterior, arranca cuando el mapa ya existe.
onMounted(() => {
  if (tour.value) tourStep()
  startTourTimer()
})
onBeforeUnmount(() => clearInterval(tourTimer))

// Si se eligió una aeronave desde un aviso, centrar el mapa en ella.
function consumeFocus() {
  if (live.focusHex && mapRef.value) {
    mapRef.value.focus(live.focusHex)
    live.focusHex = null
  }
}
watch(() => live.focusHex, consumeFocus, { flush: 'post' })
onMounted(consumeFocus)

function positionAge(ac) {
  if (!live.status?.last_update) return ''
  const age = Math.max(0, live.status.last_update - ac.timestamp)
  return age < 2 ? 'ahora' : `hace ${int(age)} s`
}
</script>

<template>
  <div class="map-layout d-flex">
    <div class="map-pane flex-grow-1 position-relative">
      <AircraftMap
        ref="mapRef"
        :aircraft="live.aircraft"
        :config="live.config"
        :selected-hex="live.selectedHex"
        @select="select"
      />
      <div
        v-if="!live.config"
        class="position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center bg-body-tertiary bg-opacity-75 fs-5"
        style="z-index: 1000"
      >
        <span class="spinner-border spinner-border-sm me-2"></span> Conectando con el servidor…
      </div>
    </div>

    <aside class="sidebar d-flex flex-column bg-body">
      <!-- Referencia: el mismo dibujo que en el mapa y qué significa. -->
      <section v-if="zone" class="p-3 border-bottom map-legend">
        <div class="d-flex align-items-center gap-2 mb-2">
          <svg width="26" height="26" viewBox="0 0 22 22" class="flex-shrink-0" aria-hidden="true">
            <circle cx="11" cy="11" r="9" fill="rgba(220, 53, 69, 0.15)" stroke="#dc3545" stroke-width="2.5" />
          </svg>
          <div class="lh-sm">
            <div class="fw-semibold">Zona de alerta</div>
            <div class="small text-body-secondary">Radio {{ km(zone.radius_nm) }} km · {{ heightRange }}</div>
          </div>
        </div>
        <div class="d-flex align-items-center gap-2">
          <svg width="26" height="26" viewBox="0 0 22 22" class="flex-shrink-0" aria-hidden="true">
            <circle cx="11" cy="11" r="9" fill="none" stroke="#212529" stroke-width="2" stroke-dasharray="4 3" />
          </svg>
          <div class="lh-sm">
            <div class="fw-semibold">Área de cobertura</div>
            <div class="small text-body-secondary">
              Radio {{ km(live.config.query_radius_nm) }} km · fuera de esta línea no se ven aeronaves
            </div>
          </div>
        </div>
      </section>

      <section class="p-3 border-bottom">
        <h6 class="text-uppercase text-body-secondary small fw-semibold mb-2">
          <i class="bi bi-info-circle me-1"></i>Aeronave seleccionada
        </h6>
        <div v-if="selected" class="details">
          <div class="d-flex align-items-center justify-content-between gap-2 mb-2">
            <strong class="fs-6">{{ identification(selected) }}</strong>
            <span v-if="selected.inside" class="badge text-bg-danger"><i class="bi bi-exclamation-triangle-fill me-1"></i>EN LA ZONA</span>
          </div>
          <dl class="row small mb-0">
            <dt class="col-4 fw-normal text-body-secondary">Altitud</dt>
            <dd class="col-8 mb-1 fw-semibold">{{ altitude(selected.alt_baro) }}</dd>
            <dt class="col-4 fw-normal text-body-secondary">Velocidad</dt>
            <dd class="col-8 mb-1 fw-semibold">{{ speed(selected.gs) }}</dd>
            <dt class="col-4 fw-normal text-body-secondary">Rumbo</dt>
            <dd class="col-8 mb-1 fw-semibold">{{ heading(selected.track) }}</dd>
            <dt class="col-4 fw-normal text-body-secondary">Distancia</dt>
            <dd class="col-8 mb-1 fw-semibold">{{ distance(selected.dst) }} del centro</dd>
            <dt class="col-4 fw-normal text-body-secondary">Código</dt>
            <dd class="col-8 mb-1 fw-semibold">{{ selected.hex.toUpperCase() }}</dd>
            <dt class="col-4 fw-normal text-body-secondary">Posición</dt>
            <dd class="col-8 mb-0 fw-semibold">{{ positionAge(selected) }}</dd>
          </dl>
          <!-- Sin referer: Flightradar24 responde 451 a los enlaces que vienen de otro sitio. -->
          <a
            :href="flightradarUrl(selected)"
            target="_blank"
            rel="noopener noreferrer"
            class="btn btn-sm btn-outline-primary mt-2"
          >
            <i class="bi bi-box-arrow-up-right me-1"></i>Ver en Flightradar24
          </a>
        </div>
        <p v-else-if="live.selectedHex" class="small text-body-secondary mb-0">
          <i class="bi bi-eye-slash me-1"></i>La aeronave seleccionada ya no se recibe.
        </p>
        <p v-else class="small text-body-secondary mb-0">
          <i class="bi bi-hand-index me-1"></i>Hacé clic en una aeronave del mapa o de la lista.
        </p>
      </section>

      <section class="d-flex flex-column border-bottom flex-grow-1" style="min-height: 120px">
        <h6 class="d-flex align-items-center justify-content-between text-uppercase text-body-secondary small fw-semibold px-3 pt-3 mb-2">
          <span class="d-flex align-items-center gap-2">
            <span><i class="bi bi-list-ul me-1"></i>Aeronaves ({{ live.aircraft.length }})</span>
            <span v-if="insideCount" class="badge text-bg-danger">{{ insideCount }} en la zona</span>
          </span>
          <span
            class="form-check form-switch d-flex align-items-center gap-2 mb-0 ps-0"
            :title="`Muestra cada aeronave de la lista, una cada ${TOUR_INTERVAL_MS / 1000} segundos`"
          >
            <input id="tour-switch" v-model="tour" class="form-check-input float-none m-0" type="checkbox" role="switch" />
            <label for="tour-switch" class="form-check-label">Recorrer</label>
          </span>
        </h6>
        <!-- Mismos anchos que las columnas de la lista, para que queden alineados. -->
        <div class="ac-list-head d-flex align-items-center gap-2 px-3 pb-1 border-bottom text-body-secondary" aria-hidden="true">
          <span class="small fw-semibold flex-grow-1" title="Vuelo, matrícula o código de la aeronave">Identificación</span>
          <span class="small fw-semibold" style="width: 3em" title="Modelo de aeronave">Tipo</span>
          <span class="small fw-semibold text-end" style="width: 4.8em" title="Altitud en pies">Altitud</span>
          <span class="small fw-semibold text-end" style="width: 4.6em" title="Distancia al centro de la zona, en millas náuticas">Distancia</span>
        </div>
        <div ref="listRef" class="list-group list-group-flush overflow-auto position-relative ac-list tabular">
          <button
            v-for="ac in sorted"
            :key="ac.hex"
            type="button"
            class="list-group-item list-group-item-action d-flex align-items-center gap-2 py-2"
            :class="{ active: ac.hex === live.selectedHex, 'list-group-item-danger': ac.inside && ac.hex !== live.selectedHex }"
            @click="pick(ac.hex)"
          >
            <i class="bi" :class="ac.alt_baro === 'ground' ? 'bi-airplane-engines' : 'bi-airplane-fill'"></i>
            <span class="fw-semibold flex-grow-1 text-truncate">{{ ac.flight || ac.registration || ac.hex.toUpperCase() }}</span>
            <span class="small opacity-75" style="width: 3em">{{ ac.type || '' }}</span>
            <span class="small text-end text-nowrap" style="width: 4.8em">{{ altitudeShort(ac.alt_baro) }}</span>
            <span class="small text-end text-nowrap opacity-75" style="width: 4.6em">{{ dec1(ac.dst) }} NM</span>
          </button>
          <div v-if="!sorted.length" class="list-group-item small text-body-secondary empty">
            No hay aeronaves en el área.
          </div>
        </div>
      </section>

      <section v-if="live.alerts.length" class="border-bottom">
        <h6 class="text-uppercase text-body-secondary small fw-semibold px-3 pt-3 mb-2">
          <i class="bi bi-bell me-1"></i>Ingresos a la zona en esta sesión
        </h6>
        <div class="list-group list-group-flush overflow-auto alert-list tabular" style="max-height: 160px">
          <button
            v-for="a in live.alerts"
            :key="a.id"
            type="button"
            class="list-group-item list-group-item-action d-flex gap-3 align-items-baseline py-1"
            @click="pick(a.hex)"
          >
            <span class="small text-body-secondary">{{ clock(a.time) }}</span>
            <strong class="flex-grow-1">{{ a.label }}</strong>
            <span class="small">{{ altitudeShort(a.alt_ft) }}</span>
          </button>
        </div>
      </section>

      <footer class="credits px-3 py-1 mt-auto text-center text-body-secondary">
        <i class="bi bi-c-circle me-1"></i>Datos de aeronaves:
        <a href="https://adsb.fi/" target="_blank" rel="noopener">adsb.fi</a> · Mapa:
        <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>
      </footer>
    </aside>
  </div>
</template>

<style scoped>
.map-layout {
  height: 100%;
}
.map-pane {
  min-width: 0;
}
.sidebar {
  width: 400px;
  font-size: 1.0625rem;
  flex-shrink: 0;
  min-height: 0;
  border-left: var(--bs-border-width) solid var(--bs-border-color);
}
/* Pantallas chicas: el mapa arriba y el panel debajo, a todo el ancho. Se
   desplaza la página; la lista conserva su propio desplazamiento. */
@media (max-width: 991.98px) {
  .map-layout {
    flex-direction: column;
    height: auto;
  }
  .map-pane {
    flex: none;
    height: 60vh;
    height: 60svh;
    min-height: 320px;
  }
  .sidebar {
    width: 100%;
    font-size: 1rem;
    border-left: none;
    border-top: var(--bs-border-width) solid var(--bs-border-color);
  }
  .ac-list {
    max-height: 50vh;
  }
}
/* Lugar reservado para la barra de desplazamiento en los dos, así los
   encabezados no se corren cuando la lista es larga. */
.ac-list,
.ac-list-head {
  scrollbar-gutter: stable;
}
.ac-list-head {
  overflow: hidden;
}
/* Los créditos no necesitan el tamaño del resto del panel. */
.credits {
  font-size: 0.75rem;
}
</style>
