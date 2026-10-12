<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api'
import { confirmDialog } from '../confirm'
import FormField from '../components/FormField.vue'
import { session } from '../session'

const users = ref([])
const loading = ref(true)
const loadError = ref('')
const message = ref('')

const editing = ref(null) // null = cerrado, 'new' o el usuario que se edita
const form = reactive({ username: '', first_name: '', last_name: '', role: 'user', password: '', password2: '' })
const errors = ref({})
const formError = ref('')
const saving = ref(false)

const isNew = computed(() => editing.value === 'new')
const isSelf = computed(() => !isNew.value && editing.value?.id === session.user?.id)
const roleLocked = computed(() => isSelf.value || (!isNew.value && editing.value?.is_superuser))

async function load() {
  loading.value = true
  try {
    users.value = await api('/users/')
    loadError.value = ''
  } catch (err) {
    loadError.value = err.message
  } finally {
    loading.value = false
  }
}

function openForm(user) {
  Object.assign(form, {
    username: user?.username ?? '',
    first_name: user?.first_name ?? '',
    last_name: user?.last_name ?? '',
    role: user?.role ?? 'user',
    password: '',
    password2: '',
  })
  errors.value = {}
  formError.value = ''
  message.value = ''
  editing.value = user ?? 'new'
}

function close() {
  editing.value = null
}

function validate() {
  const e = {}
  if (!form.username.trim()) e.username = 'El usuario es obligatorio.'
  if (isNew.value && !form.password) e.password = 'La contraseña es obligatoria.'
  if (form.password && form.password !== form.password2) e.password2 = 'Las contraseñas no coinciden.'
  errors.value = e
  return !Object.keys(e).length
}

async function save() {
  if (!validate()) return
  saving.value = true
  formError.value = ''
  const body = {
    username: form.username.trim(),
    first_name: form.first_name.trim(),
    last_name: form.last_name.trim(),
    role: form.role,
  }
  if (form.password) body.password = form.password
  try {
    if (isNew.value) {
      await api('/users/', { method: 'POST', body })
      message.value = `Usuario «${body.username}» creado.`
    } else {
      await api(`/users/${editing.value.id}/`, { method: 'PATCH', body })
      message.value = `Usuario «${body.username}» actualizado.`
    }
    editing.value = null
    await load()
  } catch (err) {
    errors.value = err.fieldErrors
    formError.value = Object.keys(err.fieldErrors).length ? 'Revisá los datos marcados.' : err.message
  } finally {
    saving.value = false
  }
}

async function toggleActive(user) {
  if (user.is_active) {
    const ok = await confirmDialog({
      title: 'Desactivar usuario',
      message: `¿Desactivar a «${user.username}»? No va a poder ingresar y se cerrará su sesión.`,
      confirmText: 'Desactivar',
      danger: true,
    })
    if (!ok) return
  }
  try {
    await api(`/users/${user.id}/`, { method: 'PATCH', body: { is_active: !user.is_active } })
    message.value = `Usuario «${user.username}» ${user.is_active ? 'desactivado' : 'activado'}.`
    loadError.value = ''
    await load()
  } catch (err) {
    message.value = ''
    loadError.value = `No se pudo ${user.is_active ? 'desactivar' : 'activar'}: ${err.message}`
  }
}

