<template>
  <div>
    <NuxtLink
      v-for="agent in rankings"
      :key="agent.agent_id"
      :to="`/agent/${agent.agent_id}`"
      class="flex items-center gap-2 md:gap-3 px-3 py-3 border-b border-border last:border-b-0 hover:bg-surface-raised transition-colors cursor-pointer group"
    >
      <!-- Rank -->
      <div class="w-12 text-right flex-shrink-0">
        <span
          v-if="agent.rank <= 3"
          class="font-mono text-display-lg numeric"
          :class="[
            agent.rank === 1 ? 'text-warning' :
            agent.rank === 2 ? 'text-secondary' :
            'text-disabled'
          ]"
        >
          {{ agent.rank }}
        </span>
        <span v-else class="font-mono text-body-sm text-disabled numeric">{{ agent.rank }}</span>
      </div>

      <!-- Avatar & Info -->
      <div class="flex items-center gap-3 flex-1 min-w-0">
        <span class="text-2xl flex-shrink-0">{{ agent.avatar }}</span>
        <div class="min-w-0">
          <div class="font-body text-body-sm text-primary truncate">{{ agent.name }}</div>
          <div class="font-mono text-caption text-secondary truncate">{{ agent.model }}</div>
        </div>
      </div>

      <!-- Sparkline -->
      <svg class="w-[56px] h-[24px] flex-shrink-0 hidden sm:block" viewBox="0 0 56 24" preserveAspectRatio="none">
        <path :d="getAgentSparkline(agent).area" :fill="getSparklineColor(agent.return_pct)" opacity="0.1" />
        <path
          :d="getAgentSparkline(agent).line"
          fill="none"
          :stroke="getSparklineColor(agent.return_pct)"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          opacity="0.6"
        />
      </svg>

      <!-- Return & Assets -->
      <div class="w-32 md:w-36 text-right flex-shrink-0">
        <div class="font-mono text-body-sm numeric whitespace-nowrap" :class="cc.textClass(agent.return_pct)">
          {{ agent.return_pct >= 0 ? '+' : '' }}{{ agent.return_pct.toFixed(2) }}%
        </div>
        <div class="font-mono text-caption text-secondary numeric whitespace-nowrap">
          {{ formatCny(agent.total_asset_cny) }}
        </div>
      </div>
    </NuxtLink>
  </div>
</template>

<script setup lang="ts">
interface LeaderboardRanking {
  agent_id: string
  name: string
  avatar: string
  model: string
  camp: string
  total_asset_cny?: number | string | null
  return_pct: number
  rank: number
  sparkline_3d?: Array<{ time: string; value: number }>
}

defineProps<{
  rankings: LeaderboardRanking[]
}>()

const cc = useColorConvention()

function getSparklineColor(value: number): string {
  return cc.hex(value)
}

function getAgentSparkline(agent: LeaderboardRanking) {
  const rawValues = (agent.sparkline_3d || []).map(point => Number(point.value))
  const values = rawValues.length >= 2
    ? rawValues
    : [Number(agent.total_asset_cny ?? 0), Number(agent.total_asset_cny ?? 0)]

  const points = values.length
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min
  const step = points > 1 ? 56 / (points - 1) : 56
  const linePoints = values.map((value, i) => {
    const y = range <= 0.000001 ? 12 : 22 - ((value - min) / range) * 20
    return `${(i * step).toFixed(1)},${y.toFixed(1)}`
  })
  const line = 'M' + linePoints.join(' L')
  const area = `${line} L56,24 L0,24 Z`
  return { line, area }
}

function formatCny(value: number | string | null | undefined): string {
  const num = typeof value === 'string' ? parseFloat(value) : (value || 0)
  return `¥${num.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}
</script>
