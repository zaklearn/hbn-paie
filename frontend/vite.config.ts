import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// Servie à la racine « / » de paie.hbnfactory.cloud (aucun base path codé en dur).
export default defineConfig({
  plugins: [vue()],
  base: '/',
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: { proxy: { '/api': 'http://localhost:8000' } },
  build: { outDir: 'dist', sourcemap: false },
  test: { environment: 'jsdom', include: ['tests/unit/**/*.spec.ts'] },
})