function lastLogin(user) {
  return user.last_login ? new Date(user.last_login).toLocaleString('es-AR') : 'nunca'
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="d-flex align-items-end justify-content-between gap-3 mb-4">
      <div>
        <h1 class="h3 mb-1"><i class="bi bi-people me-2"></i>Usuarios</h1>
        <p class="text-body-secondary mb-0">Los usuarios no se borran: se desactivan y dejan de poder ingresar.</p>
      </div>
      <button class="btn btn-primary" data-new-user @click="openForm(null)">
        <i class="bi bi-person-plus me-1"></i> Nuevo usuario
      </button>
    </div>

    <div v-if="message" class="alert alert-success d-flex align-items-center gap-2" role="status">
      <i class="bi bi-check-circle-fill"></i> {{ message }}
    </div>
    <div v-if="loadError" class="alert alert-danger d-flex align-items-center gap-2" role="alert">
      <i class="bi bi-exclamation-circle-fill"></i> {{ loadError }}
    </div>

    <div class="card shadow-sm">
      <div v-if="loading" class="card-body text-body-secondary">
        <span class="spinner-border spinner-border-sm me-2"></span> Cargando…
      </div>
      <div v-else class="table-responsive">
        <table class="table table-hover align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th>Usuario</th>
              <th>Nombre</th>
              <th>Rol</th>
              <th>Estado</th>
              <th>Último ingreso</th>
              <th class="text-end">Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id" :class="{ 'text-body-secondary': !u.is_active }" :data-user="u.username">
              <td>
                <i class="bi me-1" :class="u.is_active ? 'bi-person' : 'bi-person-slash'"></i>
                <strong>{{ u.username }}</strong>
                <span v-if="u.id === session.user?.id" class="badge text-bg-light border ms-1">vos</span>
              </td>
              <td>{{ [u.first_name, u.last_name].filter(Boolean).join(' ') || '—' }}</td>
              <td>
                <span v-if="u.role === 'admin'"><i class="bi bi-shield-lock me-1 text-primary"></i>Administrador</span>
                <span v-else><i class="bi bi-eye me-1"></i>Usuario registrado</span>
              </td>
              <td>
                <span class="badge" :class="u.is_active ? 'text-bg-success' : 'text-bg-secondary'">
                  {{ u.is_active ? 'Activo' : 'Desactivado' }}
                </span>
              </td>
              <td class="small">{{ lastLogin(u) }}</td>
              <td class="text-end text-nowrap">
                <button class="btn btn-sm btn-outline-secondary" title="Editar" @click="openForm(u)">
                  <i class="bi bi-pencil"></i> Editar
                </button>
                <button
                  v-if="u.id !== session.user?.id"
                  class="btn btn-sm ms-1"
                  :class="u.is_active ? 'btn-outline-danger' : 'btn-outline-success'"
                  @click="toggleActive(u)"
                >
                  <i class="bi" :class="u.is_active ? 'bi-person-dash' : 'bi-person-check'"></i>
                  {{ u.is_active ? 'Desactivar' : 'Activar' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Formulario de alta / edición -->
    <template v-if="editing">
      <div class="modal d-block" tabindex="-1" role="dialog" aria-modal="true" @click.self="close">
        <div class="modal-dialog modal-dialog-centered modal-lg">
          <form class="modal-content" novalidate @submit.prevent="save">
            <div class="modal-header">
              <h5 class="modal-title">
                <i class="bi me-2" :class="isNew ? 'bi-person-plus' : 'bi-pencil-square'"></i>
                {{ isNew ? 'Nuevo usuario' : `Editar «${editing.username}»` }}
              </h5>
              <button type="button" class="btn-close" aria-label="Cerrar" @click="close"></button>
            </div>
            <div class="modal-body">
              <div v-if="formError" class="alert alert-danger py-2">{{ formError }}</div>
              <div class="row g-3">
                <FormField id="u-username" v-model="form.username" class="col-md-4" label="Usuario" icon="bi-person"
                  :error="errors.username" autocomplete="off" />
                <FormField id="u-first" v-model="form.first_name" class="col-md-4" label="Nombre"
                  :error="errors.first_name" autocomplete="off" />
                <FormField id="u-last" v-model="form.last_name" class="col-md-4" label="Apellido"
                  :error="errors.last_name" autocomplete="off" />
                <div class="col-12">
                  <label for="u-role" class="form-label fw-semibold small mb-1">Rol</label>
                  <select id="u-role" v-model="form.role" class="form-select" :class="{ 'is-invalid': errors.role }" :disabled="roleLocked">
                    <option value="user">Usuario registrado (ve el mapa)</option>
                    <option value="admin">Administrador (usuarios y configuración)</option>
                  </select>
                  <div v-if="errors.role" class="invalid-feedback">{{ errors.role }}</div>
                  <div v-if="isSelf" class="form-text">No podés cambiar tu propio rol.</div>
                  <div v-else-if="roleLocked" class="form-text">Es superusuario: siempre es administrador.</div>
                </div>
                <FormField id="u-pass" v-model="form.password" class="col-md-6" type="password" autocomplete="new-password"
                  :label="isNew ? 'Contraseña' : 'Nueva contraseña'" icon="bi-key"
                  :hint="isNew ? 'Al menos 8 caracteres, distinta del usuario.' : 'Dejar vacío para no cambiarla.'"
                  :error="errors.password" />
                <FormField id="u-pass2" v-model="form.password2" class="col-md-6" type="password" autocomplete="new-password"
                  label="Repetir contraseña" icon="bi-key" :error="errors.password2" />
              </div>
            </div>
            <div class="modal-footer">
              <button class="btn btn-outline-secondary" type="button" @click="close">Cancelar</button>
              <button class="btn btn-primary" type="submit" :disabled="saving">
                <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
                <i v-else class="bi bi-check-lg me-1"></i>
                {{ saving ? 'Guardando…' : 'Guardar' }}
              </button>
            </div>
          </form>
        </div>
      </div>
      <div class="modal-backdrop show"></div>
    </template>
  </div>
</template>
