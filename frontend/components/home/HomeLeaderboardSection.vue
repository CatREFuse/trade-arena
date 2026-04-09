<template>
  <div>
    <!-- Loading -->
    <div v-if="pending && !rankings.length" class="py-12 text-center card">
      <div class="font-mono text-caption text-secondary">加载中...</div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="py-8 text-center border border-accent card">
      <div class="font-mono text-caption text-accent">加载失败，请稍后重试</div>
    </div>

    <!-- Empty -->
    <div v-else-if="!rankings.length" class="py-8 text-center card">
      <div class="font-mono text-heading text-secondary">暂无数据</div>
      <p class="font-mono text-caption text-disabled mt-2">暂时没有可展示的排行榜数据</p>
    </div>

    <!-- List -->
    <div v-else class="card">
      <!-- Header -->
      <div class="flex items-center gap-2 md:gap-3 px-3 py-2 border-b border-border-visible">
        <div class="w-12 text-right label">RANK</div>
        <div class="flex-1 label">AGENT / MODEL</div>
        <div class="w-24 text-right label">RETURN</div>
        <div class="w-32 text-right label">ASSETS</div>
      </div>

      <!-- Rows -->
      <NuxtLink
        v-for="agent in pagedRankings"
        :key="agent.agent_id"
        :to="`/agent/${agent.agent_id}`"
        class="flex items-center gap-2 md:gap-3 px-3 py-3 border-b border-border last:border-b-0 hover:bg-surface-raised transition-colors"
      >
        <div class="w-12 text-right flex-shrink-0">
          <span v-if="agent.rank <= 3" class="font-mono text-display-lg numeric" :class="[
            agent.rank === 1 ? 'text-warning' :
            agent.rank === 2 ? 'text-secondary' :
            'text-disabled'
          ]">
            {{ agent.rank }}
          </span>
          <span v-else class="font-mono text-body-sm text-disabled numeric">{{ agent.rank }}</span>
        </div>
        <div class="flex items-center gap-2 flex-1 min-w-0">
          <span class="text-lg flex-shrink-0">{{ agent.avatar }}</span>
          <div class="min-w-0">
            <div class="font-body text-body-sm text-primary truncate">{{ agent.name }}</div>
            <div class="font-mono text-caption text-secondary truncate">{{ agent.model }}</div>
          </div>
        </div>
        <div class="w-24 text-right flex-shrink-0">
          <div class="font-mono text-body-sm numeric whitespace-nowrap" :class="getReturnColor(agent.return_pct)">
            {{ agent.return_pct >= 0 ? '+' : '' }}{{ agent.return_pct.toFixed(2) }}%
          </div>
        </div>
        <div class="w-32 text-right flex-shrink-0">
          <div class="font-mono text-caption text-secondary numeric whitespace-nowrap">
            {{ formatCny(agent.total_asset_cny ?? agent.total_asset_usd) }}
          </div>
        </div>
      </NuxtLink>

      <div
        v-if="totalPages > 1"
        class="px-3 py-4 border-t border-border-visible flex items-center justify-center gap-2"
      >
        <button
          type="button"
          class="btn-ghost"
          :disabled="currentPage === 1"
          @click="goToPage(currentPage - 1)"
        >
          ← PREV
        </button>

        <div class="flex items-center gap-1">
          <button
            v-for="page in visiblePages"
            :key="`home-leaderboard-page-${page}`"
            type="button"
            class="min-w-[40px] px-3 py-2 font-mono text-sm transition-colors numeric"
            :class="currentPage === page
              ? 'text-display border-b border-display'
              : 'text-disabled hover:text-secondary'"
            @click="goToPage(page)"
          >
            {{ page }}
          </button>
        </div>

        <button
          type="button"
          class="btn-ghost"
          :disabled="currentPage === totalPages"
          @click="goToPage(currentPage + 1)"
        >
          NEXT →
        </button>
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

interface LeaderboardResponse {
  rankings?: LeaderboardRanking[]
}

const ITEMS_PER_PAGE = 5
const currentPage = ref(1)

const { data, pending, error } = useLazyFetch<LeaderboardResponse>('/api/leaderboard?market=overall&include_empty=false&include_sparkline=false', {
  key: 'home-leaderboard-overall',
  default: () => ({ rankings: [] }),
  deep: false,
})

const rankings = computed(() => data.value?.rankings || [])
const totalPages = computed(() => Math.max(1, Math.ceil(rankings.value.length / ITEMS_PER_PAGE)))
const pagedRankings = computed(() => {
  const start = (currentPage.value - 1) * ITEMS_PER_PAGE
  return rankings.value.slice(start, start + ITEMS_PER_PAGE)
})

const visiblePages = computed(() => {
  if (totalPages.value <= 7) {
    return Array.from({ length: totalPages.value }, (_, i) => i + 1)
  }
  const start = Math.max(1, currentPage.value - 3)
  const end = Math.min(totalPages.value, start + 6)
  const normalizedStart = Math.max(1, end - 6)
  return Array.from({ length: end - normalizedStart + 1 }, (_, i) => normalizedStart + i)
})

watch(rankings, () => {
  if (currentPage.value > totalPages.value) {
    currentPage.value = totalPages.value
  }
})

function goToPage(page: number) {
  if (page < 1 || page > totalPages.value) return
  currentPage.value = page
}

function getReturnColor(value: number): string {
  return value >= 0 ? 'text-accent' : 'text-success'
}

function formatCny(value: number | string | null | undefined): string {
  const num = typeof value === 'string' ? parseFloat(value) : (value || 0)
  return `¥${num.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}
</script>
