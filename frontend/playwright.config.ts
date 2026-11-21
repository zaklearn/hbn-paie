import { defineConfig } from '@playwright/test'

// E2E de DEV uniquement (projet compose hbn-paie-dev) : application servie par l'API de dev.
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  workers: 1,
  reporter: [['list']],
  use: { baseURL: process.env.E2E_BASE_URL ?? 'http://api:8000', locale: 'fr-FR', timezoneId: 'Africa/Casablanca' },
})
