import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import StatusBadge from '@/components/StatusBadge.vue'
import { BADGE_STYLES, badgeKind } from '@/shared/statuses'

// Code couleur commun (S4 / US-40) : statuts d'origine des deux modules.
const EXPECTED: [string, string][] = [
  ['brouillon', '#EEF0F3'], ['Non payé', '#EEF0F3'], ['calculee', '#E6EEFF'], ['cloturee', '#E3F4E8'],
  ['Payé – à temps', '#E3F4E8'], ['Payé – retard', '#FDECD8'], ['En retard', '#FDE7E5'], ['a_saisir', 'border-dashed'],
  ['À venir', 'border-dashed'], ['remplacee', '#EFEAFB'],
]

describe('StatusBadge', () => {
  it.each(EXPECTED)('%s -> %s', (status, token) => {
    const w = mount(StatusBadge, { props: { status } })
    expect(w.get('[data-testid="status-badge"]').classes().join(' ')).toContain(token)
  })
  it('affiche le libellé d’origine', () => {
    expect(mount(StatusBadge, { props: { status: 'cloturee' } }).text()).toBe('Clôturée')
    expect(mount(StatusBadge, { props: { status: 'a_saisir' } }).text()).toBe('À saisir')
    expect(mount(StatusBadge, { props: { status: 'Payé – retard' } }).text()).toBe('Payé – retard')
  })
  it('un statut inconnu reste neutre', () => {
    expect(BADGE_STYLES[badgeKind('inconnu')]).toContain('#EEF0F3')
  })
})
