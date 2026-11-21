<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useContextStore } from '@/stores/context'
import { useEmployeesStore } from '@/stores/employees'
import { useUiStore } from '@/stores/ui'
import { download, errorMessage, http } from '@/shared/services/http'
import { fmtDh, fmtMoney, fromDecimalString, toDecimalString } from '@/shared/format'
import type { Amounts, Issue, Payslip } from '@/shared/types'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import IssueList from '@/components/IssueList.vue'
import StatusBadge from '@/components/StatusBadge.vue'

interface MonthRow { employee_id: number; matricule: string; nom: string; prenom: string; fonction: string;
  nb_personnes_charge: number; status: string; status_label: string; payslip_id: number | null; net_a_payer: string | null }
interface Rapprochement { verse_salaire: string; echeances_salaire_montant: string; net_a_payer: string | null;
  cnss_versee: string; cotisations_totales: string | null; echeances_salaire: number; echeances_salaire_payees: number }

// Libellés d'origine (feuille Saisie de paie-bulletins).
const GAINS: [keyof typeof form, string][] = [
  ['salaire_base', 'Salaire de base mensuel (MAD) *'], ['jours_declares', 'Jours déclarés'],
  ['heures_sup', 'Heures supplémentaires — montant (MAD)'], ['prime_panier', 'Prime de panier (MAD)'],
  ['indemnite_transport', 'Indemnité de transport — périmètre urbain (MAD)'],
  ['indemnite_representation', 'Indemnité de représentation (MAD)'], ['autre_prime', 'Autre prime (MAD)'],
]
const CONGES: [keyof typeof form, string][] = [['conges_reliquat', 'Reliquat de congés'], ['conges_acquis', 'Congés acquis'],
  ['conges_pris', 'Congés pris']]

const auth = useAuthStore()
const ctx = useContextStore()
const employees = useEmployeesStore()
const ui = useUiStore()
const router = useRouter()

const rows = ref<MonthRow[]>([])
const slip = ref<Payslip | null>(null)
const versions = ref<Payslip[]>([])
const prefill = ref<{ source: string; warnings: Issue[] } | null>(null)
const preview = ref<{ result: Amounts; cumuls: Amounts; parameter_set: { valid_from: string; label: string } } | null>(null)
const previewError = ref('')
const issues = ref<Issue[]>([])
const liveChecks = ref<Issue[]>([])
const checks = ref<Issue[]>([])
const rapprochement = ref<Rapprochement | null>(null)
const busy = ref(false)
const form = reactive({ salaire_base: '', jours_declares: '', heures_sup: '', prime_panier: '', indemnite_transport: '',
  indemnite_representation: '', autre_prime: '', conges_reliquat: '', conges_acquis: '', conges_pris: '' })

const selected = computed(() => rows.value.find((r) => r.matricule === ctx.salarie) ?? rows.value[0] ?? null)
const closed = computed(() => slip.value?.status === 'cloturee')
const editable = computed(() => auth.isAdmin && !closed.value)
const step = computed(() => (closed.value ? 4 : slip.value?.status === 'calculee' ? 3 : slip.value ? 2 : 1))
const errors = computed(() => checks.value.filter((i) => i.level === 'erreur'))
const warnings = computed(() => checks.value.filter((i) => i.level === 'avertissement'))
const inputs = () => Object.fromEntries(Object.entries(form).map(([k, v]) => [k, toDecimalString(v)]))

function fillForm(values: Amounts) {
  for (const k of Object.keys(form) as (keyof typeof form)[]) form[k] = fromDecimalString(values[k] ?? '0')
}

