<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { dismissToast, live } from '../live'
import { altitude, clock, distance, heading, identification, speed } from '../format'

const router = useRouter()
const toasts = computed(() => live.alerts.filter((a) => a.toast))

function open(alert) {
  dismissToast(alert.id)
  live.selectedHex = alert.hex
  live.focusHex = alert.hex
  if (router.currentRoute.value.name !== 'map') router.push({ name: 'map' })
}
</script>

<template>
  <div
    class="toast-container position-fixed p-3 alert-toasts"
    :class="{ 'beside-sidebar': $route.name === 'map' }"
    aria-live="assertive"
  >
    <TransitionGroup name="toast-slide">
      <div
        v-for="a in toasts"
        :key="a.id"
        class="toast show border-danger border-2 shadow"
        role="alert"
        aria-atomic="true"
        @click="open(a)"
      >
        <div class="toast-header text-bg-danger">
          <i class="bi bi-exclamation-triangle-fill me-2"></i>
          <strong class="me-auto">Ingreso a {{ a.zone }}</strong>
          <small class="text-white-50">{{ clock(a.time) }}</small>
          <button
            type="button"
            class="btn-close btn-close-white ms-2"
            aria-label="Cerrar"
            @click.stop="dismissToast(a.id)"
          ></button>
        </div>
        <div class="toast-body">
          <div class="fs-6 fw-bold mb-2"><i class="bi bi-airplane-fill me-1 text-danger"></i> {{ identification(a) }}</div>
          <dl class="row small mb-1">
            <dt class="col-4 fw-normal text-body-secondary">Altitud</dt>
            <dd class="col-8 mb-1 fw-semibold">{{ altitude(a.alt_ft) }}</dd>
            <dt class="col-4 fw-normal text-body-secondary">Velocidad</dt>
            <dd class="col-8 mb-1 fw-semibold">{{ speed(a.gs) }}</dd>
            <dt class="col-4 fw-normal text-body-secondary">Rumbo</dt>
            <dd class="col-8 mb-1 fw-semibold">{{ heading(a.track) }}</dd>
            <dt class="col-4 fw-normal text-body-secondary">Distancia</dt>
            <dd class="col-8 mb-1 fw-semibold">{{ distance(a.dst) }}</dd>
          </dl>
          <div class="small text-body-secondary"><i class="bi bi-cursor me-1"></i>Clic para verla en el mapa</div>
        </div>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.alert-toasts {
  top: 56px;
  right: 0;
  z-index: 2000;
}
/* En el mapa: a la izquierda del panel lateral y del selector de capas. */
.alert-toasts.beside-sidebar {
  right: 400px;
}
.toast {
  --bs-toast-bg: var(--bs-body-bg); /* opaco: sobre el mapa el semitransparente no se lee */
  cursor: pointer;
}
.toast-slide-enter-active,
.toast-slide-leave-active {
  transition: all 0.25s ease;
}
.toast-slide-enter-from {
  opacity: 0;
  transform: translateX(30px);
}
.toast-slide-leave-to {
  opacity: 0;
}
</style>
