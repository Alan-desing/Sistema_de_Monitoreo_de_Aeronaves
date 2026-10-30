<script setup>
import L from 'leaflet'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
// Íconos de Bootstrap Icons como SVG (se pueden rotar y llevar contorno).
import planeSvg from 'bootstrap-icons/icons/airplane-fill.svg?raw'
import dotSvg from 'bootstrap-icons/icons/circle-fill.svg?raw'
import { M_PER_NM } from '../format'

const props = defineProps({
  aircraft: { type: Array, required: true },
  config: { type: Object, default: null },
  selectedHex: { type: String, default: null },
})
const emit = defineEmits(['select'])

const container = ref(null)

// Los objetos de Leaflet NO se guardan en estado reactivo de Vue.
let map = null
let zoneCircle = null
let queryCircle = null
const markers = new Map() // hex -> { marker, key, label }
let lastAreaKey = null

const BASE_LAYERS = {
  terrain: {
    name: 'Terreno (OpenTopoMap)',
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    options: {
      maxZoom: 17,
      subdomains: 'abc',
      attribution:
        'Mapa: &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">colaboradores de OpenStreetMap</a>, SRTM | Estilo: &copy; <a href="https://opentopomap.org" target="_blank" rel="noopener">OpenTopoMap</a> (CC-BY-SA)',
    },
  },
  streets: {
    name: 'Calles (OpenStreetMap)',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    options: {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">colaboradores de OpenStreetMap</a>',
    },
  },
}

function savedBaseLayer() {
  try {
    return localStorage.getItem('avion.baseLayer') || 'terrain'
  } catch {
    return 'terrain'
  }
}

function headingOf(ac) {
  return typeof ac.track === 'number' ? ac.track : typeof ac.true_heading === 'number' ? ac.true_heading : null
}

function iconKey(ac) {
  const h = headingOf(ac)
  return [h === null ? 'x' : Math.round(h), ac.inside, ac.alt_baro === 'ground', ac.hex === props.selectedHex].join('|')
}

function makeIcon(ac) {
  const h = headingOf(ac)
  const classes = ['ac-icon']
  if (ac.inside) classes.push('inside')
  if (ac.alt_baro === 'ground') classes.push('ground')
  if (ac.hex === props.selectedHex) classes.push('selected')
  // bi-airplane-fill apunta al norte: se rota según el rumbo. Sin rumbo, un punto.
  if (h === null) classes.push('no-heading')
  const shape = h === null ? dotSvg : planeSvg.replace('<svg', `<svg style="transform: rotate(${h}deg)"`)
  return L.divIcon({ className: '', html: `<div class="${classes.join(' ')}">${shape}</div>`, iconSize: [28, 28], iconAnchor: [14, 14] })
}

function labelOf(ac) {
  return ac.flight || ac.registration || ac.hex.toUpperCase()
}

function syncMarkers() {
  if (!map) return
  const seen = new Set()
  for (const ac of props.aircraft) {
    seen.add(ac.hex)
    const pos = [ac.lat, ac.lon]
    const key = iconKey(ac)
    const label = labelOf(ac)
    let entry = markers.get(ac.hex)
    if (!entry) {
      const marker = L.marker(pos, { icon: makeIcon(ac), riseOnHover: true, keyboard: false })
        .bindTooltip(label, { permanent: true, direction: 'right', offset: [12, 0], className: 'ac-label' })
        .on('click', () => emit('select', ac.hex))
        .addTo(map)
      markers.set(ac.hex, { marker, key, label })
      continue
    }
    entry.marker.setLatLng(pos)
    if (entry.key !== key) {
      entry.marker.setIcon(makeIcon(ac))
      entry.key = key
    }
    if (entry.label !== label) {
      entry.marker.setTooltipContent(label)
      entry.label = label
    }
    entry.marker.setZIndexOffset(ac.hex === props.selectedHex ? 1000 : ac.inside ? 500 : 0)
  }
  for (const [hex, entry] of markers) {
    if (!seen.has(hex)) {
      entry.marker.remove()
      markers.delete(hex)
    }
  }
}

