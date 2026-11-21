<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useContextStore } from '@/stores/context'
import { useEmployeesStore } from '@/stores/employees'
import { useUiStore } from '@/stores/ui'
import { download, errorMessage, http } from '@/shared/services/http'
import { fmtDate, fmtDh, fmtMoney } from '@/shared/format'
import type { Echeance, Employee, Issue, Payslip } from '@/shared/types'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import IssueList from '@/components/IssueList.vue'
import SidePanel from '@/components/SidePanel.vue'
import StatusBadge from '@/components/StatusBadge.vue'

type Tab = 'identite' | 'plan' | 'bulletins' | 'virements' | 'cumuls'
interface Plan { id: number; valid_from: string; s1: number; cnss: number; s2: number; s3: number; comment: string;
  created_at: string; created_by: string; total_salaire: number; total_mensuel: number }
interface Gabarit { jour: number; type: string; ordre: number; plan: 's1' | 'cnss' | 's2' | 's3' }

const auth = useAuthStore()
const ctx = useContextStore()
const employees = useEmployeesStore()
const ui = useUiStore()

const search = ref('')
const activeOnly = ref(true)
const refs = ref<{ situations_familiales: string[]; modes_paiement: string[] }>({ situations_familiales: [], modes_paiement: [] })
const list = ref<Employee[]>([])
async function loadList() {
  list.value = (await http.get<Employee[]>('/api/paie/salaries', { params: { active_only: activeOnly.value, search: search.value } })).data
}
watch([search, activeOnly], () => loadList().catch((e) => ui.notify(errorMessage(e), 'erreur')), { immediate: true })
http.get('/api/paie/referentiels').then((r) => { refs.value = r.data })

// --- Fiche -------------------------------------------------------------------------------
const open = ref<Employee | null>(null)
const tab = ref<Tab>('identite')
const plans = ref<Plan[]>([])
const gabarit = ref<Gabarit[]>([])
const slips = ref<Payslip[]>([])
const virements = ref<Echeance[]>([])
const lastClosed = computed(() => [...slips.value].filter((s) => s.status === 'cloturee')
  .sort((a, b) => b.year - a.year || b.month - a.month)[0] ?? null)
const cumulsYear = ref(ctx.year)
const cumuls = computed(() => [...slips.value].filter((s) => s.status === 'cloturee' && s.year === cumulsYear.value)
  .sort((a, b) => b.month - a.month)[0] ?? null)
const planNow = computed(() => plans.value[0] ?? null)

async function openFiche(e: Employee, t: Tab = 'identite') {
  open.value = e; tab.value = t; revealed.value = false
  const p = { employee_id: e.id }
  const [pl, ga, sl, vi] = await Promise.all([
    http.get<Plan[]>('/api/tresorerie/plans', { params: p }), http.get<Gabarit[]>('/api/tresorerie/gabarit'),
    http.get<Payslip[]>('/api/paie/paies', { params: p }), http.get<Echeance[]>('/api/tresorerie/echeances', { params: p }),
  ])
  plans.value = pl.data; gabarit.value = ga.data; slips.value = sl.data; virements.value = vi.data
}
watch(() => ctx.salarie, (m) => { const e = employees.byMatricule(m); if (e && !open.value) openFiche(e) })

// Données sensibles masquées par défaut ; affichage temporaire (30 s) pour le superadmin.
const revealed = ref(false)
let revealTimer: ReturnType<typeof setTimeout> | undefined
function reveal() { revealed.value = true; clearTimeout(revealTimer); revealTimer = setTimeout(() => { revealed.value = false }, 30_000) }
onBeforeUnmount(() => clearTimeout(revealTimer))
const masked = (v: string) => (!v ? '' : v.length <= 4 ? '•'.repeat(v.length) : '••••' + v.slice(-4))
const show = (v: string) => (revealed.value ? v : masked(v))

