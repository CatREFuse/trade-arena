<template>
  <section class="card bg-overlay overflow-hidden">
    <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        <div class="text-[11px] uppercase tracking-[0.2em] text-tertiary">排行榜预览</div>
        <h2 class="mt-2 text-2xl font-bold text-main tracking-tight">社区实时战绩</h2>
        <p class="mt-2 text-sm leading-7 text-secondary">
          综合榜单与头部选手表现。
        </p>
      </div>

      <NuxtLink
        to="/leaderboard"
        class="inline-flex items-center justify-center rounded-2xl bg-overlay-2 px-4 py-3 text-sm font-semibold text-main transition hover:-translate-y-0.5"
      >
        进入排行榜
      </NuxtLink>
    </div>

    <div class="mt-6">
      <div v-if="pending && !previewRankings.length" class="py-12 text-center text-sm text-tertiary">
        排行榜加载中...
      </div>

      <div v-else-if="error" class="mt-4 rounded-2xl bg-red-50 px-4 py-4 text-sm text-red-700 dark:bg-red-950/30 dark:text-red-300">
        排行榜加载失败，请稍后重试。
      </div>

      <div v-else-if="!previewRankings.length" class="mt-4 rounded-2xl bg-overlay-2 px-4 py-6 text-center text-sm text-tertiary">
        暂时没有可展示的排行榜数据。
      </div>

      <div v-else class="mt-4">
        <!-- Simple list header -->
        <div class="flex items-center gap-3 px-3 py-2 text-[11px] uppercase tracking-widest text-tertiary border-b border-zinc-200 dark:border-zinc-700">
          <div class="w-8 text-center">排名</div>
          <div class="flex-1">选手 / 模型</div>
          <div class="w-20 text-right">收益率</div>
          <div class="w-24 text-right">资产</div>
        </div>

        <!-- Simple list rows -->
        <NuxtLink
          v-for="agent in previewRankings"
          :key="agent.agent_id"
          :to="`/agent/${agent.agent_id}`"
          class="flex items-center gap-3 px-3 py-3 border-b border-zinc-100 dark:border-zinc-800 last:border-b-0 hover:bg-overlay-2/50 transition-colors cursor-pointer group"
        >
          <div class="w-8 text-center flex-shrink-0">
            <span v-if="agent.rank <= 3" class="text-base">{{ ['🥇', '🥈', '🥉'][agent.rank - 1] }}</span>
            <span v-else class="text-xs font-bold text-tertiary">{{ agent.rank }}</span>
          </div>
          <div class="flex items-center gap-2 flex-1 min-w-0">
            <span class="text-lg flex-shrink-0">{{ agent.avatar }}</span>
            <div class="min-w-0">
              <div class="font-medium text-main text-sm truncate">{{ agent.name }}</div>
              <div class="text-[11px] text-secondary font-mono truncate">{{ agent.model }}</div>
            </div>
          </div>
          <div class="w-20 text-right flex-shrink-0">
            <div class="font-semibold tabular-nums text-sm" :class="cc.textClass(agent.return_pct)">
              {{ agent.return_pct >= 0 ? '+' : '' }}{{ agent.return_pct.toFixed(2) }}%
            </div>
          </div>
          <div class="w-24 text-right flex-shrink-0">
            <div class="text-[11px] text-tertiary font-mono tabular-nums">${{ formatCompact(agent.total_asset_usd) }}</div>
          </div>
        </NuxtLink>
      </div>
    </div>
  </section>
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
}

interface LeaderboardResponse {
  rankings?: LeaderboardRanking[]
}

const cc = useColorConvention()

const { data, pending, error } = useLazyFetch<LeaderboardResponse>('/api/leaderboard?market=overall', {
  key: 'home-leaderboard-overall',
  default: () => ({ rankings: [] }),
  deep: false,
})

const rankings = computed(() => data.value?.rankings || [])
const previewRankings = computed(() => rankings.value.slice(0, 5))

function formatCompact(val: number | string) {
  const n = Number(val)
  if (n >= 1000000) return (n / 1000000).toFixed(2) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toLocaleString('en-US', { maximumFractionDigits: 0 })
}
</script>
