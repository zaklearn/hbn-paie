<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useContextStore } from '@/stores/context'
import { useEmployeesStore } from '@/stores/employees'
import { useUiStore } from '@/stores/ui'
import { download, errorMessage, http } from '@/shared/services/http'
import { fmtDate, fmtDh, MOIS_FR, periodLabel } from '@/shared/format'
import type { Echeance } from '@/shared/types'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import KpiCard from '@/components/KpiCard.vue'
import StatusBadge from '@/components/StatusBadge.vue'

type Tab = 'a-venir' | 'mois' | 'rappels' | 'recap'
const TABS: { id: Tab; label: string }[] = [
  { id: 'a-venir', label: 'À venir' }, { id: 'mois', label: 'Mois' },
  { id: 'rappels', label: 'Rappels J-1' }, { id: 'recap', label: 'Récap & export' },
]
interface Recap { total_paye: number; restant_du: number; payees: number; echeances: number; avancement: number;
  regularite: Record<string, number> }

const auth = useAuthStore()
const ctx = useContextStore()
const employees = useEmployeesStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()

const tab = ref<Tab>((route.query.vue as Tab) ?? 'mois')
const monthRows = ref<Echeance[]>([])
const monthRecap = ref<Recap | null>(null)
const upcoming = ref<{ en_retard: Echeance[]; a_venir: Echeance[] }>({ en_retard: [], a_venir: [] })
const reminders = ref<Echeance[]>([])
const allRows = ref<Echeance[]>([])
const globalRecap = ref<Recap | null>(null)
const diagnostic = ref<null | { compte_rendu: Record<string, number> | null; corrections: unknown[]; erreur: string | null }>(null)

const employee = computed(() => employees.byMatricule(ctx.salarie))
const employeeId = computed(() => employee.value?.id)
const who = (e: Echeance) => { const emp = employees.byId(e.employee_id); return emp ? `${emp.nom} ${emp.prenom}`.trim() : `n° ${e.employee_id}` }
const shortType = (t: string) => t.replace('Salaire – ', '').replace(' – cotisation mensuelle', '')
const badge = (e: Echeance) => (e.en_retard ? 'En retard' : e.statut)
const detail = (e: Echeance) => {
  if (e.paye) return `le ${fmtDate(e.date_paiement).slice(0, 5)}`
  if (e.en_retard) return `échue le ${fmtDate(e.date_echeance).slice(0, 5)}`
  return `rappel le ${fmtDate(e.rappel_j1).slice(0, 5)}`
}

function setTab(t: Tab) { tab.value = t; router.replace({ query: { ...route.query, vue: t } }) }

async function loadMonth() {
  const params = { year: ctx.year, month: ctx.month, employee_id: employeeId.value }
  const [rows, recap] = await Promise.all([
    http.get<Echeance[]>('/api/tresorerie/echeances', { params }),
    http.get<Recap>('/api/tresorerie/recap', { params }),
  ])
  monthRows.value = [...rows.data].sort((a, b) => a.date_echeance.localeCompare(b.date_echeance) || a.n - b.n)
  monthRecap.value = recap.data
}
async function loadTab() {
  const params = { employee_id: employeeId.value }
  if (tab.value === 'a-venir') upcoming.value = (await http.get('/api/tresorerie/a-venir', { params })).data
  if (tab.value === 'rappels') reminders.value = (await http.get('/api/tresorerie/rappels', { params })).data
  if (tab.value === 'recap') {
    const [rows, recap] = await Promise.all([
      http.get<Echeance[]>('/api/tresorerie/echeances', { params }),
      http.get<Recap>('/api/tresorerie/recap', { params }),
    ])
    allRows.value = rows.data
    globalRecap.value = recap.data
  }
}
async function reload() {
  try { await employees.load(); await Promise.all([loadMonth(), loadTab()]) } catch (e) { ui.notify(errorMessage(e), 'erreur') }
}
watch(() => [ctx.periode, ctx.salarie, tab.value], reload, { immediate: true })

