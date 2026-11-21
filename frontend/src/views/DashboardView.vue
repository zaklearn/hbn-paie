<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useContextStore } from '@/stores/context'
import { useAuthStore } from '@/stores/auth'
import { http } from '@/shared/services/http'
import { fmtDate, fmtDh, fmtMoney, MOIS_FR } from '@/shared/format'
import KpiCard from '@/components/KpiCard.vue'
import StatusBadge from '@/components/StatusBadge.vue'

interface Dot { type: string; state: string }
interface Row {
  employee_id: number; matricule: string; nom: string; prenom: string; fonction: string; dots: Dot[];
  paid_count: number; late_count: number; echeances: number; verse_salaire: number; salaire_attendu: number;
  status: string; status_label: string; net_a_payer: string | null; declared: boolean
}
interface Dashboard {
  aujourdhui: string; salaries_actifs: number; rows: Row[]
  kpi: { salaires_attendus: number; salaires_verses: number; salaires_reste: number; salaires_avancement: number;
    cnss_du_mois: number; cnss_versee: number; bulletins_clotures: number; bulletins: Record<string, number> }
  a_traiter: { en_retard: { nom: string; type: string; date_echeance: string }[]; rappels_demain: number;
    prochain_rappel: string | null; prets_a_cloturer: { nom: string }[] }
  prochaines: { date_echeance: string; type: string; nombre: number; montant: number }[]
  mois_suivant: { year: number; month: number; declare: boolean }
}

const ctx = useContextStore()
const auth = useAuthStore()
const data = ref<Dashboard | null>(null)
const year = ref<{ mois_clotures: number[]; mois_ouverts: number[]; alertes: string[]; nb_brouillons: number; nb_calculees: number;
  dernieres_paies: { id: number; employee_id: number; year: number; month: number; version: number; employee_snapshot: Record<string, string> | null }[] } | null>(null)
const error = ref('')

const DOT: Record<string, string> = {
  paye_a_temps: 'bg-succes', paye_avance: 'bg-succes', paye_retard: 'bg-[#B45309]', en_retard: 'bg-danger',
  a_venir: 'border-2 border-[#9AA3AF]', non_declaree: 'border-2 border-dotted border-[#C9D2E3]',
}
const shortType = (t: string) => t.replace('Salaire – ', '').replace(' – cotisation mensuelle', '')

async function load() {
  error.value = ''
  try {
    const [m, y] = await Promise.all([
      http.get<Dashboard>('/api/paie/tableau-de-bord-mois', { params: { year: ctx.year, month: ctx.month } }),
      http.get('/api/paie/tableau-de-bord', { params: { year: ctx.year } }),
    ])
    data.value = m.data; year.value = y.data
  } catch { error.value = 'Tableau de bord indisponible.' }
}
watch(() => ctx.periode, load, { immediate: true })

const rows = computed(() => (data.value?.rows ?? []).filter((r) => !ctx.salarie || r.matricule === ctx.salarie))
const b = computed(() => data.value?.kpi.bulletins ?? {})
const bulletinsHint = computed(() => [
  b.value.calculee ? `${b.value.calculee} calculé${b.value.calculee > 1 ? 's' : ''}` : '',
  b.value.brouillon ? `${b.value.brouillon} brouillon${b.value.brouillon > 1 ? 's' : ''}` : '',
  b.value.a_saisir ? `${b.value.a_saisir} à saisir` : '',
].filter(Boolean).join(' · ') || 'tous clôturés')
</script>

