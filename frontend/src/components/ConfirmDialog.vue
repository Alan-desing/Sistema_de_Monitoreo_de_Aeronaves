<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import { closeDialog, dialog } from '../confirm'

function onKey(event) {
  if (dialog.open && event.key === 'Escape') closeDialog(false)
}
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <template v-if="dialog.open">
    <div class="modal d-block" tabindex="-1" role="dialog" aria-modal="true" @click.self="closeDialog(false)">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi me-2" :class="dialog.danger ? 'bi-exclamation-triangle-fill text-danger' : 'bi-question-circle-fill text-primary'"></i>
              {{ dialog.title }}
            </h5>
            <button type="button" class="btn-close" aria-label="Cerrar" @click="closeDialog(false)"></button>
          </div>
          <div class="modal-body">{{ dialog.message }}</div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-secondary" @click="closeDialog(false)">Cancelar</button>
            <button
              type="button"
              class="btn"
              :class="dialog.danger ? 'btn-danger' : 'btn-primary'"
              data-confirm
              @click="closeDialog(true)"
            >
              {{ dialog.confirmText }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <div class="modal-backdrop show"></div>
  </template>
</template>
