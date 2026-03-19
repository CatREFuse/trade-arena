<template>
  <NuxtLink
    :to="`/agent/${agent.id}`"
    class="card-item bg-overlay cursor-pointer group overflow-hidden"
  >
    <div class="flex items-center gap-3 mb-2">
      <span class="text-3xl flex-shrink-0">{{ agent.avatar }}</span>
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="font-bold text-main text-sm truncate">{{ agent.name }}</span>
          <span class="px-2 py-0.5 rounded-full text-[10px] font-medium flex-shrink-0 bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400">
            社区选手
          </span>
        </div>
        <div class="text-[11px] text-tertiary font-mono truncate">{{ agent.model }}</div>
      </div>
    </div>
    <div class="text-xs text-secondary truncate">{{ agent.style }}</div>
    <div class="mt-3 flex items-center justify-between gap-3 text-[11px] text-tertiary">
      <span class="font-mono">{{ agent.framework }}</span>
      <span>{{ formatDate(agent.created_at) }}</span>
    </div>
  </NuxtLink>
</template>

<script setup lang="ts">
interface AgentItem {
  id: string
  name: string
  avatar: string
  model: string
  camp: string
  style: string
  framework: string
  created_at: string
}

defineProps<{
  agent: AgentItem
}>()

function formatDate(dateStr: string) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>
