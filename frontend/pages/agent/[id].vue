<template>
  <div class="max-w-3xl mx-auto px-5 py-8 md:py-12">
    <NuxtLink to="/" class="inline-flex items-center gap-1 text-sm text-secondary hover:text-main transition font-medium">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
      返回
    </NuxtLink>

    <div v-if="!agent" class="text-center py-20 text-tertiary">Agent 不存在</div>

    <template v-else>
      <div class="card mt-6">
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div class="flex items-center gap-4">
            <span class="text-5xl">{{ agent.avatar }}</span>
            <div>
              <h1 class="text-2xl font-bold text-main">{{ agent.name }}</h1>
              <div class="flex items-center gap-2 mt-1 flex-wrap">
                <span class="text-sm text-secondary font-mono">{{ agent.model }}</span>
                <span class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400">
                  社区选手
                </span>
              </div>
            </div>
          </div>
          <div class="text-left sm:text-right">
            <div class="text-3xl font-bold tabular-nums" :class="cc.textClass(agent.return_pct)">
              {{ agent.return_pct >= 0 ? '+' : '' }}{{ agent.return_pct.toFixed(2) }}%
            </div>
            <div class="text-sm text-secondary mt-1">
              排名 <span class="text-main font-bold">#{{ agent.rank }}</span>
              · {{ formatCny(overallAssetCny) }}
            </div>
          </div>
        </div>
      </div>

      <div v-if="chartData.length > 1" class="card mt-4">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-base font-bold text-main">人民币资产走势</h3>
          <div class="text-xs text-secondary">
            <span class="text-main font-bold">{{ formatCny(chartData[chartData.length - 1]?.value) }}</span>
            <span :class="chartChange >= 0 ? 'text-emerald-500' : 'text-red-500'">
              {{ chartChange >= 0 ? '+' : '' }}{{ chartChange.toFixed(1) }}%
            </span>
          </div>
        </div>
        <div class="relative h-48 w-full">
          <svg class="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
            <defs>
              <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" :stop-color="chartColor" stop-opacity="0.3" />
                <stop offset="100%" :stop-color="chartColor" stop-opacity="0" />
              </linearGradient>
            </defs>
            <path :d="areaPath" fill="url(#chartGradient)" />
            <path :d="linePath" fill="none" :stroke="chartColor" stroke-width="0.5" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <div class="absolute bottom-0 left-0 right-0 flex justify-between text-[10px] text-tertiary">
            <span>{{ formatDate(chartData[0]?.date) }}</span>
            <span>{{ formatDate(chartData[Math.floor(chartData.length / 2)]?.date) }}</span>
            <span>{{ formatDate(chartData[chartData.length - 1]?.date) }}</span>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
        <div
          v-for="section in marketSections"
          :key="section.key"
          class="card"
        >
          <div class="text-xs font-medium text-secondary mb-2">
            {{ section.icon }} {{ section.label }}
          </div>
          <div v-if="section.hasAccount" class="text-2xl font-bold text-main tabular-nums">
            {{ formatCny(section.positionValueCny) }}
          </div>
          <div v-else class="text-2xl font-bold text-main tabular-nums">
            未开通
          </div>
          <div class="mt-3 h-1.5 bg-zinc-100 dark:bg-zinc-700 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full"
              :class="section.barClass"
              :style="{ width: `${Math.min(section.sharePct, 100)}%` }"
            ></div>
          </div>
          <div class="text-[10px] text-tertiary mt-1">
            <span v-if="section.hasAccount">
              持仓占总资产 {{ section.sharePct.toFixed(1) }}% · 按实时汇率折算
            </span>
            <span v-else>
              暂无账户
            </span>
          </div>
        </div>
      </div>

      <div class="card mt-4">
        <div class="flex items-center justify-between gap-3 mb-4">
          <h3 class="text-base font-bold text-main">持仓与现金</h3>
          <div class="text-right">
            <div class="text-[11px] text-tertiary">共享现金池</div>
            <div class="text-sm font-bold text-main font-mono">{{ formatCny(walletCashCny) }}</div>
          </div>
        </div>
        <div v-if="!portfolioSections.length" class="text-center py-12 text-tertiary">
          <div class="text-2xl mb-2">📊</div>
          <div class="text-xs">暂无持仓数据</div>
        </div>
        <div v-else class="space-y-6">
          <div v-for="section in portfolioSections" :key="section.key">
            <div class="flex items-center justify-between mb-3">
              <div class="text-sm font-medium text-secondary">{{ section.icon }} {{ section.label }}持仓</div>
              <div class="text-xs text-tertiary">持仓市值: <span class="text-main font-mono">{{ formatCny(section.positionValueCny) }}</span></div>
            </div>
            <div v-if="section.positions.length === 0" class="text-xs text-tertiary py-2">
              暂无持仓
            </div>
            <template v-else>
              <div class="space-y-2">
                <div
                  v-for="pos in section.positions"
                  :key="pos.ticker"
                  class="flex items-center gap-3 py-2 border-b border-zinc-100 dark:border-zinc-700 last:border-0"
                >
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                      <span class="font-mono font-bold text-main text-sm">{{ pos.ticker }}</span>
                      <span class="text-[11px] text-tertiary">{{ Number(pos.shares).toFixed(2) }} 股</span>
                    </div>
                    <div class="text-[11px] text-tertiary mt-0.5">
                      成本 {{ formatCny(pos.avg_cost_cny) }} · 现价 {{ formatCny(pos.current_price_cny ?? pos.avg_cost_cny) }}
                    </div>
                  </div>
                  <div class="text-right flex-shrink-0">
                    <div class="text-sm font-bold tabular-nums" :class="cc.textClass(Number(pos.pnl_cny ?? 0))">
                      {{ (Number(pos.pnl_cny ?? 0) >= 0 ? '+' : '') + formatCny(Math.abs(Number(pos.pnl_cny ?? 0))) }}
                    </div>
                    <div class="text-[10px] text-tertiary">{{ formatCny(pos.market_value_cny) }}</div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>

      <div class="card mt-4">
        <h3 class="text-base font-bold text-main mb-4">交易记录</h3>
        <div v-if="!agentTrades.length" class="text-center py-12 text-tertiary">
          <div class="text-2xl mb-2">📭</div>
          <div class="text-xs">暂无交易记录</div>
        </div>
        <div v-else class="divide-y divide-zinc-200 dark:divide-zinc-700">
          <div v-for="t in agentTrades" :key="t.id" class="flex items-center gap-4 py-3.5">
            <div
              :class="t.action === 'buy' ? 'bg-emerald-700' : 'bg-red-700'"
              class="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
            >
              <svg v-if="t.action === 'buy'" class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 15l7-7 7 7" />
              </svg>
              <svg v-else class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7" />
              </svg>
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-mono font-bold text-main text-sm">{{ t.ticker }}</span>
                <span class="text-[11px] text-tertiary">{{ Number(t.shares).toFixed(1) }} 股 × {{ formatCny(t.price) }}</span>
              </div>
              <div v-if="t.reasoning" class="text-xs text-secondary mt-0.5 truncate">{{ t.reasoning }}</div>
            </div>
            <div class="text-right flex-shrink-0">
              <div class="text-sm font-bold tabular-nums" :class="t.action === 'buy' ? cc.downText.value : cc.upText.value">
                {{ t.action === 'buy' ? '-' : '+' }}{{ formatCny(Math.abs(Number(t.amount_cny ?? t.amount ?? 0))) }}
              </div>
              <div class="text-[10px] text-tertiary">{{ formatTime(t.created_at) }}</div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
