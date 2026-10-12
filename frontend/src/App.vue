<script setup>
import { watch } from 'vue'
import { useRouter } from 'vue-router'
import AlertToasts from './components/AlertToasts.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import { connectLive, disconnectLive, live, setSound } from './live'
import { displayName, logout, session } from './session'
import { clock } from './format'

const router = useRouter()

// La conexión en tiempo real existe solo con sesión iniciada.
watch(
  () => session.user?.id,
  (id) => (id ? connectLive() : disconnectLive()),
  { immediate: true },
)

async function onLogout() {
  await logout()
  router.replace({ name: 'login' })
}
</script>

<template>
  <div class="app">
    <nav v-if="session.user" class="navbar navbar-expand navbar-dark bg-dark px-3 py-2 flex-shrink-0">
      <RouterLink class="navbar-brand d-flex align-items-center gap-2 fs-6 fw-semibold" to="/">
        <i class="bi bi-airplane-fill text-primary"></i> Monitor de aeronaves
      </RouterLink>
      <ul class="navbar-nav me-auto gap-1">
        <li class="nav-item">
          <RouterLink class="nav-link px-3 rounded" to="/"><i class="bi bi-map me-1"></i> Mapa</RouterLink>
        </li>
        <template v-if="session.user.is_admin">
          <li class="nav-item">
            <RouterLink class="nav-link px-3 rounded" to="/usuarios"><i class="bi bi-people me-1"></i> Usuarios</RouterLink>
          </li>
          <li class="nav-item">
            <RouterLink class="nav-link px-3 rounded" to="/configuracion"><i class="bi bi-gear me-1"></i> Configuración</RouterLink>
          </li>
        </template>
      </ul>

      <div class="d-flex align-items-center gap-3">
        <span
          class="badge rounded-pill"
          :class="live.connected ? 'text-bg-success' : 'text-bg-danger'"
          data-ws-status
          :title="live.connected ? 'Recibiendo datos en tiempo real' : 'Sin conexión con el servidor: reintentando…'"
        >
          <i class="bi me-1" :class="live.connected ? 'bi-wifi' : 'bi-wifi-off'"></i>
          {{ live.connected ? 'Conectado' : 'Reconectando…' }}
        </span>
        <span
          v-if="live.connected && live.status && live.status.ok === false"
          class="badge rounded-pill text-bg-warning"
          :title="live.status.error"
        >
          <i class="bi bi-exclamation-triangle-fill me-1"></i> adsb.fi sin respuesta
        </span>
        <span v-else-if="live.connected && live.status?.last_update" class="small text-white-50">
          <i class="bi bi-clock me-1"></i>Actualizado {{ clock(live.status.last_update) }}
        </span>
        <button
          class="btn btn-sm btn-outline-light"
          :title="live.sound ? 'Silenciar el aviso sonoro de alertas' : 'Activar el aviso sonoro de alertas'"
          :aria-label="live.sound ? 'Silenciar alertas' : 'Activar sonido de alertas'"
          @click="setSound(!live.sound)"
        >
          <i class="bi" :class="live.sound ? 'bi-bell-fill' : 'bi-bell-slash-fill'"></i>
        </button>
        <span class="text-light d-flex align-items-center gap-2">
          <i class="bi bi-person-circle fs-5"></i>
          <span class="lh-sm">
            {{ displayName(session.user) }}<br />
            <span class="small text-white-50">{{ session.user.is_admin ? 'Administrador' : 'Usuario' }}</span>
          </span>
        </span>
        <button class="btn btn-sm btn-outline-light" @click="onLogout">
          <i class="bi bi-box-arrow-right me-1"></i> Salir
        </button>
      </div>
    </nav>

    <main class="content">
      <RouterView />
    </main>

    <AlertToasts v-if="session.user" />
    <ConfirmDialog />
  </div>
</template>
