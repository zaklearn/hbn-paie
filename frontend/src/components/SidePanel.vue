<script setup lang="ts">
defineProps<{ open: boolean; title: string }>()
const emit = defineEmits<{ (e: 'close'): void }>()
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-30 flex justify-end bg-[rgba(20,33,61,.25)]" @click.self="emit('close')"
       @keydown.esc="emit('close')">
    <aside role="dialog" aria-modal="true" :aria-label="title"
           class="flex h-full w-full max-w-3xl flex-col overflow-y-auto bg-white shadow-xl">
      <header class="flex items-center justify-between gap-3 border-b border-bordure px-5 py-3">
        <h2 class="m-0 text-lg font-semibold">{{ title }}</h2>
        <button type="button" class="btn-contour" aria-label="Fermer" @click="emit('close')">✕</button>
      </header>
      <div class="flex-1 p-5"><slot /></div>
    </aside>
  </div>
</template>
