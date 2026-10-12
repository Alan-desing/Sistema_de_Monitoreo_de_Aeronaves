<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api'
import { confirmDialog } from '../confirm'
import FormField from '../components/FormField.vue'
import { live } from '../live'
import { dec1, dms, int, isNumber, M_PER_FT } from '../format'

const MAX_RADIUS_NM = 250
const MIN_POLL_S = 2 // igual que MIN_POLL_INTERVAL_S del backend
const FIELDS = [
  'zone_name', 'zone_lat', 'zone_lon', 'zone_radius_nm', 'zone_floor_m', 'zone_ceiling_m',
  'poll_interval_s', 'query_radius_nm', 'telegram_chat_id',
]
const NOTICE_STYLE = {
  ok: { cls: 'alert-success', icon: 'bi-check-circle-fill' },
  error: { cls: 'alert-danger', icon: 'bi-exclamation-circle-fill' },
  info: { cls: 'alert-info', icon: 'bi-info-circle-fill' },
}

const saved = ref(null) // última configuración recibida del servidor
const form = reactive(Object.fromEntries(FIELDS.map((f) => [f, ''])))
const token = ref('') // nuevo token; vacío = conservar el guardado
const errors = ref({})
const notice = ref(null) // { kind: 'ok' | 'error' | 'info', text }
const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const fileInput = ref(null)

const dirty = computed(
  () => !!saved.value && (token.value !== '' || FIELDS.some((f) => String(form[f]) !== String(saved.value[f]))),
)
const telegramDirty = computed(
  () => !!saved.value && (token.value !== '' || String(form.telegram_chat_id) !== String(saved.value.telegram_chat_id)),
)

function fill(config) {
  saved.value = config
  for (const f of FIELDS) form[f] = config[f]
  token.value = ''
}

async function load() {
  loading.value = true
  try {
    fill(await api('/config/'))
  } catch (err) {
    notice.value = { kind: 'error', text: err.message }
  } finally {
    loading.value = false
  }
}

// Si otro administrador guarda cambios y acá no hay nada sin guardar, recargar.
watch(
  () => live.config?.updated_at,
  (updatedAt) => {
    if (saved.value && updatedAt && updatedAt !== saved.value.updated_at && !dirty.value && !saving.value) load()
  },
)

const num = (v) => (v === '' || v === null ? NaN : Number(v))

function validate() {
  const e = {}
  const lat = num(form.zone_lat)
  const lon = num(form.zone_lon)
  const radius = num(form.zone_radius_nm)
  const floor = num(form.zone_floor_m)
  const ceiling = num(form.zone_ceiling_m)
  const poll = num(form.poll_interval_s)
  const query = num(form.query_radius_nm)

  if (!String(form.zone_name).trim()) e.zone_name = 'El nombre es obligatorio.'
  if (!(lat >= -90 && lat <= 90)) e.zone_lat = 'Debe estar entre -90 y 90.'
  if (!(lon >= -180 && lon <= 180)) e.zone_lon = 'Debe estar entre -180 y 180.'
  if (!(radius > 0)) e.zone_radius_nm = 'Debe ser mayor que 0.'
  else if (radius > MAX_RADIUS_NM) e.zone_radius_nm = `No puede superar ${MAX_RADIUS_NM} NM.`
  if (!(floor >= 0)) e.zone_floor_m = 'Debe ser 0 (superficie) o mayor.'
  if (!(ceiling > 0)) e.zone_ceiling_m = 'Debe ser mayor que 0.'
  else if (floor >= 0 && !(ceiling > floor)) e.zone_ceiling_m = 'Debe ser mayor que la altura inferior.'
  if (!(Number.isInteger(poll) && poll >= MIN_POLL_S)) e.poll_interval_s = `Número entero de al menos ${MIN_POLL_S} s.`
  if (!(query > 0 && query <= MAX_RADIUS_NM)) e.query_radius_nm = `Debe estar entre 0 y ${MAX_RADIUS_NM} NM.`
  else if (radius > 0 && query < radius) e.query_radius_nm = 'No puede ser menor que el radio de la zona.'

  const chat = String(form.telegram_chat_id).trim()
  const newToken = token.value.trim()
  if (newToken && !/^\d+:[A-Za-z0-9_-]+$/.test(newToken)) {
    e.telegram_bot_token = 'Formato <número>:<clave>, como lo entrega @BotFather.'
  }
  if (chat && !/^-?\d+$/.test(chat)) e.telegram_chat_id = 'Debe ser numérico (los grupos tienen id negativo).'
  const hasToken = newToken !== '' || saved.value?.telegram_bot_token_masked
  if (chat && !hasToken) e.telegram_bot_token = 'Falta el token del bot.'
  if (!chat && newToken) e.telegram_chat_id = 'Falta el chat id del grupo.'
  if (!chat && !newToken && saved.value?.telegram_bot_token_masked) {
    e.telegram_chat_id = 'Para desactivar Telegram usá «Eliminar Telegram».'
  }

  errors.value = e
  return !Object.keys(e).length
}