// --- Déclarer / régulariser --------------------------------------------------------------------
const declaring = ref(false)
async function declare(year = ctx.year, month = ctx.month) {
  declaring.value = true
  try {
    const r = await http.post('/api/tresorerie/declarer', { year, month, employee_id: employeeId.value ?? null })
    ui.notify(r.data.message + (r.data.ignores.length ? ` Ignorés : ${r.data.ignores.map((i: { matricule: string; raison: string }) => `${i.matricule} (${i.raison})`).join(', ')}.` : ''))
    await reload()
  } catch (e) { ui.notify(errorMessage(e), 'erreur') } finally { declaring.value = false }
}
const today = new Date()
const regYears = Array.from({ length: 5 }, (_, i) => today.getFullYear() - 2 + i)   // range(an − 2, an + 3)
const regYear = ref(today.getFullYear())
const regMonth = ref(today.getMonth() + 1)
const regRows = ref<Echeance[]>([])
async function loadRegularisation() {
  regRows.value = (await http.get<Echeance[]>('/api/tresorerie/echeances', {
    params: { year: regYear.value, month: regMonth.value, employee_id: employeeId.value } })).data
}
watch([regYear, regMonth, employeeId], () => { if (auth.isAdmin) loadRegularisation().catch(() => undefined) }, { immediate: true })

// --- Payer / dévalider (dialogues de confirmation) --------------------------------------------
const paying = ref<Echeance | null>(null)
const payDate = ref('')
const preview = ref<{ statut: string; regularite: string } | null>(null)
const busy = ref(false)
const isoToday = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
function askPay(e: Echeance) { paying.value = e; payDate.value = isoToday(); refreshPreview() }
async function refreshPreview() {
  if (!paying.value || !payDate.value) { preview.value = null; return }
  try {
    preview.value = (await http.get(`/api/tresorerie/echeances/${paying.value.id}/regularite`, { params: { date_paiement: payDate.value } })).data
  } catch { preview.value = null }
}
watch(payDate, refreshPreview)
async function confirmPay() {
  if (!paying.value) return
  busy.value = true
  try {
    await http.post(`/api/tresorerie/echeances/${paying.value.id}/payer`, { version: paying.value.version, date_paiement: payDate.value || null })
    ui.notify('Paiement enregistré.')
    paying.value = null
    await reload(); if (auth.isAdmin) await loadRegularisation()
  } catch (e) { ui.notify(errorMessage(e), 'erreur'); await reload() } finally { busy.value = false }
}
const undoing = ref<Echeance | null>(null)
async function confirmUndo() {
  if (!undoing.value) return
  busy.value = true
  try {
    await http.post(`/api/tresorerie/echeances/${undoing.value.id}/devalider`, { version: undoing.value.version })
    ui.notify('Paiement dévalidé.')
    undoing.value = null
    await reload()
  } catch (e) { ui.notify(errorMessage(e), 'erreur'); await reload() } finally { busy.value = false }
}

async function runDiagnostic() {
  if (!employeeId.value) return
  diagnostic.value = (await http.get('/api/tresorerie/reconciliation', { params: { employee_id: employeeId.value } })).data
}
const exportParams = computed(() => (employeeId.value ? { employee_id: employeeId.value } : undefined))
const nextLabel = computed(() => periodLabel(ctx.year, ctx.month).toLowerCase())
</script>

