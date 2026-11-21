/**
 * Affichage des montants reçus de l'API (chaînes décimales exactes) au format français.
 * AUCUN calcul ni arrondi (R0) : pure mise en forme de texte, comme `formatting.fmt_money` (espace
 * des milliers, virgule décimale). Les montants de paie arrivent déjà arrondis par le noyau.
 */
const NBSP = ' '

function groupDigits(int: string): string {
  return int.replace(/\B(?=(\d{3})+(?!\d))/g, NBSP)
}

export function fmtMoney(value: string | number | null | undefined, opts: { decimals?: boolean } = {}): string {
  if (value === null || value === undefined || value === '') return '—'
  const text = String(value)
  const negative = text.startsWith('-')
  const [intPart, frac = ''] = (negative ? text.slice(1) : text).split('.')
  const decimals = opts.decimals ?? true
  let out = groupDigits(intPart)
  if (decimals) out += ',' + (frac + '00').slice(0, Math.max(2, frac.length))
  else if (frac && /[1-9]/.test(frac)) out += ',' + frac
  return (negative ? '− ' : '') + out
}

/** Montants entiers DH de la trésorerie : « 2 500 DH ». */
export function fmtDh(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return fmtMoney(String(value), { decimals: false }) + ' DH'
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}/${y}`
}

export const MOIS_FR = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre',
  'Octobre', 'Novembre', 'Décembre']

export function periodLabel(year: number, month: number): string {
  return `${MOIS_FR[month - 1]} ${year}`
}

/** Saisie française (« 5 436,51 ») -> chaîne décimale pour l'API (« 5436.51 »). Texte seulement. */
export function toDecimalString(input: string): string {
  const t = input.replace(/[\s  ]/g, '').replace(',', '.')
  return t === '' ? '0' : t
}

export function fromDecimalString(value: string): string {
  return value.replace('.', ',')
}