// --- Création / modification (contrôles de doublons d'origine côté API) ----------------------
const FIELDS: { key: keyof Employee; label: string; type?: string }[] = [
  { key: 'matricule', label: 'Matricule *' }, { key: 'nom', label: 'Nom *' }, { key: 'prenom', label: 'Prénom' },
  { key: 'date_naissance', label: 'Date de naissance', type: 'date' }, { key: 'cin', label: 'N° CIN' },
  { key: 'cnss', label: 'N° CNSS' }, { key: 'situation_familiale', label: 'Situation familiale', type: 'situation' },
  { key: 'nb_personnes_charge', label: 'Nombre de personnes à charge (déductions)', type: 'number' },
  { key: 'date_embauche', label: "Date d'embauche", type: 'date' }, { key: 'date_sortie', label: 'Date de sortie (facultatif)', type: 'date' },
  { key: 'fonction', label: 'Fonction' }, { key: 'departement', label: 'Département' }, { key: 'cimr', label: 'N° CIMR' },
  { key: 'categorie', label: 'Catégorie' }, { key: 'mode_paiement', label: 'Mode de paiement', type: 'mode' },
  { key: 'banque', label: 'Banque' }, { key: 'compte_bancaire', label: 'N° compte bancaire' }, { key: 'adresse', label: 'Adresse' },
]
const editing = ref<'create' | 'edit' | null>(null)
const draft = reactive<Record<string, unknown>>({})
const formIssues = ref<Issue[]>([])
const busy = ref(false)
function startEdit(mode: 'create' | 'edit') {
  formIssues.value = []
  const base: Record<string, unknown> = mode === 'edit' && open.value ? { ...open.value }
    : { matricule: '', nom: '', prenom: '', date_naissance: null, cin: '', cnss: '', situation_familiale: refs.value.situations_familiales[0],
        nb_personnes_charge: 0, date_embauche: null, date_sortie: null, fonction: '', departement: '', cimr: '', categorie: '',
        banque: '', compte_bancaire: '', adresse: '', mode_paiement: refs.value.modes_paiement[0], actif: true }
  Object.keys(draft).forEach((k) => delete draft[k]); Object.assign(draft, base); editing.value = mode
}
async function saveEmployee() {
  busy.value = true; formIssues.value = []
  const body = { ...draft }; delete body.id
  for (const k of ['date_naissance', 'date_embauche', 'date_sortie']) if (!body[k]) body[k] = null
  try {
    const r = editing.value === 'create' ? await http.post('/api/paie/salaries', body)
      : await http.put(`/api/paie/salaries/${open.value!.id}`, body)
    ui.notify(editing.value === 'create' ? 'Salarié créé.' : 'Fiche enregistrée.')
    editing.value = null
    await Promise.all([loadList(), employees.load(true)])
    await openFiche(r.data.employee)
  } catch (e) {
    const data = (e as { response?: { data?: { issues?: Issue[] } } }).response?.data
    if (data?.issues) formIssues.value = data.issues; else ui.notify(errorMessage(e), 'erreur')
  } finally { busy.value = false }
}
async function toggleActive(e: Employee) {
  try { await http.post(`/api/paie/salaries/${e.id}/activation`, { active: !e.actif }); ui.notify(e.actif ? 'Salarié désactivé.' : 'Salarié réactivé.'); await loadList() }
  catch (err) { ui.notify(errorMessage(err), 'erreur') }
}

// --- Plan de versement : nouvelle version datée (jamais modifiée) --------------------------------
const planForm = reactive({ valid_from: `${ctx.year}-${String(ctx.month).padStart(2, '0')}`, s1: 0, cnss: 0, s2: 0, s3: 0, comment: '' })
const planDialog = ref(false)
function startPlan() {
  const p = planNow.value
  Object.assign(planForm, { valid_from: `${ctx.year}-${String(ctx.month).padStart(2, '0')}`, s1: p?.s1 ?? 0, cnss: p?.cnss ?? 0, s2: p?.s2 ?? 0, s3: p?.s3 ?? 0, comment: '' })
  planDialog.value = true
}
async function savePlan() {
  if (!open.value) return
  busy.value = true
  try {
    await http.post('/api/tresorerie/plans', { employee_id: open.value.id, ...planForm })
    ui.notify('Nouvelle version du plan enregistrée. Les échéances déjà déclarées ne changent pas.')
    planDialog.value = false; await openFiche(open.value, 'plan')
  } catch (e) { ui.notify(errorMessage(e), 'erreur') } finally { busy.value = false }
}
async function openPdf(id: number) {
  try { await download(`/api/paie/paies/${id}/bulletin`) } catch (e) { ui.notify(errorMessage(e), 'erreur') }
}
const TABS: { id: Tab; label: string }[] = [
  { id: 'identite', label: 'Identité' }, { id: 'plan', label: 'Plan de versement' }, { id: 'bulletins', label: 'Bulletins' },
  { id: 'virements', label: 'Virements' }, { id: 'cumuls', label: 'Cumuls' },
]
const CUMUL_LABELS: [string, string][] = [['salaire_brut', 'Salaire brut'], ['cotisations_salariales', 'Cotisations salariales'],
  ['cotisations_patronales', 'Cotisations patronales'], ['net_imposable', 'Net imposable'], ['ir', 'IR']]
</script>

