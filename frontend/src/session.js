import { reactive } from 'vue'
import { api, ensureCsrf } from './api'

export const session = reactive({
  user: null, // { id, username, first_name, last_name, role, is_admin }
  checked: false,
})

export async function loadSession() {
  try {
    session.user = await api('/auth/me/', { silent401: true })
  } catch {
    session.user = null
  } finally {
    session.checked = true
  }
}

export async function login(username, password) {
  await ensureCsrf()
  session.user = await api('/auth/login/', { method: 'POST', body: { username, password } })
  return session.user
}

export async function logout() {
  try {
    await api('/auth/logout/', { method: 'POST', silent401: true })
  } finally {
    session.user = null
  }
}

export function displayName(user) {
  if (!user) return ''
  const full = [user.first_name, user.last_name].filter(Boolean).join(' ')
  return full || user.username
}
