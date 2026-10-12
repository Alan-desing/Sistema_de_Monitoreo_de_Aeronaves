<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login } from '../session'

const route = useRoute()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await login(username.value.trim(), password.value)
    const next = typeof route.query.next === 'string' && route.query.next.startsWith('/') ? route.query.next : '/'
    router.replace(next)
  } catch (err) {
    error.value = err.status === 429 ? 'Demasiados intentos. Esperá un minuto y probá de nuevo.' : err.message
    password.value = ''
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login-page d-flex align-items-center justify-content-center p-4">
    <form class="card shadow-lg border-0 login-card" @submit.prevent="submit">
      <div class="card-body p-4 p-md-5">
        <div class="text-center mb-4">
          <i class="bi bi-airplane-fill text-primary display-5"></i>
          <h1 class="h4 mt-2 mb-1">Monitor de aeronaves</h1>
          <p class="text-body-secondary small mb-0">Acceso solo para usuarios registrados.</p>
        </div>

        <div v-if="error" class="alert alert-danger d-flex align-items-center gap-2 py-2" role="alert">
          <i class="bi bi-exclamation-circle-fill"></i>
          <span>{{ error }}</span>
        </div>

        <div class="mb-3">
          <label for="username" class="form-label">Usuario</label>
          <div class="input-group">
            <span class="input-group-text"><i class="bi bi-person"></i></span>
            <input id="username" v-model="username" class="form-control" autocomplete="username" required autofocus />
          </div>
        </div>
        <div class="mb-4">
          <label for="password" class="form-label">Contraseña</label>
          <div class="input-group">
            <span class="input-group-text"><i class="bi bi-lock"></i></span>
            <input
              id="password"
              v-model="password"
              class="form-control"
              type="password"
              autocomplete="current-password"
              required
            />
          </div>
        </div>

        <button class="btn btn-primary w-100 py-2" type="submit" :disabled="busy">
          <span v-if="busy" class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>
          <i v-else class="bi bi-box-arrow-in-right me-2"></i>
          {{ busy ? 'Ingresando…' : 'Ingresar' }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100%;
  background: linear-gradient(160deg, var(--bs-dark) 0%, #24364f 100%);
}
.login-card {
  width: 100%;
  max-width: 400px;
}
</style>