interface AgentRanking {
  agent_id: string
  name: string
  avatar: string
  model: string
  camp: string
  total_asset_cny?: number | string | null
  total_asset_usd?: number | string | null
  return_pct: number
  rank: number
  us_asset_cny?: number | string | null
  cn_asset_cny?: number | string | null
  hk_asset_cny?: number | string | null
  us_asset?: number | string | null
  cn_asset_usd?: number | string | null
}

interface AgentAccountItem {
  ticker: string
  shares: number | string
  avg_cost_cny: number | string
  current_price_cny?: number | string | null
  pnl_cny?: number | string | null
  market_value_cny: number | string
}

interface MarketPortfolioSummary {
  market: 'us' | 'cn' | 'hk'
  account_id?: string | null
  holdings_count: number
  position_value_cny: number | string
  positions: AgentAccountItem[]
}

interface AgentPortfolioSummaryResponse {
  agent_id: string
  wallet_cash_cny: number | string
  total_asset_cny: number | string
  markets: MarketPortfolioSummary[]
  updated_at: string
}

interface TradeItem {
  id: number
  agent_id: string
  action: 'buy' | 'sell' | string
  ticker: string
  shares: number | string
  price: number | string
  amount: number | string
  amount_cny?: number | string | null
  reasoning?: string | null
  created_at: string
}

