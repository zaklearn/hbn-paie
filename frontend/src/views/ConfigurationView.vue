<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { download, errorMessage, http } from '@/shared/services/http'
import { MOIS_FR } from '@/shared/format'
import type { Issue } from '@/shared/types'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import IssueList from '@/components/IssueList.vue'

type Tab = 'entreprise' | 'parametres' | 'gabarit' | 'utilisateurs' | 'sauvegardes' | 'journal'
interface ParamSet { id: number; valid_from: string; label: string; comment: string; created_at: string; created_by: string;
  parameters: Record<string, unknown> & { bareme: { lower: string; upper: string | null; rate: string; deduction: string }[] } }
interface UserRow { id: number; username: string; display_name: string; role: string; active: boolean; last_login_at: string | null }

const auth = useAuthStore()
const ui = useUiStore()
const tab = ref<Tab>('entreprise')
const TABS: { id: Tab; label: string; admin?: boolean }[] = [
  { id: 'entreprise', label: 'Entreprise' }, { id: 'parametres', label: 'Paramètres de paie' },
  { id: 'gabarit', label: "Gabarit d'échéancier" }, { id: 'utilisateurs', label: 'Utilisateurs', admin: true },
  { id: 'sauvegardes', label: 'Sauvegardes', admin: true }, { id: 'journal', label: 'Journal' },
]
const busy = ref(false)
const issues = ref<Issue[]>([])
function fail(e: unknown) {
  const data = (e as { response?: { data?: { issues?: Issue[] } } }).response?.data
  if (data?.issues) issues.value = data.issues; else ui.notify(errorMessage(e), 'erreur')
}

// --- Entreprise --------------------------------------------------------------------------
const COMPANY: [string, string][] = [['raison_sociale', 'Raison sociale *'], ['adresse', 'Adresse'], ['ville', 'Ville'], ['ice', 'ICE'],
  ['cnss_employeur', 'N° CNSS employeur'], ['rc', 'RC'], ['identifiant_fiscal', 'Identifiant fiscal'], ['telephone', 'Téléphone'], ['email', 'E-mail']]
const company = reactive<Record<string, string>>({})
const hasLogo = ref(false)
const logo = ref<string | undefined>(undefined)
async function loadCompany() {
  const c = (await http.get('/api/paie/entreprise')).data
  for (const [k] of COMPANY) company[k] = c?.[k] ?? ''
  hasLogo.value = !!c?.has_logo; logo.value = undefined
}
function pickLogo(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => { logo.value = String(reader.result).split(',')[1] ?? '' }
  reader.readAsDataURL(file)
}
async function saveCompany() {
  busy.value = true; issues.value = []
  try {
    const r = await http.put('/api/paie/entreprise', { ...company, ...(logo.value !== undefined ? { logo_base64: logo.value } : {}) })
    issues.value = r.data.issues; ui.notify('Entreprise enregistrée.'); await loadCompany()
  } catch (e) { fail(e) } finally { busy.value = false }
}

// --- Paramètres : versions datées, jamais modifiées ----------------------------------------
// Libellés d'origine (paie-bulletins, views/parametres.py). Valeurs affichées et saisies telles quelles
// (texte décimal exact, ex. 0.0448) : aucune conversion en pourcentage dans le navigateur (R0).
const RATES: [string, string][] = [['cnss_salarial', 'CNSS — part salariale'], ['amo_salarial', 'AMO — part salariale'],
  ['cnss_patronal', 'CNSS — part patronale'], ['amo_patronal', 'AMO — part patronale'], ['participation_amo', 'Participation AMO'],
  ['formation_pro', 'Taxe de formation professionnelle'], ['allocations_familiales', 'Allocations familiales (patronal)'],
  ['fp_taux_bas', 'Frais pro. — taux si revenu annuel ≤ seuil'], ['fp_taux_haut', 'Frais pro. — taux si revenu annuel > seuil'],
  ['imposable_heures_sup', 'Part imposable — heures supplémentaires'], ['imposable_prime_panier', 'Part imposable — prime de panier'],
  ['imposable_transport', 'Part imposable — indemnité de transport'], ['imposable_representation', 'Part imposable — indemnité de représentation'],
  ['imposable_autre_prime', 'Part imposable — autre prime']]
const AMOUNTS: [string, string][] = [['plafond_cnss', 'Plafond mensuel CNSS (MAD)'], ['fp_seuil_annuel', 'Seuil annuel des frais pro. (MAD)'],
  ['fp_plafond_annuel', 'Plafond annuel des frais pro. (MAD)'], ['deduction_par_personne', 'Déduction annuelle par personne à charge (MAD)']]
