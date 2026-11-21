<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useContextStore } from '@/stores/context'
import { useEmployeesStore } from '@/stores/employees'
import { useUiStore } from '@/stores/ui'

const auth = useAuthStore()
const ctx = useContextStore()
const employees = useEmployeesStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()
const menuOpen = ref(false)

const MENU = [
  { name: 'dashboard', label: 'Tableau de bord', icon: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z' },
  { name: 'tresorerie', label: 'Trésorerie', icon: 'M3 7h18v12H3zM3 11h18M7 15h3' },
  { name: 'paie', label: 'Paie du mois', icon: 'M6 3h9l3 3v15H6zM9 10h6M9 14h6M9 18h4' },
  { name: 'salaries', label: 'Salariés', icon: 'M9 4.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7zM2.5 20c.8-3.5 3.4-5.5 6.5-5.5s5.7 2 6.5 5.5M16 4.5a3.5 3.5 0 0 1 0 7M18 14.8c1.8.8 3 2.6 3.5 5.2' },
  { name: 'bulletins', label: 'Bulletins & exports', icon: 'M4 4h16v16H4zM8 16v-5M12 16V8M16 16v-3' },
  { name: 'configuration', label: 'Configuration', icon: 'M12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6zM12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1' },
]

const search = ref('')
const options = computed(() => employees.list.map((e) => ({ value: `${e.matricule} · ${e.nom} ${e.prenom}`.trim(), matricule: e.matricule })))
const current = computed(() => employees.byMatricule(ctx.salarie))

function go(delta: number) { ctx.shift(delta); syncUrl() }
function syncUrl() { router.replace({ query: { ...route.query, ...ctx.query, ...(ctx.salarie ? {} : { salarie: undefined }) } }) }
function pickEmployee() {
  const q = search.value.trim().toLowerCase()
  if (!q) { ctx.setSalarie(''); syncUrl(); return }
  const hit = options.value.find((o) => o.value.toLowerCase() === q)
    ?? options.value.find((o) => o.value.toLowerCase().includes(q))
  if (hit) { ctx.setSalarie(hit.matricule); search.value = hit.value; syncUrl() }
}
function clearEmployee() { search.value = ''; ctx.setSalarie(''); syncUrl() }
async function logout() { await auth.logout(); router.push({ name: 'login' }) }

onMounted(async () => {
  await employees.load()
  if (current.value) search.value = `${current.value.matricule} · ${current.value.nom} ${current.value.prenom}`.trim()
})
</script>

<template>
  <div class="flex min-h-screen flex-col bg-fond md:flex-row">
    <nav aria-label="Menu principal"
         class="flex flex-col gap-1 bg-menu px-3 py-3 md:min-h-screen md:w-[232px] md:flex-none md:py-5">
      <div class="flex items-center gap-2.5 px-3 md:pb-5">
        <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-sm font-bold text-menu">HP</div>
        <div class="text-base font-semibold text-white">HBN Paie</div>
        <button type="button" class="ml-auto min-h-cible px-3 text-menu-texte md:hidden" aria-label="Ouvrir le menu"
                :aria-expanded="menuOpen" @click="menuOpen = !menuOpen">☰</button>
      </div>
      <div :class="['flex-col gap-1 md:flex md:flex-1', menuOpen ? 'flex' : 'hidden']">
        <RouterLink v-for="m in MENU" :key="m.name" :to="{ name: m.name, query: ctx.query }"
                    class="flex min-h-cible items-center gap-2.5 rounded-lg px-3 text-sm text-menu-texte no-underline hover:bg-menu-survol hover:text-white"
                    active-class="!bg-primaire !text-white" :data-testid="`menu-${m.name}`" @click="menuOpen = false">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path :d="m.icon" /></svg>
          {{ m.label }}
        </RouterLink>
        <div class="mt-auto flex items-center gap-2 border-t border-[#2A3A60] px-3 pt-4 text-[13px] text-menu-texte">
          <span data-testid="role">{{ auth.roleLabel }}</span>
          <button type="button" class="ml-auto min-h-cible px-2 text-menu-texte underline hover:text-white" @click="logout">Déconnexion</button>
        </div>
      </div>
    </nav>
    <main class="flex min-w-0 flex-1 flex-col">
      <header class="flex flex-wrap items-center gap-3 border-b border-bordure bg-white px-4 py-3.5 md:px-8">
        <div class="flex items-center gap-1">
          <button type="button" aria-label="Mois précédent" class="h-11 w-11 rounded-lg border border-champ bg-white text-lg" @click="go(-1)">‹</button>
          <div class="min-w-[160px] text-center text-[15px] font-semibold" data-testid="periode">{{ ctx.label }}</div>
          <button type="button" aria-label="Mois suivant" class="h-11 w-11 rounded-lg border border-champ bg-white text-lg" @click="go(1)">›</button>
        </div>
        <label class="flex h-11 max-w-[420px] flex-[1_1_260px] items-center gap-2 rounded-lg border border-champ px-3 text-sm text-attenue">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></svg>
          <span class="sr-only">Rechercher un salarié</span>
          <input v-model="search" list="salaries-liste" placeholder="Rechercher un salarié (nom, matricule)"
                 class="flex-1 border-0 bg-transparent text-encre outline-none" data-testid="recherche-salarie"
                 @change="pickEmployee" @keydown.enter.prevent="pickEmployee">
          <datalist id="salaries-liste"><option v-for="o in options" :key="o.matricule" :value="o.value" /></datalist>
          <button v-if="ctx.salarie" type="button" class="min-h-cible px-1 text-attenue" aria-label="Tous les salariés" @click="clearEmployee">✕</button>
        </label>
      </header>
      <div v-if="ui.readOnly" role="alert" class="bg-[#FDE7E5] px-4 py-2 text-sm text-[#8E1B12] md:px-8">
        Lecture seule : la base de données ne répond pas. Les modifications sont suspendues ; réessayez dans un instant.
      </div>
      <div class="mx-auto w-full max-w-[1240px] px-4 py-6 md:px-8"><RouterView /></div>
    </main>
    <div class="fixed bottom-4 right-4 z-50 flex max-w-sm flex-col gap-2" aria-live="polite">
      <div v-for="t in ui.toasts" :key="t.id"
           :class="['rounded-lg px-4 py-3 text-sm shadow', t.kind === 'erreur' ? 'bg-[#FDE7E5] text-[#8E1B12]' : t.kind === 'info' ? 'bg-info-fond text-info-texte' : 'bg-[#E3F4E8] text-[#14532D]']">
        {{ t.text }}
      </div>
    </div>
  </div>
</template>
