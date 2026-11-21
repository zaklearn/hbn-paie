import axios, { AxiosError } from 'axios'
import { env } from '@/config/env'

/** Client HTTP unique (convention SmartCompta). Cookie de session httpOnly envoyé automatiquement. */
export const http = axios.create({ baseURL: env.apiBase, withCredentials: true, timeout: 30_000 })

type Handlers = { onUnauthorized?: () => void; onStorageError?: () => void }
const handlers: Handlers = {}
export function setHttpHandlers(h: Handlers) { Object.assign(handlers, h) }

http.interceptors.response.use(
  (r) => r,
  (error: AxiosError) => {
    const status = error.response?.status
    if (status === 401 && !String(error.config?.url ?? '').includes('/api/auth/')) handlers.onUnauthorized?.()
    if (!error.response || status === 503 || (status !== undefined && status >= 500)) handlers.onStorageError?.()
    return Promise.reject(error)
  },
)

/** Message d'erreur lisible (détail renvoyé par l'API, en français). */
export function errorMessage(e: unknown): string {
  const err = e as AxiosError<{ detail?: unknown; issues?: { message: string }[] }>
  const data = err.response?.data
  if (data?.issues?.length) return data.issues.map((i) => i.message).join(' ')
  if (typeof data?.detail === 'string') return data.detail
  if (Array.isArray(data?.detail)) return 'Saisie invalide : vérifiez les champs.'
  return err.message || 'Erreur inattendue.'
}

export async function download(url: string, params?: Record<string, unknown>) {
  const r = await http.get(url, { params, responseType: 'blob' })
  const cd = String(r.headers['content-disposition'] ?? '')
  const name = /filename="([^"]+)"/.exec(cd)?.[1] ?? 'fichier'
  const href = URL.createObjectURL(r.data as Blob)
  const a = document.createElement('a')
  a.href = href
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(href), 10_000)
}