const OTHER_LABELS: Record<string, string> = { max_personnes: 'Nombre maximum de personnes à charge',
  methode_totaux: 'Méthode des totaux de cotisations' }
const methodes = ref<Record<string, string>>({})
http.get('/api/paie/referentiels').then((r) => { methodes.value = r.data.methodes_totaux ?? {} }).catch(() => undefined)
const sets = ref<ParamSet[]>([])
const chosenId = ref<number | null>(null)
const chosen = computed(() => sets.value.find((s) => s.id === chosenId.value) ?? sets.value[0] ?? null)
const otherKeys = computed(() => Object.keys(chosen.value?.parameters ?? {}).filter((k) => k !== 'bareme'
  && !RATES.some(([r]) => r === k) && !AMOUNTS.some(([a]) => a === k)))
async function loadParams() { sets.value = (await http.get<ParamSet[]>('/api/paie/parametres')).data }
const creating = ref(false)
const newVersion = reactive({ year: new Date().getFullYear(), month: 1, label: 'Mise à jour des paramètres', comment: '',
  parameters: {} as Record<string, unknown> })
function startVersion() {
  issues.value = []
  newVersion.parameters = JSON.parse(JSON.stringify(chosen.value?.parameters ?? {}))
  creating.value = true
}
async function createVersion() {
  busy.value = true; issues.value = []
  try {
    const r = await http.post('/api/paie/parametres', newVersion)
    issues.value = r.data.issues; creating.value = false; ui.notify('Nouvelle version de paramètres créée.'); await loadParams()
  } catch (e) { fail(e) } finally { busy.value = false }
}
const bareme = computed(() => newVersion.parameters.bareme as ParamSet['parameters']['bareme'])

// --- Gabarit, utilisateurs, journal --------------------------------------------------------
const gabarit = ref<{ jour: number; type: string }[]>([])
const users = ref<UserRow[]>([])
const newUser = reactive({ username: '', display_name: '', role: 'user', password: '' })
const pwdFor = ref<UserRow | null>(null)
const newPwd = ref('')
async function loadUsers() { users.value = (await http.get<UserRow[]>('/api/socle/utilisateurs')).data }
async function createUser() {
  busy.value = true
  try { await http.post('/api/socle/utilisateurs', newUser); Object.assign(newUser, { username: '', display_name: '', role: 'user', password: '' }); ui.notify('Compte créé.'); await loadUsers() }
  catch (e) { ui.notify(errorMessage(e), 'erreur') } finally { busy.value = false }
}
async function userAction(u: UserRow, path: string, body: unknown, msg: string) {
  try { await http.post(`/api/socle/utilisateurs/${u.id}/${path}`, body); ui.notify(msg); await loadUsers() } catch (e) { ui.notify(errorMessage(e), 'erreur') }
}
async function savePassword() {
  if (!pwdFor.value) return
  await userAction(pwdFor.value, 'mot-de-passe', { password: newPwd.value }, 'Mot de passe changé ; sessions du compte fermées.')
  pwdFor.value = null; newPwd.value = ''
}
const backups = ref<{ name: string; size: number }[]>([])
const restoreFile = ref<File | null>(null)
async function loadBackups() { backups.value = (await http.get('/api/socle/sauvegardes')).data }
async function createBackup() {
  busy.value = true
  try { const r = await http.post('/api/socle/sauvegardes'); ui.notify(`Sauvegarde créée : ${r.data.name}`); await loadBackups() }
  catch (e) { ui.notify(errorMessage(e), 'erreur') } finally { busy.value = false }
}
function pickRestore(ev: Event) { restoreFile.value = (ev.target as HTMLInputElement).files?.[0] ?? null; (ev.target as HTMLInputElement).value = '' }
async function confirmRestore() {
  if (!restoreFile.value) return
  busy.value = true
  try {
    const r = await http.post('/api/socle/sauvegardes/restauration', await restoreFile.value.arrayBuffer(),
      { headers: { 'Content-Type': 'application/zip' }, timeout: 600_000 })
    restoreFile.value = null
    ui.notify(`${r.data.message} Sauvegarde de sécurité : ${r.data.safety}`)
    await auth.fetchMe()
  } catch (e) { ui.notify(errorMessage(e), 'erreur') } finally { busy.value = false }
}
const audit = ref<Record<string, string>[]>([])
const auditAction = ref('')

