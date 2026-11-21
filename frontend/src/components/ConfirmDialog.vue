<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  open: boolean; title: string; confirmLabel?: string; busy?: boolean; disabled?: boolean
}>(), { confirmLabel: 'Confirmer', busy: false, disabled: false })
const emit = defineEmits<{ (e: 'confirm'): void; (e: 'cancel'): void }>()
const panel = ref<HTMLElement | null>(null)
watch(() => props.open, async (v) => { if (v) { await nextTick(); panel.value?.focus() } })
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-40 flex items-end justify-center bg-[rgba(20,33,61,.35)] p-4 sm:items-center"
       @keydown.esc="emit('cancel')">
    <div ref="panel" role="dialog" aria-modal="true" :aria-label="title" tabindex="-1"
         class="w-full max-w-md rounded-xl border border-[#C9D2E3] bg-white p-5 shadow-[0_8px_24px_rgba(20,33,61,.10)] outline-none">
      <div class="text-xs uppercase tracking-wide text-attenue">{{ title }}</div>
      <div class="mt-2"><slot /></div>
      <div class="mt-4 flex gap-2.5">
        <button type="button" class="btn-contour flex-1" @click="emit('cancel')">Annuler</button>
        <button type="button" class="btn-primaire flex-1" :disabled="busy || disabled" @click="emit('confirm')">
          {{ busy ? '…' : confirmLabel }}
        </button>
      </div>
    </div>
  </div>
</template>