async function loadMonth() {
  rows.value = (await http.get<MonthRow[]>('/api/paie/mois', { params: { year: ctx.year, month: ctx.month } })).data
}
async function loadEmployee() {
  slip.value = null; versions.value = []; prefill.value = null; preview.value = null; issues.value = []; checks.value = []
  rapprochement.value = null
  const r = selected.value
  if (!r) return
  const p = { employee_id: r.employee_id, year: ctx.year, month: ctx.month }
  const [current, pre, rap, ver] = await Promise.all([
    http.get<Payslip | null>('/api/paie/paies/courante', { params: p }),
    http.get('/api/paie/saisie/preremplissage', { params: p }),
    http.get<Rapprochement>('/api/tresorerie/rapprochement', { params: p }),
    http.get<Payslip[]>('/api/paie/paies/versions', { params: p }),
  ])
  slip.value = current.data
  prefill.value = { source: pre.data.source, warnings: pre.data.warnings }
  rapprochement.value = rap.data
  versions.value = ver.data
  fillForm(current.data?.inputs ?? pre.data.inputs)
  if (slip.value?.status === 'calculee') checks.value = (await http.get(`/api/paie/paies/${slip.value.id}/controles`)).data.issues
}
async function reload() {
  try { await employees.load(); await loadMonth(); await loadEmployee() } catch (e) { ui.notify(errorMessage(e), 'erreur') }
}
watch(() => [ctx.periode, ctx.salarie], reload, { immediate: true })

function select(r: MonthRow) { router.replace({ query: { ...ctx.query, salarie: r.matricule } }) }

// Aperçu instantané : calculé par l'API (noyau), requête retardée de 300 ms. Aucun calcul ici (R0).
let timer: ReturnType<typeof setTimeout> | undefined
watch(form, () => {
  clearTimeout(timer)
  timer = setTimeout(async () => {
    if (!selected.value) return
    try {
      const body = { employee_id: selected.value.employee_id, year: ctx.year, month: ctx.month, inputs: inputs() }
      const [p, c] = await Promise.all([http.post('/api/paie/apercu', body), http.post('/api/paie/saisie/controle', body)])
      preview.value = p.data
      liveChecks.value = c.data.issues
      previewError.value = ''
    } catch (e) { preview.value = null; previewError.value = errorMessage(e) }
  }, 300)
}, { deep: true })
const shown = computed(() => (slip.value?.result && !editable.value ? slip.value.result : preview.value?.result) ?? null)

async function saveDraft(): Promise<number | null> {
  if (!selected.value) return null
  issues.value = []
  try {
    const r = await http.post('/api/paie/brouillons', { employee_id: selected.value.employee_id, year: ctx.year,
      month: ctx.month, inputs: inputs() })
    issues.value = r.data.issues
    return r.data.payslip.id
  } catch (e) {
    const data = (e as { response?: { data?: { issues?: Issue[] } } }).response?.data
    if (data?.issues) issues.value = data.issues; else ui.notify(errorMessage(e), 'erreur')
    return null
  }
}
async function onSave() { busy.value = true; if (await saveDraft()) { ui.notify('Brouillon enregistré.'); await reload() } busy.value = false }
async function onCalculate() {
  busy.value = true
  try {
    const id = await saveDraft()
    if (id) { await http.post(`/api/paie/paies/${id}/calcul`); ui.notify('Paie calculée.'); await reload() }
  } catch (e) { ui.notify(errorMessage(e), 'erreur') } finally { busy.value = false }
}

const closing = ref(false)
const confirmWarnings = ref(false)
const confirmClose = ref(false)
async function onClose() {
  if (!slip.value) return
  busy.value = true
  try {
    await http.post(`/api/paie/paies/${slip.value.id}/cloture`, { confirm_warnings: confirmWarnings.value })
    ui.notify('Paie clôturée, bulletin généré et archivé.')
    closing.value = false
    await reload()
  } catch (e) { ui.notify(errorMessage(e), 'erreur') } finally { busy.value = false }
}
const rectifying = ref(false)
const reason = ref('')
async function onRectify() {
  if (!slip.value) return
  busy.value = true
  try {
    await http.post(`/api/paie/paies/${slip.value.id}/rectification`, { reason: reason.value })
    ui.notify('Rectification ouverte : nouvelle version en brouillon.')
    rectifying.value = false; reason.value = ''
    await reload()
  } catch (e) { ui.notify(errorMessage(e), 'erreur') } finally { busy.value = false }
}
const deleting = ref(false)
async function onDelete() {
  if (!slip.value) return
  busy.value = true
  try { await http.delete(`/api/paie/paies/${slip.value.id}`); ui.notify('Brouillon supprimé.'); deleting.value = false; await reload() }
  catch (e) { ui.notify(errorMessage(e), 'erreur') } finally { busy.value = false }
}
async function openPdf(kind: 'pdf-provisoire' | 'bulletin', id = slip.value?.id) {
  if (!id) return
  if (kind === 'bulletin') { await download(`/api/paie/paies/${id}/bulletin`).catch((e) => ui.notify(errorMessage(e), 'erreur')); return }
  try {
    const r = await http.get(`/api/paie/paies/${id}/${kind}`, { responseType: 'blob' })
    window.open(URL.createObjectURL(r.data as Blob), '_blank')
  } catch (e) { ui.notify(errorMessage(e), 'erreur') }
}
const lines = computed(() => {
  const r = shown.value
  if (!r) return []
  return [
    ['Salaire brut', fmtMoney(r.salaire_brut)], ['Cotisations salariales', `− ${fmtMoney(r.total_cotisations_salariales)}`],
    ['Net imposable', fmtMoney(r.net_imposable)], ['IR mensuel', `− ${fmtMoney(r.ir_mensuel)}`], ['Arrondi', fmtMoney(r.arrondi)],
  ]
})
</script>

