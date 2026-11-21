import { defineStore } from 'pinia'
import { http } from '@/shared/services/http'
import type { Employee } from '@/shared/types'

export const useEmployeesStore = defineStore('employees', {
  state: () => ({ list: [] as Employee[], loaded: false }),
  getters: {
    byMatricule: (s) => (m: string) => s.list.find((e) => e.matricule === m) ?? null,
    byId: (s) => (id: number) => s.list.find((e) => e.id === id) ?? null,
  },
  actions: {
    async load(force = false) {
      if (this.loaded && !force) return this.list
      this.list = (await http.get<Employee[]>('/api/paie/salaries')).data
      this.loaded = true
      return this.list
    },
  },
})
