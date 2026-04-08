<template>
  <div class="max-w-4xl mx-auto px-6 py-12 md:py-16">
    <!-- Header -->
    <section class="mb-12">
      <div class="label mb-4">CNY DENOMINATED</div>
      <h1 class="type-display-md mb-4">总资产排行榜</h1>
      <p class="type-body text-secondary max-w-xl">
        所有资产统一按人民币展示，实时更新排名
      </p>
      <div class="mt-4 font-mono text-caption text-disabled">
        更新时间: {{ lastUpdated }}
      </div>
    </section>

    <!-- Summary Cards -->
    <section class="mb-8">
      <LeaderboardSummaryCards :rankings="rankings" :participant-count="participantCount" />
    </section>

    <!-- Rankings List -->
    <section class="card">
      <div class="mb-6 flex items-center justify-between gap-4 border-b border-border pb-4">
        <label class="inline-flex items-center gap-3 cursor-pointer select-none">
          <input
            v-model="includeEmpty"
            type="checkbox"
            class="h-4 w-4 rounded border-border-visible bg-surface text-success focus:ring-success"
          >
          <span class="font-body text-body-sm text-primary">显示空仓选手</span>
        </label>
        <div class="font-mono text-caption text-secondary">
          当前显示 {{ rankings.length }} / {{ participantCount }}
        </div>
      </div>

      <!-- Loading State -->
      <div v-if="rankingsPending && !rankings.length" class="py-16 text-center">
        <div class="font-mono text-caption text-secondary">加载中...</div>
      </div>

      <!-- Background Loading Indicator -->
      <div v-if="rankingsPending && rankings.length" class="absolute top-4 right-4">
        <div class="font-mono text-caption text-secondary">更新中...</div>
      </div>

      <!-- Rankings List -->
      <div v-if="rankings.length" class="divide-y divide-border">
        <LeaderboardRankingsList :rankings="pagedRankings" />
      </div>

      <!-- Empty State -->
      <div v-else-if="!rankingsPending" class="py-16 text-center">
        <div class="font-mono text-heading text-secondary">暂无数据</div>
        <p class="font-mono text-caption text-disabled mt-2">
          当前还没有可展示的排行数据
        </p>
      </div>

      <!-- Pagination -->
      <div
        v-if="totalPages > 1"
        class="pt-6 mt-6 border-t border-border flex items-center justify-center gap-2"
      >
        <button
          type="button"
          class="btn-ghost"
          :disabled="currentPage === 1"
          @click="currentPage -= 1"
        >
          ← PREV
        </button>

        <div class="flex items-center gap-1">
          <button
            v-for="page in visiblePages"
            :key="`leaderboard-page-${page}`"
            type="button"
            class="min-w-[40px] px-3 py-2 font-mono text-sm transition-colors numeric"
            :class="currentPage === page
              ? 'text-display border-b border-display'
              : 'text-disabled hover:text-secondary'"
            @click="currentPage = page"
          >
            {{ page }}
          </button>
        </div>

        <button
          type="button"
          class="btn-ghost"
          :disabled="currentPage === totalPages"
          @click="currentPage += 1"
        >
          NEXT →
        </button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { parseApiDate } from '~/utils/date'

useHead({
  title: 'RANK - CocoLoop Trade Arena',
})

const REFRESH_INTERVAL_MS = 5 * 60 * 1000

const includeEmpty = ref(true)

const { data: leaderboardData, pending: rankingsPending, refresh: refreshLeaderboard } = useLazyFetch('/api/leaderboard', {
  query: computed(() => ({
    include_empty: includeEmpty.value ? 'true' : 'false',
  })),
  default: () => ({ rankings: [] }),
})

const ITEMS_PER_PAGE = 20
const currentPage = ref(1)

const rankings = computed(() => leaderboardData.value?.rankings || [])
const participantCount = computed(() => leaderboardData.value?.total_participants || rankings.value.length)
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

watch(includeEmpty, () => {
  currentPage.value = 1
})

const lastUpdated = computed(() => {
  const ts = leaderboardData.value?.timestamp || Date.now()
  return parseApiDate(ts).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
})

let refreshTimer: number | null = null
let removeVisibilityListener: (() => void) | null = null

onMounted(() => {
  const onVisible = () => {
    if (document.hidden) return
    void refreshLeaderboard()
  }
  document.addEventListener('visibilitychange', onVisible)
  removeVisibilityListener = () => document.removeEventListener('visibilitychange', onVisible)
  refreshTimer = window.setInterval(() => {
    if (document.hidden) return
    void refreshLeaderboard()
  }, REFRESH_INTERVAL_MS)
})

onBeforeUnmount(() => {
  removeVisibilityListener?.()
  removeVisibilityListener = null
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>
