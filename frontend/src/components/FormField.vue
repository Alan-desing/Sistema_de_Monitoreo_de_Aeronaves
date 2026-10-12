<script setup>
// Campo de formulario Bootstrap: etiqueta, ícono o unidad opcionales, ayuda y error.
// `class` va al contenedor (p. ej. col-md-4); el resto de los atributos
// (type, step, min, placeholder, autocomplete…) van al <input>.
import { computed, useAttrs } from 'vue'

defineOptions({ inheritAttrs: false })

const model = defineModel()
const props = defineProps({
  label: { type: String, required: true },
  id: { type: String, required: true },
  icon: { type: String, default: '' }, // clase bi-* a la izquierda
  unit: { type: String, default: '' }, // texto a la derecha (NM, m, s…)
  hint: { type: String, default: '' },
  error: { type: String, default: '' },
})

const attrs = useAttrs()
const inputAttrs = computed(() => {
  // eslint-disable-next-line no-unused-vars
  const { class: _class, style: _style, ...rest } = attrs
  return rest
})
</script>

<template>
  <div :class="attrs.class" :style="attrs.style">
    <label :for="props.id" class="form-label fw-semibold small mb-1">{{ props.label }}</label>
    <div class="input-group has-validation">
      <span v-if="props.icon" class="input-group-text"><i class="bi" :class="props.icon"></i></span>
      <input :id="props.id" v-model="model" class="form-control" :class="{ 'is-invalid': props.error }" v-bind="inputAttrs" />
      <span v-if="props.unit" class="input-group-text">{{ props.unit }}</span>
      <div v-if="props.error" class="invalid-feedback">{{ props.error }}</div>
    </div>
    <div v-if="props.hint" class="form-text">{{ props.hint }}</div>
  </div>
</template>
