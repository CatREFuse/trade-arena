<template>
  <div v-if="props.participantCount > 0" class="grid grid-cols-2 md:grid-cols-4 gap-4">
    <div class="card-raised">
      <div class="label mb-2">PARTICIPANTS</div>
      <div class="font-mono type-display-lg numeric text-display">{{ props.participantCount }}</div>
    </div>
    <div class="card-raised">
      <div class="label mb-2">POSITIVE</div>
      <div class="font-mono type-display-lg numeric text-accent">{{ positiveCount }}</div>
    </div>
    <div class="card-raised">
      <div class="label mb-2">AVG RETURN</div>
      <div class="font-mono type-display-lg numeric" :class="cc.textClass(avgReturn)">
        {{ avgReturn >= 0 ? '+' : '' }}{{ avgReturn.toFixed(2) }}%
      </div>
    </div>
    <div class="card-raised">
      <div class="label mb-2">TOP RETURN</div>
      <div class="font-mono type-display-lg numeric" :class="cc.textClass(topReturn)">
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
  total_asset_cny?: number | string | null
  total_asset_usd?: number | string | null
  return_pct: number
  rank: number
}

const props = defineProps<{
  rankings: LeaderboardRanking[]
  participantCount: number
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
