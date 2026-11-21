import { defineStore } from 'pinia'

export interface Toast { id: number; kind: 'succes' | 'erreur' | 'info'; text: string }
let next = 1

export const useUiStore = defineStore('ui', {
  state: () => ({ readOnly: false, toasts: [] as Toast[] }),
  actions: {
    notify(text: string, kind: Toast['kind'] = 'succes') {
      const id = next++
      this.toasts.push({ id, kind, text })
      setTimeout(() => { this.toasts = this.toasts.filter((t) => t.id !== id) }, 6000)
    },
    setReadOnly(value: boolean) { this.readOnly = value },
  },
})