// Brújula fija: el mapa no rota, así que el norte siempre queda arriba.
const COMPASS_SVG = `<svg viewBox="-26 -26 52 52" aria-hidden="true">
  <polygon points="0,-11 3.5,0 -3.5,0" fill="#dc3545" />
  <polygon points="0,11 3.5,0 -3.5,0" fill="#adb5bd" />
  <circle r="1.8" fill="#212529" />
  <text y="-17" class="north">N</text>
  <text x="17">E</text>
  <text y="17">S</text>
  <text x="-17">O</text>
</svg>`

const CompassControl = L.Control.extend({
  options: { position: 'topleft' },
  onAdd() {
    const div = L.DomUtil.create('div', 'leaflet-bar compass-control')
    div.title = 'Norte arriba'
    div.innerHTML = COMPASS_SVG
    // Un clic en la brújula no debe deseleccionar la aeronave.
    L.DomEvent.disableClickPropagation(div)
    return div
  },
})

// Dibuja la zona y limita la vista al área de la consulta (no es un mapa global).
function syncArea() {
  if (!map || !props.config) return
  const { zone, query_radius_nm } = props.config
  const center = L.latLng(zone.lat, zone.lon)

  if (!zoneCircle) {
    zoneCircle = L.circle(center, {
      radius: zone.radius_nm * M_PER_NM,
      color: '#dc3545',
      weight: 2.5,
      fillColor: '#dc3545',
      fillOpacity: 0.12,
      interactive: false,
    }).addTo(map)
    queryCircle = L.circle(center, {
      radius: query_radius_nm * M_PER_NM,
      // Límite del área consultada: visible sobre el terreno (ver referencia del panel).
      color: '#212529',
      weight: 2,
      opacity: 0.75,
      dashArray: '10 8',
      fill: false,
      interactive: false,
    }).addTo(map)
  } else {
    zoneCircle.setLatLng(center).setRadius(zone.radius_nm * M_PER_NM)
    queryCircle.setLatLng(center).setRadius(query_radius_nm * M_PER_NM)
  }

  const areaKey = [zone.lat, zone.lon, query_radius_nm].join(',')
  if (areaKey === lastAreaKey) return
  const first = lastAreaKey === null
  lastAreaKey = areaKey

  const area = applyViewLimits()
  map.fitBounds(area, { animate: !first })
}

// Lo que se puede ver: el área de cobertura (círculo punteado) más un margen
// chico. No tiene sentido alejarse más: fuera del círculo no hay aeronaves.
// El zoom va en saltos enteros, así que a veces la vista mínima es algo más
// grande que el área.
const COVERAGE_MARGIN = 0.15

function coverageBounds() {
  const { zone, query_radius_nm } = props.config
  const sizeM = 2 * query_radius_nm * M_PER_NM * (1 + COVERAGE_MARGIN)
  return L.latLng(zone.lat, zone.lon).toBounds(sizeM)
}

// Zoom mínimo y desplazamiento limitados al área; se recalcula al cambiar el
// radio de la consulta o el tamaño de la ventana.
function applyViewLimits() {
  if (!map || !props.config) return null
  const area = coverageBounds()
  map.setMaxBounds(area)
  // getBoundsZoom nunca devuelve menos que el minZoom vigente: sin liberarlo
  // antes, al agrandar el radio el mínimo quedaría trabado en el anterior.
  map.options.minZoom = 0
  map.setMinZoom(map.getBoundsZoom(area, false))
  return area
}

