import { createApp } from 'vue'
import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap-icons/font/bootstrap-icons.min.css'
import 'leaflet/dist/leaflet.css'
import './styles.css'
import App from './App.vue'
import router from './router'
import { setUnauthorizedHandler } from './api'
import { session } from './session'

// Cualquier 401 de la API significa que la sesión ya no es válida.
setUnauthorizedHandler(() => {
  session.user = null
  const current = router.currentRoute.value
  if (!current.meta.public) {
    router.replace({ name: 'login', query: current.fullPath !== '/' ? { next: current.fullPath } : {} })
  }
})

createApp(App).use(router).mount('#app')
