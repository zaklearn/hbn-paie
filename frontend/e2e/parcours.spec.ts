import { expect, test, type Page } from '@playwright/test'

// E2E de DEV (S4) : parcours « déclarer → payer → saisir → calculer → clôturer » sur la démo fictive
// d'origine (juillet–septembre 2026 clôturés), puis contrôle du rôle « user » et captures des 5 écrans.
const ADMIN = { username: 'admin', password: process.env.E2E_ADMIN_PW ?? '' }
const USER = { username: 'lecteur', password: process.env.E2E_USER_PW ?? '' }
const CAPTURES = process.env.E2E_CAPTURES ?? 'test-results'

async function login(page: Page, who: { username: string; password: string }) {
  await page.goto('/connexion')
  await page.getByTestId('login-username').fill(who.username)
  await page.getByTestId('login-password').fill(who.password)
  await page.getByTestId('login-submit').click()
  await expect(page.getByTestId('role')).toContainText(who.username)
}

test.describe.configure({ mode: 'serial' })

test('parcours complet octobre 2026 (superadmin)', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await login(page, ADMIN)

  // 1. Déclarer octobre 2026 en trésorerie
  await page.goto('/tresorerie?periode=2026-10&vue=mois')
  await expect(page.getByTestId('periode')).toHaveText('Octobre 2026')
  await page.getByTestId('declarer').click()
  await expect(page.getByTestId('ligne-echeance')).toHaveCount(4)

  // 2. Payer le 1er versement (dialogue de confirmation, statut calculé par l'API)
  await page.getByTestId('payer').first().click()
  const pay = page.getByRole('dialog', { name: 'Confirmer le paiement' })
  await expect(pay.getByText('Statut calculé')).toBeVisible()
  await pay.getByRole('button', { name: 'Confirmer' }).click()
  await expect(page.getByTestId('ligne-echeance').first()).toContainText('Payé – retard')
  await page.screenshot({ path: `${CAPTURES}/2-tresorerie-mois-1280.png`, fullPage: true })

  // 3. Saisir (préremplie depuis septembre) puis calculer
  await page.goto('/paie?periode=2026-10&salarie=0001')
  await expect(page.getByTestId('bandeau-prerempli')).toContainText('Septembre 2026')
  await expect(page.getByTestId('saisie-salaire_base')).toHaveValue('5436,51')
  await expect(page.getByTestId('net-a-payer')).toContainText('7')           // aperçu calculé par l'API
  await page.getByTestId('calculer').click()
  await expect(page.getByTestId('controles')).toBeVisible()
  await expect(page.getByTestId('controles')).toContainText('Versements incomplets')

  // 4. Clôturer (avertissements de trésorerie à confirmer, non bloquants)
  await page.getByTestId('cloturer').click()
  const close = page.getByRole('dialog', { name: 'Clôturer et générer le bulletin' })
  await close.getByTestId('confirmer-avertissements').check()
  await close.getByTestId('confirmer-cloture').check()
  await close.getByRole('button', { name: 'Clôturer' }).click()
  await expect(page.getByRole('button', { name: 'Télécharger le bulletin' })).toBeVisible()
  await expect(page.getByTestId('carte-paie').first()).toContainText('Clôturée')
  await page.screenshot({ path: `${CAPTURES}/3-paie-du-mois-1280.png`, fullPage: true })

  // Captures : tableau de bord et fiche salarié (plan de versement)
  await page.goto('/?periode=2026-10')
  await expect(page.getByTestId('ligne-salarie')).toHaveCount(1)
  await page.screenshot({ path: `${CAPTURES}/1-tableau-de-bord-1280.png`, fullPage: true })
  await page.goto('/salaries?periode=2026-10')
  await page.getByRole('button', { name: 'Ouvrir' }).first().click()
  await page.getByRole('tab', { name: 'Plan de versement' }).click()
  await expect(page.getByText('Plan de versement mensuel')).toBeVisible()
  await page.screenshot({ path: `${CAPTURES}/4-fiche-salarie-1280.png`, fullPage: true })
})

test('trésorerie au téléphone (390 px)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await login(page, ADMIN)
  await page.goto('/tresorerie?periode=2026-10&vue=a-venir')
  await expect(page.getByRole('tab', { name: 'À venir' })).toHaveAttribute('aria-selected', 'true')
  const width = await page.evaluate(() => document.documentElement.scrollWidth)
  expect(width).toBeLessThanOrEqual(390)                                      // aucun défilement horizontal de page
  await page.screenshot({ path: `${CAPTURES}/5-tresorerie-mobile-390.png`, fullPage: true })
  await page.goto('/tresorerie?periode=2026-10&vue=mois')
  await expect(page.getByRole('button', { name: 'Dévalider' }).first()).toBeVisible()  // vue en cartes
})

test('rôle « user » : boutons d’écriture absents', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await login(page, USER)
  await page.goto('/tresorerie?periode=2026-10&vue=mois')
  await expect(page.getByTestId('ligne-echeance')).toHaveCount(4)
  await expect(page.getByTestId('declarer')).toHaveCount(0)
  await expect(page.getByTestId('payer')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Dévalider' })).toHaveCount(0)
  await page.goto('/paie?periode=2026-11&salarie=0001')
  await expect(page.getByTestId('calculer')).toHaveCount(0)
  await expect(page.getByTestId('enregistrer')).toHaveCount(0)
  await page.goto('/salaries')
  await expect(page.getByTestId('nouveau-salarie')).toHaveCount(0)
  await expect(page.getByTestId('ligne-salarie').first()).toContainText('••••')
})
