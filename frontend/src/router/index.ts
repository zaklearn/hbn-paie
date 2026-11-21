import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useContextStore } from '@/stores/context'

const routes: RouteRecordRaw[] = [
  { path: '/connexion', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('@/components/AppLayout.vue'),
    children: [
      { path: '', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
      { path: 'tresorerie', name: 'tresorerie', component: () => import('@/views/TresorerieView.vue') },
      { path: 'paie', name: 'paie', component: () => import('@/views/PaieMoisView.vue') },
      { path: 'salaries', name: 'salaries', component: () => import('@/views/SalariesView.vue') },
      { path: 'bulletins', name: 'bulletins', component: () => import('@/views/BulletinsView.vue') },
      { path: 'configuration', name: 'configuration', component: () => import('@/views/ConfigurationView.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: { name: 'dashboard' } },
]

export const router = createRouter({ history: createWebHistory('/'), routes })

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.checked) await auth.fetchMe()
  if (!to.meta.public && !auth.user) return { name: 'login', query: { suite: to.fullPath } }
  if (to.name === 'login' && auth.user) return { name: 'dashboard' }
  useContextStore().fromQuery(to.query)
  return true
})
