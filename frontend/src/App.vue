<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AlertToasts from './components/AlertToasts.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import { connectLive, disconnectLive, live, setSound } from './live'
import { displayName, logout, session } from './session'
import { clock } from './format'

const router = useRouter()
const route = useRoute()

// Menú plegable en pantallas chicas; se cierra al cambiar de página.
const menuOpen = ref(false)
watch(() => route.fullPath, () => (menuOpen.value = false))

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
    <nav v-if="session.user" class="navbar navbar-expand-lg navbar-dark bg-dark px-3 py-2 flex-shrink-0">
      <RouterLink class="navbar-brand d-flex align-items-center gap-2 fs-6 fw-semibold me-auto me-lg-3" to="/">
        <i class="bi bi-airplane-fill text-primary"></i> Monitor de aeronaves
      </RouterLink>

      <!-- En pantallas chicas el estado de la conexión queda siempre a la vista, junto al botón del menú. -->
      <span
        class="badge rounded-pill d-lg-none me-2"
        :class="live.connected ? 'text-bg-success' : 'text-bg-danger'"
        :title="live.connected ? 'Recibiendo datos en tiempo real' : 'Sin conexión con el servidor: reintentando…'"
      >
        <i class="bi" :class="live.connected ? 'bi-wifi' : 'bi-wifi-off'"></i>
        <span class="visually-hidden">{{ live.connected ? 'Conectado' : 'Reconectando…' }}</span>
      </span>
      <button
        class="navbar-toggler"
        type="button"
        aria-controls="main-menu"
        :aria-expanded="menuOpen"
        aria-label="Abrir o cerrar el menú"
        @click="menuOpen = !menuOpen"
      >
        <span class="navbar-toggler-icon"></span>
      </button>

      <div id="main-menu" class="collapse navbar-collapse" :class="{ show: menuOpen }">
        <ul class="navbar-nav me-auto gap-1 mt-2 mt-lg-0">
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

        <div class="d-flex flex-wrap align-items-center gap-2 gap-lg-3 mt-2 mt-lg-0 pt-2 pt-lg-0 menu-status">
          <span
            class="badge rounded-pill d-none d-lg-inline-block"
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
          <span class="text-light d-flex align-items-center gap-2 menu-user">
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
      </div>
    </nav>

    <main class="content">
      <RouterView />
    </main>

    <AlertToasts v-if="session.user" />
    <ConfirmDialog />
  </div>
</template>
