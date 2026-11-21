<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useContextStore } from '@/stores/context'
import { useEmployeesStore } from '@/stores/employees'
import { useUiStore } from '@/stores/ui'
import { download, errorMessage, http } from '@/shared/services/http'
import { fmtMoney, MOIS_FR } from '@/shared/format'
import type { Payslip } from '@/shared/types'
import StatusBadge from '@/components/StatusBadge.vue'

type Row = Record<string, string | number | null>
const ctx = useContextStore()
const employees = useEmployeesStore()
const ui = useUiStore()
const wholeYear = ref(false)
const includeOpen = ref(false)
const archives = ref<Payslip[]>([])
const journal = ref<{ journal: Row[]; monthly: Row[]; annual: Row[] }>({ journal: [], monthly: [], annual: [] })
const employeeId = computed(() => employees.byMatricule(ctx.salarie)?.id)
const month = computed(() => (wholeYear.value ? undefined : ctx.month))
const who = (id: number) => { const e = employees.byId(id); return e ? `${e.matricule} · ${e.nom} ${e.prenom}` : `n° ${id}` }

async function load() {
  try {
    await employees.load()
    const [a, j] = await Promise.all([
      http.get<Payslip[]>('/api/paie/paies', { params: { year: ctx.year, month: month.value, employee_id: employeeId.value, status: ['cloturee', 'remplacee'] }, paramsSerializer: { indexes: null } }),
      http.get('/api/paie/journal', { params: { year: ctx.year, month: month.value, include_open: includeOpen.value } }),
    ])
    archives.value = a.data; journal.value = j.data
  } catch (e) { ui.notify(errorMessage(e), 'erreur') }
}
watch(() => [ctx.periode, ctx.salarie, wholeYear.value, includeOpen.value], load, { immediate: true })
async function pdf(id: number) {
  try { await download(`/api/paie/paies/${id}/bulletin`) } catch (e) { ui.notify(errorMessage(e), 'erreur') }
}
const columns = (rows: Row[]) => (rows[0] ? Object.keys(rows[0]) : [])
const cell = (v: string | number | null) => (typeof v === 'string' && /^-?\d+(\.\d+)?$/.test(v) ? fmtMoney(v) : v)
const params = computed(() => ({ year: ctx.year, month: month.value, include_open: includeOpen.value }))
</script>

<template>
  <div class="flex flex-col gap-5">
    <div class="flex flex-wrap items-end gap-4">
      <div class="flex-[1_1_320px]"><h1 class="m-0 text-[26px] font-bold">Bulletins & exports</h1>
        <p class="mt-1.5 text-sm text-attenue">Exports limités au matricule, au nom et aux montants : ni CIN, ni CNSS, ni coordonnées bancaires.</p></div>
      <button type="button" class="btn-primaire" @click="download('/api/paie/exports/recapitulatif.xlsx', params)">Classeur complet (Excel)</button>
    </div>
    <div class="flex flex-wrap gap-4 text-sm">
      <label class="flex min-h-cible items-center gap-2"><input v-model="wholeYear" type="checkbox"> Toute l'année {{ ctx.year }}</label>
      <label class="flex min-h-cible items-center gap-2"><input v-model="includeOpen" type="checkbox"> Inclure les paies non clôturées (brouillons calculés)</label>
      <button type="button" class="btn-contour" @click="download('/api/paie/exports/livre-de-paie.csv', params)">Livre de paie (CSV)</button>
    </div>
    <section class="carte">
      <h2 class="m-0 px-[18px] pt-4 text-base font-semibold">Archives des bulletins — {{ wholeYear ? ctx.year : `${MOIS_FR[ctx.month - 1]} ${ctx.year}` }}</h2>
      <div class="overflow-x-auto"><table class="w-full min-w-[560px] border-collapse">
        <thead><tr><th class="th">Période</th><th class="th">Salarié</th><th class="th">Version</th><th class="th">Statut</th><th class="th text-right">Net à payer</th><th class="th"><span class="sr-only">PDF</span></th></tr></thead>
        <tbody>
          <tr v-for="s in archives" :key="s.id"><td class="td">{{ String(s.month).padStart(2, '0') }}/{{ s.year }}</td><td class="td">{{ who(s.employee_id) }}</td>
            <td class="td">v{{ s.version }}</td><td class="td"><StatusBadge :status="s.status" :label="s.status_label" /></td>
            <td class="td text-right chiffres">{{ s.result ? fmtMoney(s.result.net_a_payer) : '—' }}</td>
            <td class="td text-right"><button type="button" class="btn-lien" @click="pdf(s.id)">Télécharger</button></td></tr>
          <tr v-if="!archives.length"><td class="td text-attenue" colspan="6">Aucun bulletin archivé pour cette sélection.</td></tr>
        </tbody></table></div>
    </section>
    <section v-for="[title, rows] in ([['Livre de paie', journal.journal], ['Récapitulatif mensuel', journal.monthly], ['Récapitulatif annuel par salarié', journal.annual]] as [string, Row[]][])" :key="title" class="carte">
      <h2 class="m-0 px-[18px] pt-4 text-base font-semibold">{{ title }}</h2>
      <div class="overflow-x-auto"><table class="w-full border-collapse">
        <thead><tr><th v-for="c in columns(rows)" :key="c" class="th whitespace-nowrap">{{ c }}</th></tr></thead>
        <tbody>
          <tr v-for="(r, i) in rows" :key="i"><td v-for="c in columns(rows)" :key="c" class="td whitespace-nowrap chiffres">{{ cell(r[c]) }}</td></tr>
          <tr v-if="!rows.length"><td class="td text-attenue">Aucune paie pour cette sélection.</td></tr>
        </tbody></table></div>
    </section>
  </div>
</template>