<template>
  <div class="flex flex-col gap-5">
    <div class="flex flex-wrap items-end gap-4">
      <div class="flex-[1_1_320px]"><h1 class="m-0 text-[26px] font-bold">Salariés</h1>
        <p class="mt-1.5 text-sm text-attenue">CIN, n° CNSS et compte bancaire masqués par défaut.</p></div>
      <button v-if="auth.isAdmin" type="button" class="btn-primaire" data-testid="nouveau-salarie" @click="startEdit('create')">Nouveau salarié</button>
    </div>
    <div class="flex flex-wrap items-center gap-4">
      <label class="etiquette min-w-[260px] flex-1">Rechercher par nom ou matricule<input v-model="search" class="champ"></label>
      <label class="flex min-h-cible items-center gap-2 text-sm"><input v-model="activeOnly" type="checkbox"> Actifs seulement</label>
    </div>
    <section class="carte overflow-x-auto">
      <table class="w-full min-w-[720px] border-collapse">
        <thead><tr><th class="th">Matricule</th><th class="th">Nom</th><th class="th">Fonction</th><th class="th">Embauche</th><th class="th">CIN</th><th class="th">N° CNSS</th><th class="th">Statut</th><th class="th"><span class="sr-only">Actions</span></th></tr></thead>
        <tbody>
          <tr v-for="e in list" :key="e.id" data-testid="ligne-salarie">
            <td class="td">{{ e.matricule }}</td><td class="td font-semibold">{{ e.nom }} {{ e.prenom }}</td><td class="td">{{ e.fonction }}</td>
            <td class="td">{{ fmtDate(e.date_embauche) }}</td><td class="td">{{ masked(e.cin) }}</td><td class="td">{{ masked(e.cnss) }}</td>
            <td class="td"><StatusBadge :status="e.actif ? 'Clôturée' : 'Brouillon'" :label="e.actif ? 'Actif' : 'Désactivé'" /></td>
            <td class="td whitespace-nowrap text-right">
              <button type="button" class="btn-lien mr-3" @click="openFiche(e)">Ouvrir</button>
              <button v-if="auth.isAdmin" type="button" class="btn-lien text-attenue" @click="toggleActive(e)">{{ e.actif ? 'Désactiver' : 'Réactiver' }}</button>
            </td>
          </tr>
          <tr v-if="!list.length"><td class="td text-attenue" colspan="8">Aucun salarié.</td></tr>
        </tbody>
      </table>
    </section>

    <SidePanel :open="!!open" :title="open ? `${open.nom} ${open.prenom}` : ''" @close="open = null">
      <template v-if="open">
        <div class="flex flex-wrap items-center gap-3">
          <div class="text-[13px] text-attenue">Matricule {{ open.matricule }} · {{ open.fonction || '—' }} · embauché le {{ fmtDate(open.date_embauche) || '—' }} · {{ open.mode_paiement.toLowerCase() }}</div>
          <StatusBadge :status="open.actif ? 'Clôturée' : 'Brouillon'" :label="open.actif ? 'Actif' : 'Désactivé'" />
          <button v-if="auth.isAdmin" type="button" class="btn-contour ml-auto" @click="startEdit('edit')">Modifier la fiche</button>
        </div>
        <div role="tablist" aria-label="Fiche salarié" class="mt-4 flex flex-wrap border-b border-bordure">
          <button v-for="t in TABS" :key="t.id" type="button" role="tab" :aria-selected="tab === t.id" :class="['onglet', tab === t.id && 'onglet-actif']" @click="tab = t.id">{{ t.label }}</button>
        </div>

        <div v-if="tab === 'identite'" class="mt-4 flex flex-col gap-3">
          <button v-if="auth.isAdmin && !revealed" type="button" class="btn-contour self-start" @click="reveal">Afficher les données sensibles (30 s)</button>
          <dl class="m-0 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            <template v-for="f in FIELDS" :key="f.key">
              <div class="flex justify-between gap-3 border-b border-ligne py-2"><dt class="text-attenue">{{ f.label.replace(' *', '') }}</dt>
                <dd class="m-0 text-right">{{ ['cin', 'cnss', 'compte_bancaire'].includes(f.key) ? show(String(open[f.key] ?? '')) : f.type === 'date' ? fmtDate(open[f.key] as string | null) : open[f.key] }}</dd></div>
            </template>
          </dl>
        </div>

        <div v-if="tab === 'plan'" class="mt-4 flex flex-col gap-4">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div><h3 class="m-0 text-base">Plan de versement mensuel</h3>
              <div class="text-[13px] text-attenue">{{ planNow ? `En vigueur depuis ${planNow.valid_from} · ${plans.length} version(s)` : 'Aucun plan : la trésorerie ne peut pas déclarer de mois pour ce salarié.' }}</div></div>
            <button v-if="auth.isAdmin" type="button" class="btn-contour" @click="startPlan">Nouvelle version datée</button>
          </div>
          <div class="overflow-x-auto"><table class="w-full border-collapse">
            <thead><tr><th class="th">Jour</th><th class="th">Échéance</th><th class="th text-right">Montant</th></tr></thead>
            <tbody>
              <tr v-for="g in gabarit" :key="g.type"><td class="td">{{ g.jour === 30 ? '30 ou dernier jour' : g.jour }}</td><td class="td">{{ g.type }}</td>
                <td class="td text-right chiffres">{{ planNow ? fmtDh(planNow[g.plan]) : '—' }}</td></tr>
              <tr v-if="planNow"><td class="td" colspan="2">Salaire net versé · total mensuel</td><td class="td text-right font-semibold chiffres">{{ fmtMoney(String(planNow.total_salaire), { decimals: false }) }} · {{ fmtDh(planNow.total_mensuel) }}</td></tr>
            </tbody></table></div>
          <p class="m-0 rounded-lg bg-fond px-3 py-2.5 text-[13px] text-attenue">Les jours, les types, le rappel J-1 et les règles de régularité sont fixes et communs à tous les salariés (gabarit en lecture seule). Seuls les montants sont propres à chaque salarié. Une nouvelle version ne modifie jamais les échéances déjà déclarées.</p>
          <section v-if="lastClosed?.result && planNow" class="carte p-4 text-sm">
            <h3 class="m-0 mb-2 text-base">Cohérence avec la paie</h3>
            <div class="text-[13px] text-attenue">Dernier bulletin clôturé : {{ String(lastClosed.month).padStart(2, '0') }}/{{ lastClosed.year }}</div>
            <div class="flex justify-between py-1"><span>Net à payer</span><strong class="chiffres">{{ fmtMoney(lastClosed.result.net_a_payer) }}</strong></div>
            <div class="flex justify-between py-1"><span>Σ versements salaire (plan)</span><strong class="chiffres">{{ fmtMoney(String(planNow.total_salaire), { decimals: false }) }}</strong></div>
            <div class="flex justify-between py-1"><span>Cotisations sal. + pat.</span><strong class="chiffres">{{ fmtMoney(lastClosed.result.total_cotisations_salariales) }} + {{ fmtMoney(lastClosed.result.total_cotisations_patronales) }}</strong></div>
            <div class="flex justify-between py-1"><span>CNSS du plan</span><strong class="chiffres">{{ fmtMoney(String(planNow.cnss), { decimals: false }) }}</strong></div>
            <p class="m-0 mt-1 text-[13px] text-attenue">Rapprochement détaillé (écarts calculés par le serveur) : écran Paie du mois.</p>
          </section>
          <div v-if="plans.length" class="overflow-x-auto"><table class="w-full border-collapse">
            <thead><tr><th class="th">Effet</th><th class="th text-right">1er</th><th class="th text-right">CNSS</th><th class="th text-right">2e</th><th class="th text-right">3e</th><th class="th">Motif</th><th class="th">Par</th></tr></thead>
            <tbody><tr v-for="p in plans" :key="p.id"><td class="td">{{ p.valid_from }}</td><td class="td text-right">{{ fmtDh(p.s1) }}</td><td class="td text-right">{{ fmtDh(p.cnss) }}</td><td class="td text-right">{{ fmtDh(p.s2) }}</td><td class="td text-right">{{ fmtDh(p.s3) }}</td><td class="td">{{ p.comment }}</td><td class="td">{{ p.created_by }}</td></tr></tbody>
          </table></div>
        </div>

        <div v-if="tab === 'bulletins'" class="mt-4 overflow-x-auto">
          <table class="w-full border-collapse">
            <thead><tr><th class="th">Période</th><th class="th">Version</th><th class="th">Statut</th><th class="th text-right">Net à payer</th><th class="th"><span class="sr-only">PDF</span></th></tr></thead>
            <tbody>
              <tr v-for="s in slips" :key="s.id"><td class="td">{{ String(s.month).padStart(2, '0') }}/{{ s.year }}</td><td class="td">v{{ s.version }}</td>
                <td class="td"><StatusBadge :status="s.status" :label="s.status_label" /></td><td class="td text-right chiffres">{{ s.result ? fmtMoney(s.result.net_a_payer) : '—' }}</td>
                <td class="td text-right"><button v-if="['cloturee', 'remplacee'].includes(s.status)" type="button" class="btn-lien" @click="openPdf(s.id)">PDF</button></td></tr>
              <tr v-if="!slips.length"><td class="td text-attenue" colspan="5">Aucune paie.</td></tr>
            </tbody>
          </table>
        </div>

        <div v-if="tab === 'virements'" class="mt-4 overflow-x-auto">
          <table class="w-full min-w-[560px] border-collapse">
            <thead><tr><th class="th">N°</th><th class="th">Échéance</th><th class="th">Type</th><th class="th text-right">Montant</th><th class="th">Statut</th><th class="th">Observations</th></tr></thead>
            <tbody>
              <tr v-for="v in virements" :key="v.id"><td class="td">{{ v.n }}</td><td class="td">{{ fmtDate(v.date_echeance) }}</td><td class="td">{{ v.type }}</td>
                <td class="td text-right chiffres">{{ fmtDh(v.montant) }}</td><td class="td"><StatusBadge :status="v.en_retard ? 'En retard' : v.statut" /></td><td class="td">{{ v.observations }}</td></tr>
              <tr v-if="!virements.length"><td class="td text-attenue" colspan="6">Aucune échéance déclarée.</td></tr>
            </tbody>
          </table>
        </div>

        <div v-if="tab === 'cumuls'" class="mt-4 flex flex-col gap-3">
          <label class="etiquette w-40">Année<input v-model.number="cumulsYear" type="number" class="champ"></label>
          <p class="m-0 text-[13px] text-attenue">Cumuls figés du dernier bulletin clôturé de l'année (paies clôturées uniquement).</p>
          <dl v-if="cumuls?.cumuls" class="m-0 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
            <div v-for="[k, l] in CUMUL_LABELS" :key="k" class="flex justify-between border-b border-ligne py-2"><dt class="text-attenue">{{ l }}</dt><dd class="m-0 chiffres">{{ fmtMoney(cumuls.cumuls[k]) }}</dd></div>
          </dl>
          <p v-else class="text-sm text-attenue">Aucune paie clôturée en {{ cumulsYear }}.</p>
        </div>
      </template>
    </SidePanel>

    <SidePanel :open="!!editing" :title="editing === 'create' ? 'Nouveau salarié' : 'Modifier la fiche'" @close="editing = null">
      <form class="flex flex-col gap-4" @submit.prevent="saveEmployee">
        <IssueList :issues="formIssues" />
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label v-for="f in FIELDS" :key="f.key" class="etiquette">{{ f.label }}
            <select v-if="f.type === 'situation'" v-model="draft[f.key]" class="champ"><option v-for="s in refs.situations_familiales" :key="s">{{ s }}</option></select>
            <select v-else-if="f.type === 'mode'" v-model="draft[f.key]" class="champ"><option v-for="s in refs.modes_paiement" :key="s">{{ s }}</option></select>
            <input v-else-if="f.type === 'date'" v-model="draft[f.key]" type="date" class="champ">
            <input v-else-if="f.type === 'number'" v-model.number="draft[f.key]" type="number" min="0" max="20" class="champ">
            <input v-else v-model="draft[f.key]" class="champ" :data-testid="`fiche-${f.key}`">
          </label>
        </div>
        <div class="flex justify-end gap-2.5"><button type="button" class="btn-contour" @click="editing = null">Annuler</button>
          <button type="submit" class="btn-primaire" :disabled="busy">Enregistrer</button></div>
      </form>
    </SidePanel>

    <ConfirmDialog :open="planDialog" title="Nouvelle version datée du plan" :busy="busy" @cancel="planDialog = false" @confirm="savePlan">
      <div class="grid grid-cols-2 gap-3">
        <label class="etiquette col-span-2">Date d'effet (AAAA-MM)<input v-model="planForm.valid_from" class="champ" pattern="\d{4}-\d{2}"></label>
        <label class="etiquette">1er versement (DH)<input v-model.number="planForm.s1" type="number" min="0" class="champ"></label>
        <label class="etiquette">CNSS (DH)<input v-model.number="planForm.cnss" type="number" min="0" class="champ"></label>
        <label class="etiquette">2e versement (DH)<input v-model.number="planForm.s2" type="number" min="0" class="champ"></label>
        <label class="etiquette">3e versement (DH)<input v-model.number="planForm.s3" type="number" min="0" class="champ"></label>
        <label class="etiquette col-span-2">Motif<input v-model="planForm.comment" class="champ"></label>
      </div>
    </ConfirmDialog>
  </div>
</template>
