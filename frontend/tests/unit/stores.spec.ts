import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { formatPeriod, parsePeriod, shiftPeriod, useContextStore } from '@/stores/context'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

beforeEach(() => setActivePinia(createPinia()))

describe('barre de contexte', () => {
  it('lit et écrit la période dans l’URL', () => {
    const ctx = useContextStore()
    ctx.fromQuery({ periode: '2026-11', salarie: '0001' })
    expect(ctx.query).toEqual({ periode: '2026-11', salarie: '0001' })
    expect(ctx.label).toBe('Novembre 2026')
    ctx.fromQuery({ periode: '2026-13' })                 // invalide : période conservée
    expect(ctx.periode).toBe('2026-11')
    expect(ctx.salarie).toBe('')
  })
  it('passe d’une année à l’autre', () => {
    expect(shiftPeriod(2026, 12, 1)).toEqual({ year: 2027, month: 1 })
    expect(shiftPeriod(2026, 1, -1)).toEqual({ year: 2025, month: 12 })
    const ctx = useContextStore(); ctx.fromQuery({ periode: '2026-01' }); ctx.shift(-1)
    expect(ctx.periode).toBe('2025-12')
  })
  it('valide le format AAAA-MM', () => {
    expect(parsePeriod('2026-07')).toEqual({ year: 2026, month: 7 })
    expect(parsePeriod('2026-7')).toBeNull()
    expect(formatPeriod(2026, 3)).toBe('2026-03')
  })
})

describe('rôles et interface', () => {
  it('seul le superadmin écrit', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'zak', display_name: '', role: 'superadmin' }
    expect(auth.isAdmin).toBe(true)
    expect(auth.roleLabel).toBe('zak · superadmin')
    auth.user = { id: 2, username: 'lecteur', display_name: '', role: 'user' }
    expect(auth.isAdmin).toBe(false)
  })
  it('bandeau lecture seule et notifications', () => {
    const ui = useUiStore()
    ui.setReadOnly(true); expect(ui.readOnly).toBe(true)
    ui.notify('ok'); expect(ui.toasts).toHaveLength(1)
  })
})