<template>
  <div class="flex flex-wrap items-start gap-6">
    <section aria-label="Salariés du mois" class="flex min-w-0 flex-[1_1_280px] flex-col gap-2.5">
      <h1 class="m-0 mb-1 text-2xl font-bold">Paie du mois</h1>
      <p class="m-0 mb-2 text-[13px] text-attenue">{{ ctx.label }} · {{ rows.length }} salarié{{ rows.length > 1 ? 's' : '' }} actif{{ rows.length > 1 ? 's' : '' }}</p>
      <button v-for="r in rows" :key="r.employee_id" type="button" data-testid="carte-paie"
              :class="['block rounded-xl bg-white p-3.5 text-left', r === selected ? 'border-2 border-primaire' : 'border border-bordure']" @click="select(r)">
        <div class="flex justify-between gap-2"><strong>{{ r.nom }} {{ r.prenom }}</strong><StatusBadge :status="r.status" :label="r.status_label" /></div>
        <div class="mt-1 text-[13px] text-attenue">{{ r.matricule }}<template v-if="r.net_a_payer"> · net {{ fmtMoney(r.net_a_payer, { decimals: false }) }} DH</template></div>
      </button>
      <p v-if="!rows.length" class="text-sm text-attenue">Aucun salarié actif sur ce mois.</p>
      <div class="px-0.5 py-1 text-xs text-attenue">Statuts : À saisir → Brouillon → Calculée → Clôturée. Une rectification crée une nouvelle version ; l'ancienne passe en « Remplacée ».</div>
    </section>

    <section v-if="selected" :aria-label="`Bulletin de ${selected.nom}`" class="carte flex min-w-0 flex-[999_1_640px] flex-col gap-[18px] p-[22px]">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 class="m-0 text-xl">{{ selected.nom }} {{ selected.prenom }} — {{ ctx.label.toLowerCase() }}</h2>
          <div class="mt-1 text-[13px] text-attenue">Matricule {{ selected.matricule }} · {{ selected.fonction || '—' }} · {{ selected.nb_personnes_charge }} personne(s) à charge<template v-if="slip"> · version {{ slip.version }}</template></div>
        </div>
        <ol aria-label="Étapes" class="m-0 flex list-none flex-wrap gap-1.5 p-0 text-[13px]">
          <li v-for="(s, i) in ['Saisie', 'Calcul', 'Contrôles', 'Clôture']" :key="s"
              :class="['rounded-full px-3 py-1.5', i + 1 === step ? 'bg-primaire font-semibold text-white' : i + 1 < step ? 'bg-[#E3F4E8] text-succes' : 'bg-ligne text-[#3F4754]']">{{ i + 1 }} {{ s }}</li>
        </ol>
      </div>
      <div v-if="slip?.replaces_id" class="rounded-lg bg-[#EFEAFB] px-3 py-2.5 text-[13px] text-[#5B3FA8]">Rectification de la version précédente (motif : {{ slip.rectification_reason }}).</div>
      <div v-if="prefill && !closed" class="rounded-lg bg-info-fond px-3 py-2.5 text-[13px] text-info-texte" data-testid="bandeau-prerempli">{{ prefill.source }}</div>
      <IssueList v-if="prefill && !closed" :issues="prefill.warnings" />
      <IssueList :issues="issues.length ? issues : editable ? liveChecks : []" data-testid="controles-saisie" />

      <div class="flex flex-wrap gap-6">
        <div class="flex min-w-0 flex-[1_1_340px] flex-col gap-3.5">
          <div class="text-[13px] font-semibold uppercase tracking-wide text-attenue">Éléments de rémunération</div>
          <div class="grid grid-cols-2 gap-3">
            <label v-for="[k, l] in GAINS" :key="k" class="etiquette">{{ l }}
              <input v-model="form[k]" inputmode="decimal" class="champ text-right chiffres" :readonly="!editable" :data-testid="`saisie-${k}`">
            </label>
          </div>
          <div class="mt-1 text-[13px] font-semibold uppercase tracking-wide text-attenue">Congés (jours)</div>
          <div class="grid grid-cols-3 gap-3">
            <label v-for="[k, l] in CONGES" :key="k" class="etiquette">{{ l }}
              <input v-model="form[k]" inputmode="decimal" class="champ text-right chiffres" :readonly="!editable">
            </label>
          </div>
        </div>
        <div class="flex min-w-0 flex-[1_1_280px] flex-col gap-3.5">
          <div class="rounded-[10px] bg-[#F7F8FA] p-4" data-testid="apercu">
            <div class="mb-1.5 text-[13px] font-semibold uppercase tracking-wide text-attenue">{{ closed ? 'Bulletin clôturé' : 'Aperçu instantané' }}</div>
            <p v-if="previewError && !shown" class="text-[13px] text-danger">{{ previewError }}</p>
            <div v-for="[l, v] in lines" :key="l" class="flex justify-between gap-3 border-b border-ligne py-[7px] text-sm chiffres"><span>{{ l }}</span><span>{{ v }}</span></div>
            <div v-if="shown" class="flex justify-between gap-3 pt-2.5 text-lg font-bold chiffres" data-testid="net-a-payer"><span>Net à payer</span><span>{{ fmtMoney(shown.net_a_payer) }} DH</span></div>
            <div v-if="shown" class="mt-1 text-[13px] text-attenue">Coût employeur {{ fmtMoney(shown.cout_employeur) }} · patronal {{ fmtMoney(shown.total_cotisations_patronales) }}</div>
          </div>
          <div v-if="rapprochement" class="rounded-[10px] border border-alerte-bord bg-alerte-fond p-3.5 text-[13px] text-alerte-texte">
            <div class="text-sm font-semibold text-[#3D2900]">Rapprochement trésorerie</div>
            <div class="flex justify-between gap-3 border-b border-[#F2E2BC] py-[7px] chiffres"><span>Versé au salarié</span>
              <span>{{ fmtMoney(rapprochement.verse_salaire, { decimals: false }) }} / {{ rapprochement.net_a_payer ? fmtMoney(rapprochement.net_a_payer, { decimals: false }) : fmtMoney(rapprochement.echeances_salaire_montant, { decimals: false }) }}</span></div>
            <div class="flex justify-between gap-3 py-[7px] chiffres"><span>CNSS versée</span>
              <span>{{ fmtMoney(rapprochement.cnss_versee, { decimals: false }) }}<template v-if="rapprochement.cotisations_totales"> · cotisations {{ fmtMoney(rapprochement.cotisations_totales) }}</template></span></div>
            <div class="mt-1.5">{{ rapprochement.echeances_salaire_payees }} versement(s) de salaire payé(s) sur {{ rapprochement.echeances_salaire }}. Information seulement : un avertissement à confirmer s'affiche à la clôture, il ne bloque pas.</div>
          </div>
        </div>
      </div>

      <div v-if="slip?.status === 'calculee'" class="flex flex-col gap-2" data-testid="controles">
        <div class="text-[13px] font-semibold uppercase tracking-wide text-attenue">Contrôles avant clôture</div>
        <IssueList :issues="checks" />
        <p v-if="!checks.length" class="m-0 text-sm text-succes">Tous les contrôles sont satisfaits.</p>
      </div>

      <div v-if="versions.length > 1" class="text-[13px] text-attenue">
        Versions :
        <span v-for="v in versions" :key="v.id" class="mr-2"><StatusBadge :status="v.status" :label="`v${v.version} · ${v.status_label}`" />
          <button v-if="['cloturee', 'remplacee'].includes(v.status)" type="button" class="btn-lien ml-1" @click="openPdf('bulletin', v.id)">PDF</button></span>
      </div>

      <div class="flex flex-wrap justify-end gap-2.5 border-t border-ligne pt-4">
        <template v-if="closed">
          <button v-if="auth.isAdmin" type="button" class="btn-contour" @click="rectifying = true">Rectifier</button>
          <button type="button" class="btn-primaire" @click="openPdf('bulletin')">Télécharger le bulletin</button>
        </template>
        <template v-else-if="auth.isAdmin">
          <button v-if="slip" type="button" class="btn-contour" @click="deleting = true">Supprimer le brouillon</button>
          <button v-if="slip?.status === 'calculee'" type="button" class="btn-contour" @click="openPdf('pdf-provisoire')">Aperçu PDF provisoire</button>
          <button type="button" class="btn-contour" :disabled="busy" data-testid="enregistrer" @click="onSave">Enregistrer le brouillon</button>
          <button v-if="slip?.status === 'calculee'" type="button" class="btn-contour" :disabled="busy" @click="onCalculate">Recalculer</button>
          <button v-if="slip?.status === 'calculee'" type="button" class="btn-primaire" :disabled="busy || errors.length > 0" data-testid="cloturer"
                  @click="closing = true; confirmWarnings = !warnings.length; confirmClose = false">Clôturer</button>
          <button v-else type="button" class="btn-primaire" :disabled="busy" data-testid="calculer" @click="onCalculate">Calculer</button>
        </template>
        <template v-else-if="slip?.status === 'calculee'">
          <button type="button" class="btn-contour" @click="openPdf('pdf-provisoire')">Aperçu PDF provisoire</button>
        </template>
      </div>
    </section>

    <ConfirmDialog :open="closing" title="Clôturer et générer le bulletin" confirm-label="Clôturer" :busy="busy"
                   :disabled="!confirmClose || !confirmWarnings" @cancel="closing = false" @confirm="onClose">
      <p class="m-0 text-sm">La clôture est <strong>définitive</strong> : la paie, les cumuls et le bulletin PDF seront figés et archivés. Une correction ultérieure passera par une rectification tracée.</p>
      <IssueList class="mt-3" :issues="warnings" />
      <label v-if="warnings.length" class="mt-3 flex min-h-cible items-center gap-2 text-sm"><input v-model="confirmWarnings" type="checkbox" data-testid="confirmer-avertissements"> J'ai pris connaissance des avertissements ci-dessus.</label>
      <label class="flex min-h-cible items-center gap-2 text-sm"><input v-model="confirmClose" type="checkbox" data-testid="confirmer-cloture"> Je confirme la clôture et la génération du bulletin.</label>
      <p class="m-0 text-[13px] text-attenue" v-if="selected">Net à payer : {{ slip?.result ? fmtMoney(slip.result.net_a_payer) : '—' }} DH · plan de versement {{ rapprochement ? fmtDh(rapprochement.echeances_salaire_montant) : '—' }}</p>
    </ConfirmDialog>
    <ConfirmDialog :open="rectifying" title="Ouvrir une rectification" confirm-label="Rectifier" :busy="busy"
                   :disabled="reason.trim().length < 5" @cancel="rectifying = false" @confirm="onRectify">
      <label class="etiquette">Motif (obligatoire, 5 caractères minimum)<textarea v-model="reason" rows="3" class="rounded-lg border border-champ p-3 text-[15px]" /></label>
    </ConfirmDialog>
    <ConfirmDialog :open="deleting" title="Supprimer le brouillon" confirm-label="Supprimer" :busy="busy" @cancel="deleting = false" @confirm="onDelete">
      <p class="m-0 text-sm">Supprimer la version de travail (brouillon ou paie calculée non clôturée) ?</p>
    </ConfirmDialog>
  </div>
</template>