watch(tab, async (t) => {
  issues.value = []
  try {
    if (t === 'entreprise') await loadCompany()
    if (t === 'parametres') await loadParams()
    if (t === 'gabarit') gabarit.value = (await http.get('/api/tresorerie/gabarit')).data
    if (t === 'utilisateurs') await loadUsers()
    if (t === 'sauvegardes' && auth.isAdmin) await loadBackups()
    if (t === 'journal') audit.value = (await http.get('/api/paie/audit', { params: { limit: 500, action: auditAction.value || undefined } })).data
  } catch (e) { ui.notify(errorMessage(e), 'erreur') }
}, { immediate: true })
</script>

<template>
  <div class="flex flex-col gap-5">
    <h1 class="m-0 text-[26px] font-bold">Configuration</h1>
    <div role="tablist" aria-label="Configuration" class="flex flex-wrap border-b border-bordure">
      <button v-for="t in TABS.filter((x) => !x.admin || auth.isAdmin)" :key="t.id" type="button" role="tab" :aria-selected="tab === t.id"
              :class="['onglet', tab === t.id && 'onglet-actif']" @click="tab = t.id">{{ t.label }}</button>
    </div>
    <IssueList :issues="issues" />

    <form v-if="tab === 'entreprise'" class="carte flex flex-col gap-4 p-5" @submit.prevent="saveCompany">
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label v-for="[k, l] in COMPANY" :key="k" class="etiquette">{{ l }}<input v-model="company[k]" class="champ" :readonly="!auth.isAdmin"></label>
        <label v-if="auth.isAdmin" class="etiquette">Logo (PNG/JPEG, 1 Mo max){{ hasLogo ? ' — un logo est enregistré' : '' }}<input type="file" accept="image/png,image/jpeg" class="text-sm" @change="pickLogo"></label>
      </div>
      <div v-if="auth.isAdmin" class="flex justify-end gap-2.5">
        <button v-if="hasLogo" type="button" class="btn-contour" @click="logo = ''; saveCompany()">Retirer le logo</button>
        <button type="submit" class="btn-primaire" :disabled="busy">Enregistrer</button></div>
    </form>

    <template v-if="tab === 'parametres'">
      <section class="carte overflow-x-auto">
        <h2 class="m-0 px-[18px] pt-4 text-base font-semibold">Historique des versions</h2>
        <table class="w-full min-w-[640px] border-collapse">
          <thead><tr><th class="th">En vigueur à partir de</th><th class="th">Libellé</th><th class="th">Motif / source</th><th class="th">Créée le</th><th class="th">Par</th><th class="th"><span class="sr-only">Consulter</span></th></tr></thead>
          <tbody><tr v-for="s in sets" :key="s.id" :class="s === chosen && 'bg-selection'"><td class="td">{{ s.valid_from }}</td><td class="td">{{ s.label }}</td><td class="td">{{ s.comment }}</td>
            <td class="td">{{ s.created_at.replace('T', ' ') }}</td><td class="td">{{ s.created_by }}</td><td class="td text-right"><button type="button" class="btn-lien" @click="chosenId = s.id">Consulter</button></td></tr></tbody>
        </table>
      </section>
      <section v-if="chosen" class="carte flex flex-col gap-3 p-5">
        <div class="flex flex-wrap items-center justify-between gap-3"><h2 class="m-0 text-base font-semibold">Version {{ chosen.valid_from }} — {{ chosen.label }}</h2>
          <button v-if="auth.isAdmin" type="button" class="btn-primaire" @click="startVersion">Créer une nouvelle version</button></div>
        <p class="m-0 text-[13px] text-attenue">Une version existante n'est jamais modifiée : toute évolution passe par une nouvelle version datée, saisie par le propriétaire, jamais rétroactive. Valeurs en texte décimal exact (taux : 0.0448 = 4,48 %).</p>
        <dl class="m-0 grid grid-cols-1 gap-x-6 text-sm sm:grid-cols-2">
          <div v-for="[k, l] in [...RATES, ...AMOUNTS]" :key="k" class="flex justify-between gap-3 border-b border-ligne py-2"><dt class="text-attenue">{{ l }}</dt><dd class="m-0 chiffres">{{ chosen.parameters[k] }}</dd></div>
          <div v-for="k in otherKeys" :key="k" class="flex justify-between gap-3 border-b border-ligne py-2"><dt class="text-attenue">{{ OTHER_LABELS[k] ?? k }}</dt><dd class="m-0">{{ k === 'methode_totaux' ? (methodes[String(chosen.parameters[k])] ?? chosen.parameters[k]) : chosen.parameters[k] }}</dd></div>
        </dl>
        <table class="w-full border-collapse"><thead><tr><th class="th">À partir de</th><th class="th">Jusqu'à</th><th class="th">Taux</th><th class="th">Somme à déduire</th></tr></thead>
          <tbody><tr v-for="(b, i) in chosen.parameters.bareme" :key="i"><td class="td chiffres">{{ b.lower }}</td><td class="td chiffres">{{ b.upper ?? 'et plus' }}</td><td class="td chiffres">{{ b.rate }}</td><td class="td chiffres">{{ b.deduction }}</td></tr></tbody></table>
      </section>
    </template>

    <section v-if="tab === 'gabarit'" class="carte flex flex-col gap-3 p-5">
      <p class="m-0 text-sm text-attenue">Gabarit fixe, commun à tous les salariés, défini dans le code (lecture seule). Rappel J-1 = échéance − 1 jour.</p>
      <table class="w-full border-collapse"><thead><tr><th class="th">Jour</th><th class="th">Type</th></tr></thead>
        <tbody><tr v-for="g in gabarit" :key="g.type"><td class="td">{{ g.jour === 30 ? '30 ou dernier jour du mois' : g.jour }}</td><td class="td">{{ g.type }}</td></tr></tbody></table>
    </section>

    <template v-if="tab === 'utilisateurs' && auth.isAdmin">
      <section class="carte overflow-x-auto">
        <table class="w-full min-w-[640px] border-collapse">
          <thead><tr><th class="th">Identifiant</th><th class="th">Nom</th><th class="th">Rôle</th><th class="th">État</th><th class="th">Dernière connexion</th><th class="th"><span class="sr-only">Actions</span></th></tr></thead>
          <tbody><tr v-for="u in users" :key="u.id"><td class="td font-semibold">{{ u.username }}</td><td class="td">{{ u.display_name }}</td>
            <td class="td"><select :value="u.role" class="champ h-9" @change="userAction(u, 'role', { role: ($event.target as HTMLSelectElement).value }, 'Rôle modifié.')"><option>superadmin</option><option>user</option></select></td>
            <td class="td">{{ u.active ? 'Actif' : 'Désactivé' }}</td><td class="td">{{ u.last_login_at?.replace('T', ' ') ?? '—' }}</td>
            <td class="td whitespace-nowrap text-right"><button type="button" class="btn-lien mr-3" @click="pwdFor = u">Mot de passe</button>
              <button type="button" class="btn-lien text-attenue" @click="userAction(u, 'activation', { active: !u.active }, u.active ? 'Compte désactivé.' : 'Compte réactivé.')">{{ u.active ? 'Désactiver' : 'Réactiver' }}</button></td></tr></tbody>
        </table>
      </section>
      <form class="carte flex flex-wrap items-end gap-3 p-5" @submit.prevent="createUser">
        <label class="etiquette">Identifiant<input v-model="newUser.username" class="champ" required></label>
        <label class="etiquette">Nom affiché<input v-model="newUser.display_name" class="champ"></label>
        <label class="etiquette">Rôle<select v-model="newUser.role" class="champ"><option>user</option><option>superadmin</option></select></label>
        <label class="etiquette">Mot de passe (10 caractères minimum)<input v-model="newUser.password" type="password" autocomplete="new-password" class="champ" required></label>
        <button type="submit" class="btn-primaire" :disabled="busy">Créer le compte</button>
      </form>
    </template>

    <template v-if="tab === 'sauvegardes' && auth.isAdmin">
      <div class="flex flex-wrap items-center gap-3">
        <button type="button" class="btn-primaire" :disabled="busy" data-testid="creer-sauvegarde" @click="createBackup">Créer une sauvegarde</button>
        <label class="btn-contour cursor-pointer">Restaurer depuis un fichier…<input type="file" accept=".zip" class="sr-only" @change="pickRestore"></label>
      </div>
      <p class="m-0 text-[13px] text-attenue">Sauvegarde complète : base, paramètres, comptes, journal et bulletins PDF archivés. Toute restauration est précédée d'une sauvegarde automatique ; le fichier est vérifié (empreintes, protections, unicités, références) avant toute modification.</p>
      <section class="carte overflow-x-auto">
        <table class="w-full min-w-[480px] border-collapse">
          <thead><tr><th class="th">Fichier</th><th class="th text-right">Taille</th><th class="th"><span class="sr-only">Télécharger</span></th></tr></thead>
          <tbody>
            <tr v-for="b in backups" :key="b.name"><td class="td">{{ b.name }}</td><td class="td text-right chiffres">{{ b.size.toLocaleString('fr-FR') }} octets</td>
              <td class="td text-right"><button type="button" class="btn-lien" @click="download(`/api/socle/sauvegardes/${b.name}`)">Télécharger</button></td></tr>
            <tr v-if="!backups.length"><td class="td text-attenue" colspan="3">Aucune sauvegarde.</td></tr>
          </tbody>
        </table>
      </section>
    </template>

    <template v-if="tab === 'journal'">
      <label class="etiquette max-w-sm">Filtrer par action<input v-model="auditAction" class="champ" placeholder="ex. paie.cloture" @change="tab = 'entreprise'; tab = 'journal'"></label>
      <section class="carte overflow-x-auto">
        <table class="w-full min-w-[720px] border-collapse">
          <thead><tr><th class="th">Date</th><th class="th">Acteur</th><th class="th">Action</th><th class="th">Objet</th><th class="th">Détails</th></tr></thead>
          <tbody><tr v-for="a in audit" :key="a.id"><td class="td whitespace-nowrap">{{ a.ts.replace('T', ' ') }}</td><td class="td">{{ a.actor }}</td><td class="td">{{ a.action }}</td>
            <td class="td">{{ a.entity }} {{ a.entity_id }}</td><td class="td text-xs text-attenue">{{ a.details }}</td></tr></tbody>
        </table>
      </section>
    </template>

    <ConfirmDialog :open="creating" title="Créer une nouvelle version de paramètres" confirm-label="Créer la version" :busy="busy"
                   :disabled="!newVersion.comment.trim()" @cancel="creating = false" @confirm="createVersion">
      <div class="flex max-h-[60vh] flex-col gap-3 overflow-y-auto pr-1">
        <div class="grid grid-cols-2 gap-3">
          <label class="etiquette">Année d'effet<input v-model.number="newVersion.year" type="number" min="2000" max="2100" class="champ"></label>
          <label class="etiquette">Mois d'effet<select v-model.number="newVersion.month" class="champ"><option v-for="(m, i) in MOIS_FR" :key="m" :value="i + 1">{{ m }}</option></select></label>
        </div>
        <label class="etiquette">Libellé<input v-model="newVersion.label" class="champ"></label>
        <label class="etiquette">Motif ou source *<textarea v-model="newVersion.comment" rows="2" class="rounded-lg border border-champ p-3" /></label>
        <label v-for="[k, l] in [...RATES, ...AMOUNTS]" :key="k" class="etiquette">{{ l }}<input v-model="newVersion.parameters[k]" class="champ chiffres"></label>
        <label v-for="k in otherKeys" :key="k" class="etiquette">{{ OTHER_LABELS[k] ?? k }}
          <select v-if="k === 'methode_totaux'" v-model="newVersion.parameters[k]" class="champ"><option v-for="(l, v) in methodes" :key="v" :value="v">{{ l }}</option></select>
          <input v-else-if="k === 'max_personnes'" v-model.number="newVersion.parameters[k]" type="number" min="0" class="champ">
          <input v-else v-model="newVersion.parameters[k]" class="champ"></label>
        <div class="text-[13px] font-semibold">Barème IR (annuel)</div>
        <div v-for="(b, i) in bareme" :key="i" class="grid grid-cols-4 gap-2">
          <input v-model="b.lower" class="champ chiffres" aria-label="À partir de"><input v-model="b.upper" class="champ chiffres" aria-label="Jusqu'à" placeholder="et plus">
          <input v-model="b.rate" class="champ chiffres" aria-label="Taux"><input v-model="b.deduction" class="champ chiffres" aria-label="Somme à déduire">
        </div>
      </div>
    </ConfirmDialog>
    <ConfirmDialog :open="!!restoreFile" title="Remplacer toute la base" confirm-label="Restaurer" :busy="busy"
                   @cancel="restoreFile = null" @confirm="confirmRestore">
      <p class="m-0 text-sm">Remplacement <strong>total</strong> de la base par <strong>{{ restoreFile?.name }}</strong>. Les données actuelles seront remplacées ; une sauvegarde de sécurité est créée d'abord. Toutes les sessions seront fermées.</p>
    </ConfirmDialog>
    <ConfirmDialog :open="!!pwdFor" title="Changer le mot de passe" :busy="busy" :disabled="newPwd.length < 10" @cancel="pwdFor = null" @confirm="savePassword">
      <label class="etiquette">Nouveau mot de passe pour {{ pwdFor?.username }}<input v-model="newPwd" type="password" autocomplete="new-password" class="champ"></label>
    </ConfirmDialog>
  </div>
</template>