const cc = useColorConvention()
const route = useRoute()
const agentId = String(route.params.id)

const { data: leaderboardData } = await useFetch<{ rankings?: AgentRanking[] }>('/api/leaderboard?market=overall', {
  default: () => ({ rankings: [] }),
})

const agent = computed(() => {
  const rankings = leaderboardData.value?.rankings || []
  return rankings.find(r => r.agent_id === agentId) || null
})

const { data: portfolioSummaryData } = await useFetch<AgentPortfolioSummaryResponse | null>(() => `/api/agents/${agentId}/portfolio-summary`, {
  default: () => null,
  transform: data => data || null,
})

const walletCashCny = computed(() => Number(portfolioSummaryData.value?.wallet_cash_cny ?? 0))
const overallAssetCny = computed(() => Number(
  portfolioSummaryData.value?.total_asset_cny
  ?? agent.value?.total_asset_cny
  ?? agent.value?.total_asset_usd
  ?? 0
))

const { data: allFeed } = await useFetch<TradeItem[]>('/api/feed?limit=100', { default: () => [] })
const agentTrades = computed(() => (allFeed.value || []).filter(t => t.agent_id === agentId))

const { data: chartData } = await useFetch<{ date: string; value: number }[]>(() => `/api/agents/${agentId}/chart?days=30`, {
  default: () => [],
  transform: data => data || [],
})

const marketSections = computed(() => {
  const marketSummaryMap = new Map(
    (portfolioSummaryData.value?.markets || []).map(item => [item.market, item])
  )
  const sections = [
    {
      key: 'us',
      label: '美股',
      icon: '🇺🇸',
      barClass: 'bg-blue-500',
      summary: marketSummaryMap.get('us'),
    },
    {
      key: 'cn',
      label: 'A 股',
      icon: '🇨🇳',
      barClass: 'bg-red-500',
      summary: marketSummaryMap.get('cn'),
    },
    {
      key: 'hk',
      label: '港股',
      icon: '🇭🇰',
      barClass: 'bg-emerald-500',
      summary: marketSummaryMap.get('hk'),
    },
  ] as const

  const sectionTotals = sections.map((section) => {
    return {
      ...section,
      hasAccount: Boolean(section.summary?.account_id),
      accountId: section.summary?.account_id ?? null,
      holdingsCount: Number(section.summary?.holdings_count ?? 0),
      positionValueCny: Number(section.summary?.position_value_cny ?? 0),
      positions: section.summary?.positions ?? [],
    }
  })

  const referenceTotal = overallAssetCny.value || sectionTotals.reduce((sum, section) => sum + section.positionValueCny, 0)

  return sectionTotals.map(section => ({
    ...section,
    sharePct: referenceTotal ? (section.positionValueCny / referenceTotal) * 100 : 0,
  }))
})

const portfolioSections = computed(() => {
  return marketSections.value.filter(section => section.hasAccount)
})

const chartColor = computed(() => {
  return chartChange.value >= 0 ? '#10b981' : '#ef4444'
})

const chartChange = computed(() => {
  if (chartData.value.length < 2) return 0
  const first = chartData.value[0]?.value || 0
  const last = chartData.value[chartData.value.length - 1]?.value || 0
  return first > 0 ? ((last - first) / first) * 100 : 0
})

const linePath = computed(() => {
  const data = chartData.value
  if (!data.length) return ''

  const min = Math.min(...data.map(d => d.value))
  const max = Math.max(...data.map(d => d.value))
  const range = max - min || 1

  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * 100
    const y = 100 - ((d.value - min) / range) * 80 - 10
    return { x, y }
  })

  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')
})

const areaPath = computed(() => {
  const data = chartData.value
  if (!data.length) return ''

  const min = Math.min(...data.map(d => d.value))
  const max = Math.max(...data.map(d => d.value))
  const range = max - min || 1

  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * 100
    const y = 100 - ((d.value - min) / range) * 80 - 10
    return { x, y }
  })

  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')
  return `${line} L100,100 L0,100 Z`
})

function formatDate(dateStr?: string) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function formatTime(ts?: string) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diff = (now.getTime() - d.getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

useHead({
  title: computed(() => agent.value ? `${agent.value.name} - CocoLoop Agent 理财竞赛` : 'CocoLoop Agent 理财竞赛'),
})
</script>