function payload() {
  const body = {
    zone_name: String(form.zone_name).trim(),
    zone_lat: num(form.zone_lat),
    zone_lon: num(form.zone_lon),
    zone_radius_nm: num(form.zone_radius_nm),
    zone_floor_m: num(form.zone_floor_m),
    zone_ceiling_m: num(form.zone_ceiling_m),
    poll_interval_s: num(form.poll_interval_s),
    query_radius_nm: num(form.query_radius_nm),
    telegram_chat_id: String(form.telegram_chat_id).trim(),
  }
  if (token.value.trim()) body.telegram_bot_token = token.value.trim()
  return body
}

async function send(body, okText) {
  saving.value = true
  notice.value = null
  try {
    fill(await api('/config/', { method: 'PATCH', body }))
    errors.value = {}
    notice.value = { kind: 'ok', text: okText }
  } catch (err) {
    errors.value = err.fieldErrors
    notice.value = { kind: 'error', text: Object.keys(err.fieldErrors).length ? 'Revisá los datos marcados.' : err.message }
  } finally {
    saving.value = false
  }
}

async function save() {
  notice.value = null
  if (!validate()) {
    notice.value = { kind: 'error', text: 'Revisá los datos marcados.' }
    return
  }
  await send(payload(), 'Configuración guardada. El mapa y el monitor ya usan los valores nuevos.')
}

function discard() {
  fill(saved.value)
  errors.value = {}
  notice.value = null
}

async function clearTelegram() {
  const ok = await confirmDialog({
    title: 'Quitar Telegram',
    message: '¿Quitar el token y el chat id? Las alertas dejarán de enviarse por Telegram.',
    confirmText: 'Quitar',
    danger: true,
  })
  if (ok) await send({ telegram_bot_token: '', telegram_chat_id: '' }, 'Telegram desactivado.')
}

async function testTelegram() {
  testing.value = true
  notice.value = null
  try {
    const res = await api('/config/telegram-test/', { method: 'POST' })
    notice.value = { kind: 'ok', text: res.detail }
  } catch (err) {
    notice.value = { kind: 'error', text: err.message }
  } finally {
    testing.value = false
  }
}

async function loadOpenAir(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  const data = new FormData()
  data.append('file', file)
  notice.value = null
  try {
    const zone = await api('/config/openair/', { method: 'POST', form: data })
    Object.assign(form, zone)
    errors.value = {}
    notice.value = {
      kind: 'info',
      text: `Zona «${zone.zone_name}» cargada desde ${file.name}. Revisá los valores y tocá «Guardar» para aplicarla.`,
    }
  } catch (err) {
    notice.value = { kind: 'error', text: `No se pudo leer ${file.name}: ${err.message}` }
  }
}

