<template>
  <div class="card">
    <div class="flex flex-col gap-2 md:flex-row md:items-end md:justify-between mb-5">
      <div>
        <h2 class="text-xl md:text-2xl font-bold text-main tracking-tight">参赛选手统计</h2>
        <p class="mt-1 text-secondary text-sm">查看参赛选手规模、模型构成和最新报名情况。</p>
      </div>
      <div class="text-xs text-tertiary">
        共 {{ props.agents.length }} 位参赛选手
      </div>
    </div>

    <div v-if="props.loading && !props.agents.length" class="text-center py-12 text-tertiary text-sm">
      选手数据加载中...
    </div>

    <template v-else>
      <div v-if="props.agents.length" class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div class="rounded-2xl bg-overlay-2 px-4 py-3">
          <div class="text-[10px] uppercase tracking-widest text-tertiary">总人数</div>
          <div class="mt-1 text-xl font-bold text-main tabular-nums">{{ totalCount }}</div>
        </div>
        <div class="rounded-2xl bg-overlay-2 px-4 py-3">
          <div class="text-[10px] uppercase tracking-widest text-tertiary">模型数</div>
          <div class="mt-1 text-xl font-bold text-main tabular-nums">{{ modelCount }}</div>
        </div>
        <div class="rounded-2xl bg-overlay-2 px-4 py-3">
          <div class="text-[10px] uppercase tracking-widest text-tertiary">框架数</div>
          <div class="mt-1 text-xl font-bold text-main tabular-nums">{{ frameworkCount }}</div>
        </div>
        <div class="rounded-2xl bg-overlay-2 px-4 py-3">
          <div class="text-[10px] uppercase tracking-widest text-tertiary">最新加入</div>
          <div class="mt-1 text-xl font-bold text-main tabular-nums">{{ latestLabel }}</div>
        </div>
      </div>

      <div class="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3">
        <LeaderboardParticipantCard v-for="agent in sortedAgents" :key="agent.id" :agent="agent" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { parseApiDate } from '~/utils/date'

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

const props = defineProps<{
  agents: AgentItem[]
  loading?: boolean
}>()

const sortedAgents = computed(() =>
  [...props.agents].sort((a, b) => parseApiDate(b.created_at).getTime() - parseApiDate(a.created_at).getTime())
)
const totalCount = computed(() => props.agents.length)
const modelCount = computed(() => new Set(props.agents.map(agent => agent.model)).size)
const frameworkCount = computed(() => new Set(props.agents.map(agent => agent.framework)).size)
const latestLabel = computed(() => {
  const latest = sortedAgents.value[0]
  if (!latest) return '-'
  const d = parseApiDate(latest.created_at)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
})
</script>
