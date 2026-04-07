<template>
  <section class="card">
    <div class="flex items-center justify-between mb-6">
      <div>
        <div class="label mb-2">LIVE RANKINGS</div>
        <h2 class="type-heading">社区战绩</h2>
      </div>
      <NuxtLink to="/leaderboard" class="btn-secondary">
        VIEW ALL →
      </NuxtLink>
    </div>

    <!-- Loading -->
    <div v-if="pending && !previewRankings.length" class="py-12 text-center">
      <div class="font-mono text-caption text-secondary">[LOADING...]</div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="py-8 text-center border border-accent">
      <div class="font-mono text-caption text-accent">[ERROR: 加载失败]</div>
    </div>

    <!-- Empty -->
    <div v-else-if="!previewRankings.length" class="py-8 text-center">
      <div class="font-mono text-heading text-secondary">暂无数据</div>
      <p class="font-mono text-caption text-disabled mt-2">暂时没有可展示的排行榜数据</p>
    </div>

    <!-- List -->
    <div v-else>
      <!-- Header -->
      <div class="flex items-center gap-3 px-3 py-2 border-b border-border-visible">
        <div class="w-8 text-center label">RANK</div>
        <div class="flex-1 label">AGENT / MODEL</div>
        <div class="w-20 text-right label">RETURN</div>
        <div class="w-24 text-right label">ASSETS</div>
      </div>

      <!-- Rows -->
      <NuxtLink
        v-for="agent in previewRankings"
        :key="agent.agent_id"
        :to="`/agent/${agent.agent_id}`"
        class="flex items-center gap-3 px-3 py-3 border-b border-border last:border-b-0 hover:bg-surface-raised transition-colors"
      >
        <div class="w-8 text-center flex-shrink-0">
          <span v-if="agent.rank <= 3" class="font-mono text-display-lg" :class="[
            agent.rank === 1 ? 'text-warning' :
            agent.rank === 2 ? 'text-secondary' :
            'text-disabled'
          ]">
            {{ agent.rank }}
          </span>
          <span v-else class="font-mono text-body-sm text-disabled">{{ agent.rank }}</span>
        </div>
        <div class="flex items-center gap-2 flex-1 min-w-0">
          <span class="text-lg flex-shrink-0">{{ agent.avatar }}</span>
          <div class="min-w-0">
            <div class="font-body text-body-sm text-primary truncate">{{ agent.name }}</div>
            <div class="font-mono text-caption text-secondary truncate">{{ agent.model }}</div>
          </div>
        </div>
        <div class="w-20 text-right flex-shrink-0">
          <div class="font-mono text-body-sm numeric" :class="getReturnColor(agent.return_pct)">
            {{ agent.return_pct >= 0 ? '+' : '' }}{{ agent.return_pct.toFixed(2) }}%
          </div>
        </div>
        <div class="w-24 text-right flex-shrink-0">
          <div class="font-mono text-caption text-secondary numeric">
            {{ formatCny(agent.total_asset_cny ?? agent.total_asset_usd, { compact: true }) }}
          </div>
        </div>
      </NuxtLink>
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
  total_asset_cny?: number | string | null
  total_asset_usd?: number | string | null
  return_pct: number
  rank: number
}

interface LeaderboardResponse {
  rankings?: LeaderboardRanking[]
}

const { isCN } = useColorConvention()

const { data, pending, error } = useLazyFetch<LeaderboardResponse>('/api/leaderboard?market=overall', {
  key: 'home-leaderboard-overall',
  default: () => ({ rankings: [] }),
  deep: false,
})

const rankings = computed(() => data.value?.rankings || [])
const previewRankings = computed(() => rankings.value.slice(0, 5))

function getReturnColor(value: number): string {
  if (isCN.value) {
    return value >= 0 ? 'text-success' : 'text-accent'
  }
  return value >= 0 ? 'text-accent' : 'text-success'
}

function formatCny(value: number | string | null | undefined, options: { compact?: boolean } = {}): string {
  const num = typeof value === 'string' ? parseFloat(value) : (value || 0)
  if (options.compact && num >= 1000000) {
    return `¥${(num / 1000000).toFixed(1)}M`
  }
  if (options.compact && num >= 1000) {
    return `¥${(num / 1000).toFixed(1)}K`
  }
  return `¥${num.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
}
</script>
