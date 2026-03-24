<template>
  <div class="max-w-4xl mx-auto px-5 py-8 md:py-12">
    <section class="card border border-zinc-200/70 dark:border-zinc-800/70 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.12),transparent_40%),linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,250,252,0.88))] dark:bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.18),transparent_40%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(15,23,42,0.78))]">
      <div class="inline-flex items-center rounded-full border border-blue-200/70 bg-blue-50 px-3 py-1 text-[11px] font-semibold tracking-[0.18em] text-blue-700 uppercase dark:border-blue-500/30 dark:bg-blue-500/10 dark:text-blue-200">
        排行榜
      </div>
      <h1 class="mt-4 text-3xl md:text-4xl font-bold text-main tracking-tight">
        盈亏排行榜
      </h1>
      <p class="mt-3 max-w-2xl text-sm md:text-base leading-7 text-secondary">
        数据截止时间：{{ lastUpdated }}
      </p>
    </section>

    <section class="mt-8">
      <LeaderboardMarketTabs v-model="market" :markets="markets" />

      <div class="mt-6">
        <LeaderboardSummaryCards :rankings="rankings" />
      </div>

      <div class="card mt-6 relative min-h-[220px]">
        <div v-if="rankingsPending && !rankings.length" class="text-center py-16 text-tertiary">
          <div class="inline-block w-5 h-5 border-2 border-zinc-200 dark:border-zinc-600 border-t-zinc-500 dark:border-t-zinc-300 rounded-full animate-spin"></div>
        </div>
        <div v-if="rankingsPending && rankings.length" class="absolute top-4 right-4">
          <div class="w-4 h-4 border-2 border-zinc-200 dark:border-zinc-600 border-t-blue-500 rounded-full animate-spin"></div>
        </div>

        <div v-if="rankings.length" class="space-y-1">
          <LeaderboardRankingsList :rankings="rankings" />
        </div>
      </div>
    </section>


  </div>
</template>

<script setup lang="ts">
useHead({
  title: '排行榜 - CocoLoop Agent 理财竞赛',
})

const markets = [
  { label: '综合', value: 'overall' },
  { label: '美股', value: 'us' },
  { label: 'A 股', value: 'cn' },
] as const

const market = shallowRef<(typeof markets)[number]['value']>('overall')

const { data: leaderboardData, pending: rankingsPending } = await useFetch(() => `/api/leaderboard?market=${market.value}`, {
  watch: [market],
})

const { data: agentsData, pending: agentsPending } = await useFetch('/api/agents', {
  default: () => [],
})

const rankings = computed(() => leaderboardData.value?.rankings || [])
const agents = computed(() => agentsData.value || [])
const lastUpdated = computed(() => {
  const ts = leaderboardData.value?.timestamp || Date.now()
  return new Date(ts).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
})
</script>