<template>
  <div class="flex flex-col gap-6">
    <div class="flex flex-wrap items-end gap-4">
      <div class="flex-[1_1_320px]">
        <h1 class="m-0 text-[26px] font-bold">Tableau de bord</h1>
        <p class="mt-1.5 text-sm text-attenue" v-if="data">
          {{ ctx.label }} · {{ data.salaries_actifs }} salarié{{ data.salaries_actifs > 1 ? 's' : '' }} actif{{ data.salaries_actifs > 1 ? 's' : '' }} · aujourd'hui le {{ fmtDate(data.aujourdhui) }}
        </p>
      </div>
      <RouterLink :to="{ name: 'paie', query: ctx.query }" class="btn-primaire no-underline">Ouvrir la paie du mois</RouterLink>
    </div>
    <p v-if="error" role="alert" class="text-danger">{{ error }}</p>
    <template v-if="data">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Salaires nets du mois" :value="fmtDh(data.kpi.salaires_attendus)" hint="selon plans de versement" />
        <KpiCard label="Salaires versés" :value="fmtDh(data.kpi.salaires_verses)" :progress="data.kpi.salaires_avancement"
                 :hint="`reste ${fmtDh(data.kpi.salaires_reste)} · ${data.kpi.salaires_avancement} %`" />
        <KpiCard label="CNSS du mois" :value="fmtDh(data.kpi.cnss_du_mois)"
                 :hint="data.kpi.cnss_du_mois && data.kpi.cnss_versee === data.kpi.cnss_du_mois ? 'entièrement versée' : `${fmtDh(data.kpi.cnss_versee)} versés`"
                 :hint-class="data.kpi.cnss_du_mois && data.kpi.cnss_versee === data.kpi.cnss_du_mois ? 'text-succes' : undefined" />
        <KpiCard label="Bulletins clôturés" :value="`${data.kpi.bulletins_clotures} / ${data.salaries_actifs}`" :hint="bulletinsHint" />
      </div>
      <div class="flex flex-wrap items-start gap-6">
        <section class="carte min-w-0 flex-[999_1_600px]">
          <div class="flex items-center justify-between px-[18px] py-4">
            <h2 class="m-0 text-base font-semibold">Suivi par salarié — trésorerie et bulletin</h2>
            <span class="text-[13px] text-attenue">versé / net du mois</span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full min-w-[640px] border-collapse">
              <thead><tr><th class="th">Salarié</th><th class="th">Échéances</th><th class="th">Versé / net</th><th class="th">Bulletin</th><th class="th"><span class="sr-only">Action</span></th></tr></thead>
              <tbody>
                <tr v-for="r in rows" :key="r.employee_id" data-testid="ligne-salarie">
                  <td class="td"><div class="font-semibold">{{ r.nom }} {{ r.prenom }}</div><div class="text-xs text-attenue">{{ r.matricule }} · {{ r.fonction }}</div></td>
                  <td class="td">
                    <div class="flex items-center gap-1.5">
                      <span v-for="d in r.dots" :key="d.type" :title="`${shortType(d.type)} : ${d.state.replace(/_/g, ' ')}`"
                            :class="['box-border h-2.5 w-2.5 rounded-full', DOT[d.state]]" />
                      <span v-if="r.late_count" class="ml-1 text-[13px] text-danger">{{ r.late_count }} en retard</span>
                      <span v-else-if="r.declared" class="ml-1 text-[13px] text-attenue">{{ r.paid_count }} / {{ r.echeances }}</span>
                      <span v-else class="ml-1 text-[13px] text-attenue">non déclaré</span>
                    </div>
                  </td>
                  <td class="td chiffres">{{ fmtMoney(String(r.verse_salaire), { decimals: false }) }} / {{ r.net_a_payer ? fmtMoney(r.net_a_payer, { decimals: false }) : fmtMoney(String(r.salaire_attendu), { decimals: false }) }}</td>
                  <td class="td"><StatusBadge :status="r.status" :label="r.status_label" /></td>
                  <td class="td text-right">
                    <RouterLink v-if="r.late_count && auth.isAdmin" :to="{ name: 'tresorerie', query: { ...ctx.query, salarie: r.matricule } }" class="btn-lien">Régler</RouterLink>
                    <RouterLink v-else :to="{ name: 'paie', query: { ...ctx.query, salarie: r.matricule } }" class="btn-lien">Ouvrir</RouterLink>
                  </td>
                </tr>
                <tr v-if="!rows.length"><td class="td text-attenue" colspan="5">Aucun salarié actif sur ce mois.</td></tr>
              </tbody>
            </table>
          </div>
          <div class="flex flex-wrap gap-4 px-[18px] py-3.5 text-xs text-attenue">
            <span class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-succes" />payé à temps</span>
            <span class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-[#B45309]" />payé en retard</span>
            <span class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-danger" />échu non payé</span>
            <span class="flex items-center gap-1.5"><span class="box-border h-2.5 w-2.5 rounded-full border-2 border-[#9AA3AF]" />à venir</span>
            <span>Ordre : 1er versement · CNSS · 2e · 3e</span>
          </div>
        </section>
        <aside class="flex min-w-0 flex-[1_1_300px] flex-col gap-4">
          <section class="carte p-[18px]">
            <h2 class="m-0 mb-3 text-base font-semibold">À traiter</h2>
            <div class="flex flex-col gap-3 text-sm">
              <div class="flex gap-2.5"><span class="mt-1.5 h-2 w-2 flex-none rounded bg-danger" /><div>
                <strong>{{ data.a_traiter.en_retard.length }} échéance{{ data.a_traiter.en_retard.length > 1 ? 's' : '' }} en retard</strong>
                <div class="text-[13px] text-attenue">{{ data.a_traiter.en_retard.map((l) => `${l.nom} · ${shortType(l.type)}`).join(' ; ') || 'Aucune' }}</div></div></div>
              <div class="flex gap-2.5"><span class="mt-1.5 h-2 w-2 flex-none rounded bg-accent" /><div>
                <strong>Rappels J-1 demain</strong>
                <div class="text-[13px] text-attenue">{{ data.a_traiter.rappels_demain || 'Aucun' }}{{ data.a_traiter.prochain_rappel ? ` · prochains le ${fmtDate(data.a_traiter.prochain_rappel).slice(0, 5)}` : '' }}</div></div></div>
              <div class="flex gap-2.5"><span class="mt-1.5 h-2 w-2 flex-none rounded bg-[#1D4ED8]" /><div>
                <strong>{{ data.a_traiter.prets_a_cloturer.length }} bulletin{{ data.a_traiter.prets_a_cloturer.length > 1 ? 's' : '' }} prêt{{ data.a_traiter.prets_a_cloturer.length > 1 ? 's' : '' }} à clôturer</strong>
                <div class="text-[13px] text-attenue">{{ data.a_traiter.prets_a_cloturer.map((p) => p.nom).join(' ; ') || 'Aucun' }}</div></div></div>
            </div>
          </section>
          <section v-if="year" class="carte p-[18px]" data-testid="annee">
            <h2 class="m-0 mb-3 text-base font-semibold">Année {{ ctx.year }} — paie</h2>
            <div class="flex flex-col gap-2 text-sm">
              <div><span class="text-attenue">Mois clôturés :</span> {{ year.mois_clotures.map((m) => MOIS_FR[m - 1]).join(', ') || 'aucun' }}</div>
              <div><span class="text-attenue">Mois ouverts :</span> {{ year.mois_ouverts.map((m) => MOIS_FR[m - 1]).join(', ') || 'aucun' }} ({{ year.nb_brouillons }} brouillon(s), {{ year.nb_calculees }} calculée(s))</div>
              <ul v-if="year.alertes.length" class="m-0 flex list-none flex-col gap-1.5 p-0">
                <li v-for="a in year.alertes" :key="a" class="rounded-lg bg-alerte-fond px-3 py-2 text-[13px] text-alerte-texte">{{ a }}</li>
              </ul>
              <div v-if="year.dernieres_paies.length"><div class="text-attenue">Dernières paies clôturées :</div>
                <div v-for="p in year.dernieres_paies" :key="p.id" class="text-[13px]">{{ String(p.month).padStart(2, '0') }}/{{ p.year }} · {{ p.employee_snapshot?.matricule }} {{ p.employee_snapshot?.nom }} · v{{ p.version }}</div></div>
            </div>
          </section>
          <section class="carte p-[18px]">
            <h2 class="m-0 mb-3 text-base font-semibold">Prochaines échéances</h2>
            <div class="flex flex-col gap-2.5 text-sm">
              <div v-for="p in data.prochaines" :key="p.date_echeance + p.type" class="flex justify-between gap-2">
                <span>{{ fmtDate(p.date_echeance).slice(0, 5) }} · {{ shortType(p.type) }}{{ p.nombre > 1 ? ` ×${p.nombre}` : '' }}</span><strong class="chiffres">{{ fmtDh(p.montant) }}</strong>
              </div>
              <div v-if="!data.mois_suivant.declare" class="flex justify-between gap-2">
                <span>{{ String(data.mois_suivant.month).padStart(2, '0') }}/{{ data.mois_suivant.year }} · mois non déclaré</span>
                <RouterLink v-if="auth.isAdmin" :to="{ name: 'tresorerie', query: { periode: `${data.mois_suivant.year}-${String(data.mois_suivant.month).padStart(2, '0')}` } }" class="font-semibold">Déclarer</RouterLink>
              </div>
            </div>
          </section>
        </aside>
      </div>
    </template>
  </div>
</template>