onMounted(() => {
  // Zoom entero: con zoom fraccionario Leaflet deja líneas visibles entre
  // teselas en todos los navegadores (probado en Chromium, Firefox y WebKit).
  map = L.map(container.value, {
    zoomControl: true,
    worldCopyJump: false,
    maxBoundsViscosity: 1.0,
  })
  map.attributionControl.setPrefix('<a href="https://leafletjs.com" target="_blank" rel="noopener">Leaflet</a>')
  map.attributionControl.addAttribution(
    'Aeronaves: <a href="https://adsb.fi/" target="_blank" rel="noopener">adsb.fi</a>',
  )

  const layers = {}
  for (const [id, def] of Object.entries(BASE_LAYERS)) {
    layers[def.name] = L.tileLayer(def.url, def.options)
    layers[def.name]._avionId = id
  }
  const initial = BASE_LAYERS[savedBaseLayer()] || BASE_LAYERS.terrain
  layers[initial.name].addTo(map)
  L.control.layers(layers, null, { position: 'topright' }).addTo(map)
  L.control.scale({ metric: true, imperial: false, maxWidth: 160 }).addTo(map)
  new CompassControl().addTo(map)
  map.on('baselayerchange', (e) => {
    try {
      localStorage.setItem('avion.baseLayer', e.layer._avionId)
    } catch {
      /* sin almacenamiento */
    }
  })
  map.on('click', () => emit('select', null))
  map.on('resize', applyViewLimits)

  if (props.config) syncArea()
  else map.setView([-35.11, -58.73], 9)
  syncMarkers()
})

onBeforeUnmount(() => {
  map?.remove()
  map = null
  markers.clear()
  zoneCircle = queryCircle = null
  lastAreaKey = null
})

watch(() => props.config, syncArea, { deep: true })
watch([() => props.aircraft, () => props.selectedHex], syncMarkers)

function focus(hex) {
  const entry = markers.get(hex)
  if (entry && map) map.panTo(entry.marker.getLatLng())
}

defineExpose({ focus })
</script>

<template>
  <div ref="container" class="aircraft-map" />
</template>

<style>
.aircraft-map {
  width: 100%;
  height: 100%;
  background: var(--bs-tertiary-bg);
}
/* Controles más grandes que los de Leaflet por defecto, para leerlos y tocarlos fácil. */
.aircraft-map .leaflet-control-zoom a {
  width: 40px;
  height: 40px;
  line-height: 40px;
  font-size: 26px;
}
.aircraft-map .compass-control {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #fff;
}
/* Centrada bajo el zoom: 56 px de ancho (borde incluido) contra 44 px de la barra de
   zoom, así que se corre 6 px a la izquierda del margen de 10 px de Leaflet. */
.aircraft-map .leaflet-left .compass-control {
  margin-left: 4px;
}
.compass-control svg {
  display: block;
  width: 100%;
  height: 100%;
}
.compass-control text {
  font-size: 9px;
  font-weight: 600;
  fill: var(--bs-secondary-color);
  text-anchor: middle;
  dominant-baseline: central;
}
.compass-control text.north {
  font-size: 11px;
  font-weight: 700;
  fill: #dc3545;
}
.aircraft-map .leaflet-control-scale-line {
  font-size: 14px;
  font-weight: 600;
  padding: 2px 8px;
  border-width: 3px;
  line-height: 1.4;
}
/* Pantallas chicas: la atribución ocupa todo el ancho, así que va más chica y
   la escala se sube para que no queden encimadas. */
@media (max-width: 575.98px) {
  .aircraft-map .leaflet-control-attribution {
    font-size: 10px;
    line-height: 1.3;
  }
  .aircraft-map .leaflet-bottom.leaflet-left {
    bottom: 28px;
  }
}
.ac-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.ac-icon svg {
  width: 24px;
  height: 24px;
  color: var(--bs-primary);
  stroke: #fff;
  stroke-width: 0.7px;
  paint-order: stroke fill;
  filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.45));
}
.ac-icon.no-heading svg {
  width: 12px;
  height: 12px;
  stroke-width: 1.5px;
}
.ac-icon.ground svg {
  color: var(--bs-secondary);
}
.ac-icon.inside svg {
  color: var(--bs-danger);
}
.ac-icon.selected svg {
  color: var(--bs-warning);
  stroke: #000;
  width: 28px;
  height: 28px;
}
.leaflet-tooltip.ac-label {
  background: rgba(255, 255, 255, 0.85);
  border: none;
  box-shadow: none;
  padding: 0 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--bs-dark);
}
.leaflet-tooltip.ac-label::before {
  display: none;
}
</style>
