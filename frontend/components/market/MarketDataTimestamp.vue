<template>
  <div class="text-[11px] text-tertiary tabular-nums">
    行情时间 {{ formattedTimestamp }}
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  timestamp?: string | null
}>()

const formattedTimestamp = computed(() => {
  if (!props.timestamp) return '加载中'

  const date = new Date(props.timestamp)
  if (Number.isNaN(date.getTime())) return '未知'

  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
})
</script>
