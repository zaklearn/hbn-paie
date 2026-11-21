/** Code couleur commun aux deux modules (US-40) : un seul composant StatusBadge. */
export type BadgeKind = 'neutre' | 'calculee' | 'succes' | 'retard' | 'danger' | 'avenir' | 'remplacee'

export const BADGE_STYLES: Record<BadgeKind, string> = {
  neutre: 'bg-[#EEF0F3] text-[#3F4754]',
  calculee: 'bg-[#E6EEFF] text-[#1D4ED8]',
  succes: 'bg-[#E3F4E8] text-[#166534]',
  retard: 'bg-[#FDECD8] text-[#8A3A00]',
  danger: 'bg-[#FDE7E5] text-[#B42318]',
  avenir: 'bg-white text-[#5B6472] border border-dashed border-[#9AA3AF]',
  remplacee: 'bg-[#EFEAFB] text-[#5B3FA8]',
}

/** Libellés d'origine des deux applications -> famille de couleur. */
const BY_STATUS: Record<string, BadgeKind> = {
  brouillon: 'neutre', Brouillon: 'neutre', 'Non payé': 'neutre',
  calculee: 'calculee', Calculée: 'calculee',
  cloturee: 'succes', Clôturée: 'succes', 'Payé – à temps': 'succes', 'Payé – avance': 'succes',
  'Payé – retard': 'retard',
  en_retard: 'danger', 'En retard': 'danger',
  a_saisir: 'avenir', 'À saisir': 'avenir', a_venir: 'avenir', 'À venir': 'avenir',
  remplacee: 'remplacee', 'Remplacée (rectifiée)': 'remplacee',
}

export function badgeKind(status: string): BadgeKind {
  return BY_STATUS[status] ?? 'neutre'
}

const LABELS: Record<string, string> = {
  brouillon: 'Brouillon', calculee: 'Calculée', cloturee: 'Clôturée', remplacee: 'Remplacée (rectifiée)',
  a_saisir: 'À saisir', a_venir: 'À venir', en_retard: 'En retard',
}

export function statusLabel(status: string): string {
  return LABELS[status] ?? status
}
