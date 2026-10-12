import { createRouter, createWebHistory } from 'vue-router'
import { loadSession, session } from './session'
import LoginView from './views/LoginView.vue'
import MapView from './views/MapView.vue'

const router = createRouter({
  history: createWebHistory(),
  // Clase de Bootstrap para el enlace activo del menú.
  linkActiveClass: '',
  linkExactActiveClass: 'active',
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true, title: 'Ingresar' } },
    { path: '/', name: 'map', component: MapView, meta: { title: 'Mapa' } },
    {
      path: '/usuarios',
      name: 'users',
      component: () => import('./views/UsersView.vue'),
      meta: { admin: true, title: 'Usuarios' },
    },
    {
      path: '/configuracion',
      name: 'config',
      component: () => import('./views/ConfigView.vue'),
      meta: { admin: true, title: 'Configuración' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  if (!session.checked) await loadSession()
  if (to.meta.public) return session.user ? { name: 'map' } : true
  if (!session.user) {
    return { name: 'login', query: to.fullPath !== '/' ? { next: to.fullPath } : {} }
  }
  if (to.meta.admin && !session.user.is_admin) return { name: 'map' }
  return true
})

router.afterEach((to) => {
  document.title = `${to.meta.title ? `${to.meta.title} · ` : ''}Monitor de aeronaves`
})

export default router
