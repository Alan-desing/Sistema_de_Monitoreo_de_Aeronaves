// Diálogo de confirmación (modal de Bootstrap controlado por Vue).
//   if (await confirmDialog({ title, message, confirmText, danger: true })) { … }

import { reactive } from 'vue'

export const dialog = reactive({
  open: false,
  title: '',
  message: '',
  confirmText: 'Aceptar',
  danger: false,
  resolve: null,
})

export function confirmDialog({ title, message, confirmText = 'Aceptar', danger = false }) {
  dialog.resolve?.(false)
  return new Promise((resolve) => {
    Object.assign(dialog, { open: true, title, message, confirmText, danger, resolve })
  })
}

export function closeDialog(result) {
  const resolve = dialog.resolve
  dialog.open = false
  dialog.resolve = null
  resolve?.(result)
}
