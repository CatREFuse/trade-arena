<template>
  <div>
    <NuxtLink
      v-for="agent in rankings"
      :key="agent.agent_id"
      :to="`/agent/${agent.agent_id}`"
      class="flex items-center gap-3 px-3 py-3 rounded-2xl border border-transparent md:transition-[transform,border-color,background-color] md:hover:-translate-y-0.5 md:hover:border-zinc-200 dark:md:hover:border-zinc-700 cursor-pointer group"
    >
      <div class="w-7 text-center flex-shrink-0">
        <span v-if="agent.rank <= 3" class="text-base">{{ ['🥇', '🥈', '🥉'][agent.rank - 1] }}</span>
        <span v-else class="text-xs font-bold text-tertiary">{{ agent.rank }}</span>
      </div>
      <div class="flex items-center gap-3 flex-1 min-w-0">
        <span class="text-2xl flex-shrink-0">{{ agent.avatar }}</span>
        <div class="min-w-0">
          <div class="font-bold text-main text-sm">{{ agent.name }}</div>
          <div class="text-[11px] text-secondary font-mono truncate">{{ agent.model }}</div>
        </div>
      </div>
      <svg class="w-[56px] h-[24px] flex-shrink-0 hidden sm:block" viewBox="0 0 56 24" preserveAspectRatio="none">
        <defs>
          <filter :id="'leaderboard-glow-' + agent.agent_id" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <path :d="getAgentSparkline(agent).area" :fill="cc.hex(agent.return_pct)" opacity="0.1" />
        <path
          :d="getAgentSparkline(agent).line"
          fill="none"
          :stroke="cc.hex(agent.return_pct)"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          opacity="0.5"
          :filter="'url(#leaderboard-glow-' + agent.agent_id + ')'"
        />
      </svg>
      <div class="text-right flex-shrink-0">
        <div class="font-bold tabular-nums text-sm" :class="cc.textClass(agent.return_pct)">
          {{ agent.return_pct >= 0 ? '+' : '' }}{{ agent.return_pct.toFixed(2) }}%
        </div>
        <div class="text-[11px] text-tertiary font-mono tabular-nums">{{ formatCny(agent.total_asset_cny ?? agent.total_asset_usd, { compact: true }) }}</div>
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
  total_asset_usd?: number | string | null
  return_pct: number
  rank: number
  sparkline_3d?: Array<{ time: string; value: number }>
}

defineProps<{
  rankings: LeaderboardRanking[]
}>()

const cc = useColorConvention()

function getAgentSparkline(agent: LeaderboardRanking) {
  const rawValues = (agent.sparkline_3d || []).map(point => Number(point.value))
  const values = rawValues.length >= 2
    ? rawValues
    : [Number(agent.total_asset_cny ?? agent.total_asset_usd ?? 0), Number(agent.total_asset_cny ?? agent.total_asset_usd ?? 0)]

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
</script>
