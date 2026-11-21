import { defineStore } from 'pinia'
import { periodLabel } from '@/shared/format'

/** Barre de contexte partagée (US-40) : période et salarié, persistés dans l'URL (?periode=2026-11&salarie=0001). */
export function parsePeriod(value: unknown): { year: number; month: number } | null {
  const m = /^(\d{4})-(\d{2})$/.exec(String(value ?? ''))
  if (!m) return null
  const year = Number(m[1]); const month = Number(m[2])
  return month >= 1 && month <= 12 ? { year, month } : null
}

export function formatPeriod(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, '0')}`
}

export function shiftPeriod(year: number, month: number, delta: number): { year: number; month: number } {
  const index = year * 12 + (month - 1) + delta
  return { year: Math.floor(index / 12), month: (index % 12) + 1 }
}

export const useContextStore = defineStore('context', {
  state: () => {
    const now = new Date()
    return { year: now.getFullYear(), month: now.getMonth() + 1, salarie: '' as string }
  },
  getters: {
    periode: (s) => formatPeriod(s.year, s.month),
    label: (s) => periodLabel(s.year, s.month),
    query: (s): Record<string, string> => {
      const q: Record<string, string> = { periode: formatPeriod(s.year, s.month) }
      if (s.salarie) q.salarie = s.salarie
      return q
    },
  },
  actions: {
    fromQuery(query: Record<string, unknown>) {
      const p = parsePeriod(query.periode)
      if (p) { this.year = p.year; this.month = p.month }
      this.salarie = typeof query.salarie === 'string' ? query.salarie : ''
    },
    shift(delta: number) {
      const p = shiftPeriod(this.year, this.month, delta)
      this.year = p.year; this.month = p.month
    },
    setSalarie(matricule: string) { this.salarie = matricule },
  },
})
