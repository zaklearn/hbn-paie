<script setup lang="ts">
import type { Issue } from '@/shared/types'
defineProps<{ issues: Issue[] }>()
</script>

<template>
  <ul v-if="issues.length" class="m-0 flex list-none flex-col gap-2 p-0">
    <li v-for="(i, k) in issues" :key="k"
        :class="['rounded-lg px-3 py-2 text-[13px]', i.level === 'erreur' ? 'bg-[#FDE7E5] text-[#8E1B12]' : 'bg-alerte-fond text-alerte-texte']">
      <strong>{{ i.level === 'erreur' ? 'Erreur' : 'Avertissement' }} :</strong> {{ i.message }}
    </li>
  </ul>
</template>
