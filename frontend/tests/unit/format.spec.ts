import { describe, expect, it } from 'vitest'
import { fmtDate, fmtDh, fmtMoney, toDecimalString } from '@/shared/format'

const N = ' '

// R0 : mise en forme de texte uniquement, jamais d'arrondi ni de calcul.
describe('format des montants', () => {
  it('format français d’origine (espace des milliers, virgule)', () => {
    expect(fmtMoney('1146.57')).toBe(`1${N}146,57`)
    expect(fmtMoney('22099.53')).toBe(`22${N}099,53`)
    expect(fmtMoney('7000')).toBe(`7${N}000,00`)
    expect(fmtMoney('-0.08')).toBe('− 0,08')
  })
  it('ne tronque ni n’arrondit jamais', () => {
    expect(fmtMoney('3167.305')).toBe(`3${N}167,305`)
    expect(fmtMoney('0.1')).toBe('0,10')
  })
  it('montants entiers DH de la trésorerie', () => {
    expect(fmtDh(2500)).toBe(`2${N}500 DH`)
  })
  it('saisie française -> chaîne décimale pour l’API (sans conversion numérique)', () => {
    expect(toDecimalString('5 436,51')).toBe('5436.51')
    expect(toDecimalString('')).toBe('0')
    expect(fmtDate('2026-07-01')).toBe('01/07/2026')
  })
})