const ft = (m) => (isNumber(num(m)) ? int(num(m) / M_PER_FT) : '—')
const km = (nm) => (isNumber(num(nm)) ? dec1(num(nm) * 1.852) : '—')

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="mb-4">
      <h1 class="h3 mb-1"><i class="bi bi-gear me-2"></i>Configuración</h1>
      <p class="text-body-secondary mb-0">Los cambios se aplican al guardar, sin reiniciar nada, y se ven en el mapa de todos.</p>
    </div>

    <p v-if="loading" class="text-body-secondary"><span class="spinner-border spinner-border-sm me-2"></span> Cargando…</p>

    <form v-else-if="saved" novalidate @submit.prevent="save">
      <div
        v-if="notice"
        class="alert d-flex align-items-center gap-2"
        :class="NOTICE_STYLE[notice.kind].cls"
        :data-notice="notice.kind"
        role="status"
      >
        <i class="bi" :class="NOTICE_STYLE[notice.kind].icon"></i>
        <span>{{ notice.text }}</span>
      </div>

      <!-- Zona -->
      <section class="card shadow-sm mb-3" data-section="zone">
        <div class="card-header bg-body d-flex align-items-center justify-content-between gap-3 py-3">
          <div>
            <h2 class="h5 mb-0"><i class="bi bi-bullseye text-danger me-2"></i>Zona de alerta</h2>
            <div class="small text-body-secondary">Cilindro vertical: se avisa cuando una aeronave entra.</div>
          </div>
          <input ref="fileInput" type="file" accept=".txt,.openair,.air,text/plain" hidden @change="loadOpenAir" />
          <button class="btn btn-outline-primary" type="button" @click="fileInput.click()">
            <i class="bi bi-file-earmark-arrow-up me-1"></i> Cargar archivo OpenAir…
          </button>
        </div>
        <div class="card-body">
          <div class="row g-3">
            <FormField id="zone_name" v-model="form.zone_name" class="col-12" label="Nombre" icon="bi-tag"
              maxlength="100" :error="errors.zone_name" />
            <FormField id="zone_lat" v-model="form.zone_lat" class="col-md-6 col-lg-3" label="Latitud del centro"
              icon="bi-geo-alt" type="number" step="any" min="-90" max="90" unit="°"
              :hint="dms(num(form.zone_lat), true) || 'Grados decimales (sur negativo)'" :error="errors.zone_lat" />
            <FormField id="zone_lon" v-model="form.zone_lon" class="col-md-6 col-lg-3" label="Longitud del centro"
              icon="bi-geo-alt" type="number" step="any" min="-180" max="180" unit="°"
              :hint="dms(num(form.zone_lon), false) || 'Grados decimales (oeste negativo)'" :error="errors.zone_lon" />
            <FormField id="zone_radius_nm" v-model="form.zone_radius_nm" class="col-md-4 col-lg-2" label="Radio"
              type="number" step="any" min="0" unit="NM" :hint="`≈ ${km(form.zone_radius_nm)} km`"
              :error="errors.zone_radius_nm" />
            <FormField id="zone_floor_m" v-model="form.zone_floor_m" class="col-md-4 col-lg-2" label="Altura inferior"
              type="number" step="any" min="0" unit="m"
              :hint="num(form.zone_floor_m) === 0 ? 'Superficie: sin límite inferior' : `≈ ${ft(form.zone_floor_m)} ft`"
              :error="errors.zone_floor_m" />
            <FormField id="zone_ceiling_m" v-model="form.zone_ceiling_m" class="col-md-4 col-lg-2" label="Altura superior"
              type="number" step="any" min="0" unit="m" :hint="`≈ ${ft(form.zone_ceiling_m)} ft`"
              :error="errors.zone_ceiling_m" />
          </div>
        </div>
      </section>

      <!-- Consulta -->
      <section class="card shadow-sm mb-3" data-section="query">
        <div class="card-header bg-body py-3">
          <h2 class="h5 mb-0"><i class="bi bi-broadcast me-2"></i>Consulta a adsb.fi</h2>
          <div class="small text-body-secondary">Una consulta por ciclo, centrada en la zona. El mapa muestra el área consultada.</div>
        </div>
        <div class="card-body">
          <div class="row g-3">
            <FormField id="poll_interval_s" v-model="form.poll_interval_s" class="col-md-6" label="Frecuencia de actualización"
              icon="bi-arrow-repeat" type="number" step="1" :min="MIN_POLL_S" unit="s"
              :hint="`Mínimo ${MIN_POLL_S} segundos.`" :error="errors.poll_interval_s" />
            <FormField id="query_radius_nm" v-model="form.query_radius_nm" class="col-md-6" label="Radio de la consulta y del mapa"
              icon="bi-circle" type="number" step="any" min="0" :max="MAX_RADIUS_NM" unit="NM"
              :hint="`≈ ${km(form.query_radius_nm)} km · máximo ${MAX_RADIUS_NM} NM`" :error="errors.query_radius_nm" />
          </div>
        </div>
      </section>

      <!-- Telegram -->
      <section class="card shadow-sm mb-3" data-section="telegram">
        <div class="card-header bg-body d-flex align-items-center justify-content-between gap-3 py-3">
          <div>
            <h2 class="h5 mb-0"><i class="bi bi-telegram text-primary me-2"></i>Telegram</h2>
            <div class="small text-body-secondary">
              Las alertas se envían al grupo. Para que alguien las reciba, agregalo al grupo desde Telegram.
            </div>
          </div>
          <span class="badge" :class="saved.telegram_enabled ? 'text-bg-success' : 'text-bg-secondary'">
            <i class="bi me-1" :class="saved.telegram_enabled ? 'bi-check-circle' : 'bi-dash-circle'"></i>
            {{ saved.telegram_enabled ? 'Activo' : 'No configurado' }}
          </span>
        </div>
        <div class="card-body">
          <div class="row g-3">
            <FormField id="telegram_bot_token" v-model="token" class="col-md-6" label="Token del bot" icon="bi-key"
              type="password" autocomplete="off" :placeholder="saved.telegram_bot_token_masked || 'Sin configurar'"
              :hint="saved.telegram_bot_token_masked ? `Guardado: ${saved.telegram_bot_token_masked}. Dejar vacío para conservarlo.` : 'Lo entrega @BotFather.'"
              :error="errors.telegram_bot_token" />
            <FormField id="telegram_chat_id" v-model="form.telegram_chat_id" class="col-md-6" label="Chat id del grupo"
              icon="bi-chat-dots" autocomplete="off" placeholder="-1001234567890" hint="Número negativo."
              :error="errors.telegram_chat_id" />
          </div>
          <div class="d-flex flex-wrap align-items-center gap-2 mt-3">
            <button
              class="btn btn-outline-primary"
              type="button"
              data-telegram-test
              :disabled="!saved.telegram_enabled || telegramDirty || testing"
              :title="telegramDirty ? 'Guardá los cambios antes de probar' : ''"
              @click="testTelegram"
            >
              <span v-if="testing" class="spinner-border spinner-border-sm me-1"></span>
              <i v-else class="bi bi-send me-1"></i>
              {{ testing ? 'Enviando…' : 'Enviar mensaje de prueba' }}
            </button>
            <button v-if="saved.telegram_enabled" class="btn btn-outline-danger" type="button" :disabled="saving" @click="clearTelegram">
              <i class="bi bi-trash me-1"></i> Eliminar Telegram
            </button>
            <span v-if="telegramDirty" class="small text-body-secondary">
              <i class="bi bi-info-circle me-1"></i>Guardá los cambios para poder probar.
            </span>
          </div>
        </div>
      </section>

      <div class="save-bar card shadow d-flex flex-row align-items-center gap-2 px-3 py-2">
        <span class="me-auto small" :class="dirty ? 'text-warning-emphasis fw-semibold' : 'text-body-secondary'">
          <i class="bi me-1" :class="dirty ? 'bi-pencil-fill' : 'bi-check2'"></i>
          {{ dirty ? 'Hay cambios sin guardar.' : 'Sin cambios.' }}
        </span>
        <button class="btn btn-outline-secondary" type="button" :disabled="!dirty || saving" @click="discard">
          <i class="bi bi-arrow-counterclockwise me-1"></i> Descartar
        </button>
        <button class="btn btn-primary" type="submit" :disabled="!dirty || saving">
          <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-floppy me-1"></i>
          {{ saving ? 'Guardando…' : 'Guardar' }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.save-bar {
  position: sticky;
  bottom: 0.75rem;
  z-index: 10;
}
</style>
