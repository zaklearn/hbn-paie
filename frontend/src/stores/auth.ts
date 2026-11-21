import { defineStore } from 'pinia'
import { http } from '@/shared/services/http'
import type { User } from '@/shared/types'

export const useAuthStore = defineStore('auth', {
  state: () => ({ user: null as User | null, checked: false }),
  getters: {
    isAdmin: (s) => s.user?.role === 'superadmin',
    roleLabel: (s) => (s.user ? `${s.user.username} · ${s.user.role}` : ''),
  },
  actions: {
    async fetchMe() {
      try {
        this.user = (await http.get<User>('/api/auth/moi')).data
      } catch {
        this.user = null
      } finally {
        this.checked = true
      }
      return this.user
    },
    async login(username: string, password: string) {
      this.user = (await http.post<User>('/api/auth/connexion', { username, password })).data
      this.checked = true
    },
    async logout() {
      try { await http.post('/api/auth/deconnexion') } finally { this.user = null }
    },
  },
})
