<script setup lang="ts">
import { computed } from 'vue'
import { BADGE_STYLES, badgeKind, statusLabel } from '@/shared/statuses'

const props = defineProps<{ status: string; label?: string }>()
const classes = computed(() => BADGE_STYLES[badgeKind(props.status)])
</script>

<template>
  <span :class="['inline-block whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold', classes]"
        data-testid="status-badge">{{ label ?? statusLabel(status) }}</span>
</template>