<template>
  <div class="flex flex-col gap-5">
    <div class="flex flex-wrap items-end gap-4">
      <div class="flex-[1_1_320px]">
        <h1 class="m-0 text-[26px] font-bold">Trésorerie — virements salaires et CNSS</h1>
        <p class="mt-1.5 text-sm text-attenue">Échéancier commun : le 10 (1er versement + CNSS), le 20 (2e), le 30 ou dernier jour (3e). Montants propres à chaque salarié.</p>
      </div>
      <button v-if="auth.isAdmin" type="button" class="btn-primaire" :disabled="declaring" data-testid="declarer" @click="declare()">
        Déclarer {{ nextLabel }}
      </button>
    </div>

    <div role="tablist" aria-label="Vues de la trésorerie" class="flex flex-wrap border-b border-bordure">
      <button v-for="t in TABS" :key="t.id" type="button" role="tab" :aria-selected="tab === t.id"
              :class="['onglet', tab === t.id && 'onglet-actif']" :data-testid="`onglet-${t.id}`" @click="setTab(t.id)">{{ t.label }}</button>
    </div>

    <!-- Mois -->
    <template v-if="tab === 'mois'">
      <div v-if="monthRecap" class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiCard label="Payé" :value="fmtDh(monthRecap.total_paye)" />
        <KpiCard label="Restant" :value="fmtDh(monthRecap.restant_du)" />
        <KpiCard label="Avancement" :value="`${monthRecap.avancement} %`" :progress="monthRecap.avancement" />
      </div>
      <p v-if="!monthRows.length" class="carte p-4 text-sm text-attenue">
        {{ ctx.label }} n'est pas encore déclaré{{ employee ? ` pour ${employee.nom} ${employee.prenom}` : '' }}.
        <span v-if="auth.isAdmin"> Utilisez « Déclarer {{ nextLabel }} ».</span>
      </p>
      <section v-else class="carte overflow-x-auto max-sm:hidden">
        <table class="w-full min-w-[640px] border-collapse">
          <thead><tr><th class="th">Échéance</th><th class="th">Salarié</th><th class="th">Type</th><th class="th text-right">Montant</th><th class="th">Statut</th><th class="th"><span class="sr-only">Action</span></th></tr></thead>
          <tbody>
            <tr v-for="e in monthRows" :key="e.id" data-testid="ligne-echeance">
              <td class="td whitespace-nowrap text-attenue">{{ fmtDate(e.date_echeance) }}</td>
              <td class="td whitespace-nowrap font-semibold">{{ who(e) }}</td>
              <td class="td">{{ shortType(e.type) }}</td>
              <td class="td whitespace-nowrap text-right chiffres">{{ fmtDh(e.montant) }}</td>
              <td class="td"><StatusBadge :status="badge(e)" /><div class="mt-1 text-xs text-attenue">{{ detail(e) }}</div></td>
              <td class="td text-right">
                <template v-if="auth.isAdmin">
                  <button v-if="!e.paye" type="button" class="btn min-h-9 border border-primaire bg-white text-[13px] text-primaire" data-testid="payer" @click="askPay(e)">Payer</button>
                  <button v-else type="button" class="min-h-9 px-2.5 text-[13px] text-attenue" @click="undoing = e">Dévalider</button>
                </template>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
      <div v-if="monthRows.length" class="flex flex-col gap-3 sm:hidden">
        <div v-for="e in monthRows" :key="e.id" :class="['carte flex flex-col gap-2.5 p-3.5', e.en_retard && 'border-[#F3C4BF]']">
          <div class="flex justify-between gap-2"><div><div class="text-[15px] font-semibold">{{ who(e) }}</div>
            <div class="text-[13px] text-attenue">{{ shortType(e.type) }} · {{ fmtDate(e.date_echeance).slice(0, 5) }}</div></div>
            <div class="text-base font-bold chiffres">{{ fmtDh(e.montant) }}</div></div>
          <div class="flex items-center justify-between gap-2"><StatusBadge :status="badge(e)" />
            <template v-if="auth.isAdmin">
              <button v-if="!e.paye" type="button" class="btn-primaire" @click="askPay(e)">Payer</button>
              <button v-else type="button" class="min-h-cible px-2.5 text-[13px] text-attenue" @click="undoing = e">Dévalider</button>
            </template>
          </div>
        </div>
      </div>
    </template>

    <!-- À venir : en retard puis 6 prochaines (cartes, pilotable au téléphone) -->
    <template v-if="tab === 'a-venir'">
      <div v-if="upcoming.en_retard.length" class="text-[13px] font-semibold text-danger">En retard ({{ upcoming.en_retard.length }})</div>
      <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        <div v-for="e in upcoming.en_retard" :key="e.id" class="carte flex flex-col gap-2.5 border-[#F3C4BF] p-3.5" data-testid="carte-retard">
          <div class="flex justify-between gap-2"><div><div class="text-[15px] font-semibold">{{ who(e) }}</div>
            <div class="text-[13px] text-attenue">{{ shortType(e.type) }} · échu le {{ fmtDate(e.date_echeance).slice(0, 5) }}</div></div>
            <div class="text-base font-bold chiffres">{{ fmtDh(e.montant) }}</div></div>
          <button v-if="auth.isAdmin" type="button" class="btn-primaire" @click="askPay(e)">Payer</button>
        </div>
      </div>
      <div class="mt-1 text-[13px] font-semibold text-[#3F4754]">Prochaines échéances</div>
      <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        <div v-for="e in upcoming.a_venir" :key="e.id" class="carte flex items-center justify-between gap-2 p-3.5">
          <div><div class="text-[15px] font-semibold">{{ who(e) }}</div>
            <div class="text-[13px] text-attenue">{{ shortType(e.type) }} · {{ fmtDate(e.date_echeance).slice(0, 5) }} · rappel {{ fmtDate(e.rappel_j1).slice(0, 5) }}</div></div>
          <div class="text-right"><div class="font-bold chiffres">{{ fmtDh(e.montant) }}</div>
            <button v-if="auth.isAdmin" type="button" class="btn-lien" @click="askPay(e)">Payer</button></div>
        </div>
        <p v-if="!upcoming.a_venir.length" class="text-sm text-attenue">Aucune échéance à venir.</p>
      </div>
    </template>

    <!-- Rappels J-1 -->
    <template v-if="tab === 'rappels'">
      <div class="flex justify-end"><button type="button" class="btn-contour" @click="download('/api/tresorerie/exports/rappels_salaires_cnss.ics', exportParams)">Exporter les rappels (.ics)</button></div>
      <section class="carte overflow-x-auto">
        <table class="w-full min-w-[640px] border-collapse">
          <thead><tr><th class="th">Rappel J-1</th><th class="th">Échéance</th><th class="th">Mois</th><th class="th">Salarié</th><th class="th">Type</th><th class="th text-right">Montant</th><th class="th">État</th></tr></thead>
          <tbody>
            <tr v-for="e in reminders" :key="e.id">
              <td class="td">{{ fmtDate(e.rappel_j1) }}</td><td class="td">{{ fmtDate(e.date_echeance) }}</td><td class="td">{{ e.mois }}</td>
              <td class="td font-semibold">{{ who(e) }}</td><td class="td">{{ e.type }}</td><td class="td text-right chiffres">{{ fmtDh(e.montant) }}</td>
              <td class="td"><StatusBadge :status="e.en_retard ? 'En retard' : 'À venir'" /></td>
            </tr>
            <tr v-if="!reminders.length"><td class="td text-attenue" colspan="7">Aucune échéance non payée.</td></tr>
          </tbody>
        </table>
      </section>
    </template>

    <!-- Récap & export -->
    <template v-if="tab === 'recap' && globalRecap">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Total payé" :value="fmtDh(globalRecap.total_paye)" />
        <KpiCard label="Restant dû" :value="fmtDh(globalRecap.restant_du)" />
        <KpiCard label="Échéances payées" :value="`${globalRecap.payees} / ${globalRecap.echeances}`" />
        <KpiCard label="Avancement" :value="`${globalRecap.avancement} %`" :progress="globalRecap.avancement" />
      </div>
      <p class="text-[13px] text-attenue">Régularité — à temps : {{ globalRecap.regularite['à temps'] }} · retard : {{ globalRecap.regularite.retard }} · avance : {{ globalRecap.regularite.avance }}</p>
      <div class="flex flex-wrap gap-2.5">
        <button type="button" class="btn-contour" @click="download('/api/tresorerie/exports/recap_paiements.xlsx', exportParams)">Recap (payées)</button>
        <button type="button" class="btn-contour" @click="download('/api/tresorerie/exports/base_complete.xlsx', exportParams)">Base complète</button>
        <button type="button" class="btn-contour" @click="download('/api/tresorerie/exports/rappels_salaires_cnss.ics', exportParams)">Rappels (.ics)</button>
      </div>
      <section class="carte overflow-x-auto">
        <table class="w-full min-w-[760px] border-collapse">
          <thead><tr><th class="th">N°</th><th class="th">Date échéance</th><th class="th">Mois</th><th class="th">Salarié</th><th class="th">Type</th><th class="th text-right">Montant (DH)</th><th class="th">Statut</th><th class="th">Rappel J-1</th><th class="th">Observations</th></tr></thead>
          <tbody>
            <tr v-for="e in allRows" :key="e.id">
              <td class="td">{{ e.n }}</td><td class="td">{{ fmtDate(e.date_echeance) }}</td><td class="td">{{ e.mois }}</td><td class="td">{{ who(e) }}</td>
              <td class="td">{{ e.type }}</td><td class="td text-right chiffres">{{ fmtDh(e.montant) }}</td><td class="td"><StatusBadge :status="e.statut" /></td>
              <td class="td">{{ fmtDate(e.rappel_j1) }}</td><td class="td">{{ e.observations }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>

    <!-- Régularisation (mois passés) et diagnostic : superadmin -->
    <div v-if="auth.isAdmin" class="flex flex-wrap gap-6">
      <section class="carte flex min-w-0 flex-[1_1_360px] flex-col gap-3 p-[18px]">
        <h2 class="m-0 text-base font-semibold">Régularisation / mois passé</h2>
        <div class="flex flex-wrap gap-2">
          <label class="etiquette">Année<select v-model.number="regYear" class="champ"><option v-for="y in regYears" :key="y" :value="y">{{ y }}</option></select></label>
          <label class="etiquette">Mois<select v-model.number="regMonth" class="champ"><option v-for="(m, i) in MOIS_FR" :key="m" :value="i + 1">{{ m }}</option></select></label>
        </div>
        <button v-if="!regRows.length" type="button" class="btn-contour self-start" @click="declare(regYear, regMonth)">Déclarer {{ periodLabel(regYear, regMonth) }}</button>
        <template v-else>
          <p class="m-0 text-[13px] text-attenue">« {{ periodLabel(regYear, regMonth) }} » déjà déclaré :</p>
          <button v-for="e in regRows.filter((r) => !r.paye)" :key="e.id" type="button" class="btn-contour justify-between" @click="askPay(e)">
            <span>{{ who(e) }} · {{ e.type }}</span><span class="chiffres">{{ fmtDh(e.montant) }}</span>
          </button>
          <p v-if="!regRows.some((r) => !r.paye)" class="m-0 text-[13px] text-succes">Toutes les échéances sont payées.</p>
        </template>
      </section>
      <section class="carte flex min-w-0 flex-[1_1_360px] flex-col gap-3 p-[18px]">
        <h2 class="m-0 text-base font-semibold">Diagnostic (réconciliation en simulation)</h2>
        <p class="m-0 text-[13px] text-attenue">Contrôle d'origine : schéma, doublons, rappels, montants au plan, mois, cohérence payé ⇔ date. Aucune correction n'est appliquée.</p>
        <button type="button" class="btn-contour self-start" :disabled="!employeeId" @click="runDiagnostic">{{ employeeId ? 'Lancer le diagnostic' : 'Choisissez un salarié' }}</button>
        <div v-if="diagnostic" class="text-sm">
          <p v-if="diagnostic.erreur" class="text-danger">{{ diagnostic.erreur }}</p>
          <ul v-else-if="diagnostic.compte_rendu" class="m-0 pl-4">
            <li>Total : {{ diagnostic.compte_rendu.total }} · payées : {{ diagnostic.compte_rendu.payes }} · en retard : {{ diagnostic.compte_rendu.en_retard }}</li>
            <li>Corrections proposées : {{ diagnostic.corrections.length }}</li>
          </ul>
        </div>
      </section>
    </div>

    <ConfirmDialog :open="!!paying" title="Confirmer le paiement" :busy="busy" :disabled="!payDate" @cancel="paying = null" @confirm="confirmPay">
      <template v-if="paying">
        <h2 class="m-0 text-lg">{{ who(paying) }}</h2>
        <div class="text-sm text-attenue">{{ paying.type }} · échéance {{ fmtDate(paying.date_echeance) }}</div>
        <div class="my-4 text-[28px] font-bold chiffres">{{ fmtDh(paying.montant) }}</div>
        <label class="etiquette">Date du virement<input v-model="payDate" type="date" class="champ" :max="isoToday()" data-testid="date-paiement"></label>
        <div v-if="preview" :class="['mt-3.5 rounded-lg px-3 py-2.5 text-[13px]', preview.regularite === 'retard' ? 'bg-[#FDE7E5] text-[#8E1B12]' : 'bg-[#E3F4E8] text-[#14532D]']">
          Statut calculé : <strong>{{ preview.statut }}</strong>
        </div>
      </template>
    </ConfirmDialog>
    <ConfirmDialog :open="!!undoing" title="Dévalider le paiement" confirm-label="Dévalider" :busy="busy" @cancel="undoing = null" @confirm="confirmUndo">
      <p v-if="undoing" class="m-0">Repasser <strong>{{ undoing.type }} — {{ undoing.mois }}</strong> ({{ who(undoing) }}) en « Non payé » ?</p>
    </ConfirmDialog>
  </div>
</template>
