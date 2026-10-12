// Cliente de la API del backend (sesión de Django + CSRF).

export class ApiError extends Error {
  constructor(status, data) {
    super(messageFrom(data) || `Error ${status}`)
    this.status = status
    this.data = data || {}
  }

  // Errores por campo, con un solo mensaje por campo: { campo: 'mensaje' }
  get fieldErrors() {
    const out = {}
    for (const [key, value] of Object.entries(this.data)) {
      if (key === 'detail') continue
      out[key] = Array.isArray(value) ? value.join(' ') : String(value)
    }
    return out
  }
}

function messageFrom(data) {
  if (!data) return ''
  if (typeof data.detail === 'string') return data.detail
  const first = Object.values(data)[0]
  return Array.isArray(first) ? first[0] : typeof first === 'string' ? first : ''
}

function getCookie(name) {
  const match = document.cookie.split('; ').find((row) => row.startsWith(`${name}=`))
  return match ? decodeURIComponent(match.split('=')[1]) : ''
}

let onUnauthorized = () => {}

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

export async function api(path, { method = 'GET', body, form, silent401 = false } = {}) {
  const headers = { Accept: 'application/json' }
  if (method !== 'GET') headers['X-CSRFToken'] = getCookie('csrftoken')
  let payload
  if (form) {
    payload = form
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  let response
  try {
    response = await fetch(`/api${path}`, { method, headers, body: payload, credentials: 'same-origin' })
  } catch {
    throw new ApiError(0, { detail: 'No se pudo conectar con el servidor.' })
  }
  const data = response.status === 204 ? null : await response.json().catch(() => null)
  if (response.status === 401 && !silent401) onUnauthorized()
  if (!response.ok) throw new ApiError(response.status, data)
  return data
}

export async function ensureCsrf() {
  if (!getCookie('csrftoken')) await api('/auth/csrf/')
}
