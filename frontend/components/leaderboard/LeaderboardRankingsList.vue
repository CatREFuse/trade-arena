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
}

defineProps<{
  rankings: LeaderboardRanking[]
}>()

const cc = useColorConvention()
const sparklineCache: Record<string, { line: string; area: string }> = {}

function hashSeed(str: string) {
  let h = 0
  for (let i = 0; i < str.length; i++) h = ((h << 5) - h + str.charCodeAt(i)) | 0
  return Math.abs(h)
}

function getAgentSparkline(agent: LeaderboardRanking) {
  if (sparklineCache[agent.agent_id]) return sparklineCache[agent.agent_id]

  const seed = hashSeed(agent.agent_id)
  const trend = agent.return_pct >= 0 ? 1 : -1
  const points = 16
  const values: number[] = []
  let value = 12 + (seed % 6)

  for (let i = 0; i < points; i++) {
    const noise = (Math.sin(seed * 7.3 + i * 2.7) * 0.5 + 0.5) * 6 - 3
    const drift = trend * (i / points) * 5
    value = Math.max(2, Math.min(22, value + noise + drift * 0.4))
    values.push(value)
  }

  const step = 56 / (points - 1)
  const linePoints = values.map((y, i) => `${(i * step).toFixed(1)},${(24 - y).toFixed(1)}`)
  const line = 'M' + linePoints.join(' L')
  const area = `${line} L56,24 L0,24 Z`
  sparklineCache[agent.agent_id] = { line, area }
  return { line, area }
}
</script>
