<template>
  <div class="font-mono text-caption text-disabled">
    <span class="text-secondary">MARKET TIME</span> {{ formattedTimestamp }}
  </div>
</template>

<script setup lang="ts">
import { parseApiDate } from '~/utils/date'

const props = defineProps<{
  timestamp?: string | null
}>()

const formattedTimestamp = computed(() => {
  if (!props.timestamp) return '加载中...'

  const date = parseApiDate(props.timestamp)
  if (Number.isNaN(date.getTime())) return '--'

  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).toUpperCase()
})
</script>
