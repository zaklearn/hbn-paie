<script setup lang="ts">
defineProps<{ label: string; value: string; hint?: string; progress?: number; hintClass?: string }>()
</script>

<template>
  <div class="carte p-[18px]">
    <div class="text-[13px] text-attenue">{{ label }}</div>
    <div class="mt-1.5 text-2xl font-bold chiffres" data-testid="kpi-value">{{ value }}</div>
    <div v-if="progress !== undefined" class="mt-2.5 h-1.5 rounded bg-ligne">
      <div class="h-1.5 rounded bg-primaire" :style="{ width: `${Math.min(100, Math.max(0, progress))}%` }" />
    </div>
    <div v-if="hint" :class="['mt-1 text-[13px]', hintClass ?? 'text-attenue']">{{ hint }}</div>
  </div>
</template>
