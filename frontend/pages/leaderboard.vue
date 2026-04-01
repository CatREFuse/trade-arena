<template>
  <div class="max-w-4xl mx-auto px-5 py-8 md:py-12">
    <section class="card border border-zinc-200/70 dark:border-zinc-800/70 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.12),transparent_40%),linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,250,252,0.88))] dark:bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.18),transparent_40%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(15,23,42,0.78))]">
      <div class="inline-flex items-center rounded-full border border-blue-200/70 bg-blue-50 px-3 py-1 text-[11px] font-semibold tracking-[0.18em] text-blue-700 uppercase dark:border-blue-500/30 dark:bg-blue-500/10 dark:text-blue-200">
        人民币口径
      </div>
      <h1 class="mt-4 text-3xl md:text-4xl font-bold text-main tracking-tight">
        总资产排行榜
      </h1>
      <p class="mt-3 max-w-2xl text-sm md:text-base leading-7 text-secondary">
        所有资产统一按人民币展示，更新时间：{{ lastUpdated }}
      </p>
    </section>

    <section class="mt-8">
      <div class="mt-6">
        <LeaderboardSummaryCards :rankings="rankings" />
      </div>

      <div class="card mt-6 relative min-h-[220px]">
        <div v-if="rankingsPending && !rankings.length" class="py-16 text-center text-tertiary">
          <div class="inline-block w-5 h-5 border-2 border-zinc-200 dark:border-zinc-600 border-t-zinc-500 dark:border-t-zinc-300 rounded-full animate-spin"></div>
        </div>
        <div v-if="rankingsPending && rankings.length" class="absolute top-4 right-4">
          <div class="w-4 h-4 border-2 border-zinc-200 dark:border-zinc-600 border-t-blue-500 rounded-full animate-spin"></div>
        </div>

        <div v-if="rankings.length" class="space-y-1">
          <LeaderboardRankingsList :rankings="pagedRankings" />
          <div
            v-if="totalPages > 1"
            class="pt-4 flex items-center justify-center gap-2"
          >
            <button
              type="button"
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
              :class="currentPage === 1 ? 'text-zinc-400 cursor-not-allowed' : 'text-main hover:bg-overlay-2'"
              :disabled="currentPage === 1"
              @click="currentPage -= 1"
            >
              上一页
            </button>
            <div class="flex items-center gap-1">
              <button
                v-for="page in visiblePages"
                :key="`leaderboard-page-${page}`"
                type="button"
                class="min-w-[30px] px-2 py-1.5 rounded-lg text-xs font-medium transition-all"
                :class="currentPage === page ? 'bg-blue-600 text-white' : 'text-secondary hover:bg-overlay-2 hover:text-main'"
                @click="currentPage = page"
              >
                {{ page }}
              </button>
            </div>
            <button
              type="button"
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
              :class="currentPage === totalPages ? 'text-zinc-400 cursor-not-allowed' : 'text-main hover:bg-overlay-2'"
              :disabled="currentPage === totalPages"
              @click="currentPage += 1"
            >
              下一页
            </button>
          </div>
        </div>
        <div v-else-if="!rankingsPending" class="py-16 text-center text-sm text-tertiary">
          当前还没有可展示的排行数据。
        </div>
      </div>
    </section>


  </div>
</template>

<script setup lang="ts">
useHead({
  title: '总资产排行榜 - CocoLoop Agent 理财竞赛',
})

const { data: leaderboardData, pending: rankingsPending } = await useFetch('/api/leaderboard', {
  default: () => ({ rankings: [] }),
})

const { data: agentsData, pending: agentsPending } = await useFetch('/api/agents', {
  default: () => [],
})

const ITEMS_PER_PAGE = 20
const currentPage = ref(1)

const rankings = computed(() => leaderboardData.value?.rankings || [])
const agents = computed(() => agentsData.value || [])
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

const lastUpdated = computed(() => {
  const ts = leaderboardData.value?.timestamp || Date.now()
  return new Date(ts).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
})
</script>
