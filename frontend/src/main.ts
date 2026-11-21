import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { http, setHttpHandlers } from './shared/services/http'
import { useAuthStore } from './stores/auth'
import { useUiStore } from './stores/ui'
// Police Inter des maquettes, embarquée (licence OFL) : aucun appel à un service externe.
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
import './style.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia).use(router)

const ui = useUiStore(pinia)
setHttpHandlers({
  onUnauthorized: () => {
    useAuthStore(pinia).user = null
    if (router.currentRoute.value.name !== 'login') router.push({ name: 'login' })
  },
  onStorageError: () => ui.setReadOnly(true),
})
// Bandeau « lecture seule » : état de la base signalé par l'API.
http.get('/api/health').then((r) => ui.setReadOnly(r.data?.db !== 'ok')).catch(() => ui.setReadOnly(true))

app.mount('#app')
