// Conexión en tiempo real con el backend (WebSocket /ws/aircraft/).
//
// Mensajes que llegan: snapshot (al conectar), aircraft (cada ciclo),
// alert (ingreso a la zona) y config (cambio de configuración).

import { reactive } from 'vue'
import { api } from './api'
import { beep } from './sound'

const MAX_ALERTS = 50
const TOAST_SECONDS = 30

export const live = reactive({
  connected: false,
  aircraft: [],
  config: null,
  status: null,
  alerts: [], // alertas recibidas en esta sesión del navegador (solo en memoria)
  selectedHex: null,
  focusHex: null, // pedido de centrar el mapa en una aeronave (desde un aviso)
  sound: readSoundSetting(),
})

let socket = null
let wanted = false
let retries = 0
let retryTimer = null
let alertSeq = 0

function readSoundSetting() {
  try {
    return localStorage.getItem('avion.sound') !== 'off'
  } catch {
    return true
  }
}

export function setSound(enabled) {
  live.sound = enabled
  try {
    localStorage.setItem('avion.sound', enabled ? 'on' : 'off')
  } catch {
    /* sin almacenamiento: queda solo en memoria */
  }
}

export function connectLive() {
  wanted = true
  if (!socket) open()
}

export function disconnectLive() {
  wanted = false
  clearTimeout(retryTimer)
  if (socket) {
    const s = socket
    socket = null
    s.close(1000)
  }
  live.connected = false
  live.aircraft = []
  live.status = null
  live.alerts = []
  live.selectedHex = null
}

function open() {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${protocol}://${location.host}/ws/aircraft/`)
  socket = ws
  let opened = false

  ws.onopen = () => {
    opened = true
    retries = 0
    live.connected = true
  }
  ws.onmessage = (event) => {
    try {
      handle(JSON.parse(event.data))
    } catch (err) {
      console.error('Mensaje inválido del servidor', err)
    }
  }
  ws.onclose = async (event) => {
    if (socket !== ws) return // cierre pedido por nosotros
    socket = null
    live.connected = false
    if (!wanted) return
    // Un rechazo en el handshake llega como 1006 sin haber abierto; 4401 es
    // "sesión cerrada" (p. ej. usuario desactivado). En ambos casos se
    // confirma la sesión: si venció, el manejador de 401 lleva al login.
    if (!opened || event.code === 4401) {
      const stillLoggedIn = await checkSession()
      if (!stillLoggedIn || !wanted) return
    }
    retries += 1
    const delay = Math.min(30000, 1000 * 2 ** Math.min(retries - 1, 5))
    retryTimer = setTimeout(() => wanted && !socket && open(), delay)
  }
}

async function checkSession() {
  try {
    await api('/auth/me/')
    return true
  } catch (err) {
    return err.status !== 401
  }
}

function handle(message) {
  switch (message.type) {
    case 'snapshot':
      live.aircraft = message.aircraft
      live.config = message.config
      live.status = message.status
      break
    case 'aircraft':
      live.aircraft = message.aircraft
      live.status = message.status
      break
    case 'config':
      live.config = message.config
      break
    case 'alert':
      addAlert(message.alert)
      break
  }
}

function addAlert(alert) {
  const item = { ...alert, id: ++alertSeq, receivedAt: Date.now(), toast: true }
  live.alerts.unshift(item)
  live.alerts.splice(MAX_ALERTS)
  if (live.sound) beep()
  setTimeout(() => dismissToast(item.id), TOAST_SECONDS * 1000)
}

export function dismissToast(id) {
  const item = live.alerts.find((a) => a.id === id)
  if (item) item.toast = false
}
