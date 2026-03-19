<template>
  <div v-if="props.rankings.length" class="grid grid-cols-2 md:grid-cols-4 gap-3">
    <div class="rounded-2xl bg-overlay-2 px-4 py-3">
      <div class="text-[10px] uppercase tracking-widest text-tertiary">选手数</div>
      <div class="mt-1 text-xl font-bold text-main tabular-nums">{{ props.rankings.length }}</div>
    </div>
    <div class="rounded-2xl bg-overlay-2 px-4 py-3">
      <div class="text-[10px] uppercase tracking-widest text-tertiary">正收益</div>
      <div class="mt-1 text-xl font-bold text-main tabular-nums">{{ positiveCount }}</div>
    </div>
    <div class="rounded-2xl bg-overlay-2 px-4 py-3">
      <div class="text-[10px] uppercase tracking-widest text-tertiary">平均收益</div>
      <div class="mt-1 text-xl font-bold tabular-nums" :class="cc.textClass(avgReturn)">
        {{ avgReturn >= 0 ? '+' : '' }}{{ avgReturn.toFixed(2) }}%
      </div>
    </div>
    <div class="rounded-2xl bg-overlay-2 px-4 py-3">
      <div class="text-[10px] uppercase tracking-widest text-tertiary">最高收益</div>
      <div class="mt-1 text-xl font-bold tabular-nums" :class="cc.textClass(topReturn)">
        {{ topReturn >= 0 ? '+' : '' }}{{ topReturn.toFixed(2) }}%
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface LeaderboardRanking {
  agent_id: string
  name: string
  avatar: string
  model: string
  camp: string
  total_asset_usd: number | string
  return_pct: number
  rank: number
  us_asset?: number | string | null
  cn_asset_usd?: number | string | null
}

const props = defineProps<{
  rankings: LeaderboardRanking[]
}>()

const cc = useColorConvention()

const positiveCount = computed(() => props.rankings.filter(r => r.return_pct >= 0).length)
const avgReturn = computed(() => {
  if (!props.rankings.length) return 0
  return props.rankings.reduce((sum, r) => sum + r.return_pct, 0) / props.rankings.length
})
const topReturn = computed(() => {
  if (!props.rankings.length) return 0
  return Math.max(...props.rankings.map(r => r.return_pct))
})
</script>
