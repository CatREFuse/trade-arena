<template>
  <div class="max-w-6xl mx-auto px-5 py-8 md:py-12">
    <div class="card">
      <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 class="text-2xl md:text-3xl font-bold text-main tracking-tight">管理后台</h1>
          <p class="mt-1 text-secondary text-sm">用户、日志、数据源、大盘和交易统计总览</p>
        </div>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-zinc-100 dark:bg-zinc-800 text-main hover:bg-zinc-200 dark:hover:bg-zinc-700 transition"
            @click="logout"
          >
            退出
          </button>
          <div class="text-xs text-tertiary">更新时间 {{ generatedAtLabel }}</div>
          <button
            type="button"
            class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="pending"
            @click="refresh"
          >
            {{ pending ? '刷新中...' : '刷新数据' }}
          </button>
        </div>
      </div>
      <div v-if="error" class="mt-4 rounded-xl bg-rose-50 dark:bg-rose-900/20 text-rose-700 dark:text-rose-300 px-4 py-3 text-xs">
        后台数据加载失败：{{ normalizedError }}
      </div>
    </div>

    <div class="mt-6 space-y-4">
      <AdminUsersPanel :total="dashboard.users.total" :items="dashboard.users.items" />
      <AdminLogsPanel :items="dashboard.logs.items" />
      <AdminDataSourcesPanel :status="dashboard.data_sources" />
      <AdminMarketPanel :snapshot="dashboard.market" />
      <AdminTradeStatsPanel :stats="dashboard.trade_stats" />
    </div>
  </div>
</template>

<script setup lang="ts">
import AdminDataSourcesPanel from '~/components/admin/AdminDataSourcesPanel.vue'
import AdminLogsPanel from '~/components/admin/AdminLogsPanel.vue'
import AdminMarketPanel from '~/components/admin/AdminMarketPanel.vue'
import AdminTradeStatsPanel from '~/components/admin/AdminTradeStatsPanel.vue'
import AdminUsersPanel from '~/components/admin/AdminUsersPanel.vue'

useHead({ title: '管理后台 - CocoLoop Agent 理财竞赛' })

const {
  data,
  pending,
  error,
  refresh,
  generatedAtLabel,
} = useAdminDashboard()

const dashboard = computed(() => data.value || {
  users: { total: 0, items: [] },
  logs: { items: [] },
  data_sources: {
    db: { ok: false, detail: '' },
    redis: { ok: false, detail: '' },
    probes: [],
    provider_chains: {},
    provider_circuits: [],
    cache: {},
  },
  market: {
    updated_at: '',
    indices: [],
    market_summary: [],
    boards: {},
  },
  trade_stats: {
    totals: {
      trade_count: 0,
      trade_amount: 0,
      buy_count: 0,
      sell_count: 0,
      recent_24h_count: 0,
    },
    by_market: {},
    daily: [],
    top_tickers: [],
  },
})

const normalizedError = computed(() => {
  const detail = (error.value as any)?.data?.detail
  if (typeof detail === 'string')
    return detail
  if (typeof detail?.message === 'string')
    return detail.message
  return '未知错误'
})

async function logout() {
  await $fetch('/api/admin/auth/logout', { method: 'POST' })
  await navigateTo('/console/login', { replace: true })
}
</script>
