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
        <div class="mb-4 flex flex-wrap items-center gap-2">
          <button
            v-for="item in chartTypeItems"
            :key="item.value"
            type="button"
            class="px-2.5 py-1 rounded-lg text-xs transition"
            :class="chartType === item.value ? 'bg-blue-600 text-white' : 'bg-overlay-2 text-secondary hover:text-main'"
            @click="onChartTypeChange(item.value)"
          >
            {{ item.label }}
          </button>
          <div class="w-px h-5 bg-zinc-200 dark:bg-zinc-700 mx-1"></div>
          <button
            v-for="spanItem in spanOptions"
            :key="spanItem"
            type="button"
            class="px-2.5 py-1 rounded-lg text-xs transition"
            :class="selectedSpan === spanItem ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900' : 'bg-overlay-2 text-secondary hover:text-main'"
            @click="selectedSpan = spanItem"
          >
            {{ spanLabelMap[spanItem] }}
          </button>
        </div>
        <div class="relative h-56 w-full">
          <ClientOnly>
            <VChart
              class="h-full w-full"
              :option="equityChartOption"
              autoresize
            />
            <template #fallback>
              <div class="h-full w-full flex items-center justify-center text-xs text-tertiary">图表加载中</div>
            </template>
          </ClientOnly>
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
                      <NuxtLink
                        :to="`/market-detail/${section.key}/${pos.ticker}`"
                        class="font-mono font-bold text-main text-sm hover:underline"
                      >
                        {{ pos.ticker }}
                      </NuxtLink>
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
        <div v-else class="divide-y divide-border">
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
                <NuxtLink
                  :to="`/market-detail/${resolveTickerMarket(t.ticker)}/${t.ticker}`"
                  class="font-mono font-bold text-main text-sm hover:underline"
                >
                  {{ t.ticker }}
                </NuxtLink>
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
import { use as useECharts } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

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

interface AgentEquityCurveResponse {
  span: '1d' | '3d' | '7d' | '30d' | 'max'
  interval: '5m' | '15m' | '1h' | '1d'
  points: Array<{ date: string; value: number }>
}

type ChartType = 'intraday' | 'swing' | 'trend' | 'long'
type SpanType = '1d' | '3d' | '7d' | '30d' | 'max'

useECharts([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const cc = useColorConvention()
const route = useRoute()
const agentId = String(route.params.id)
const REFRESH_INTERVAL_MS = 5 * 60 * 1000

const chartTypeItems: Array<{ value: ChartType; label: string; defaultSpan: SpanType }> = [
  { value: 'intraday', label: '日内', defaultSpan: '1d' },
  { value: 'swing', label: '波段', defaultSpan: '7d' },
  { value: 'trend', label: '趋势', defaultSpan: '30d' },
  { value: 'long', label: '长期', defaultSpan: 'max' },
]
const spanLabelMap: Record<SpanType, string> = {
  '1d': '1天',
  '3d': '3天',
  '7d': '7天',
  '30d': '30天',
  max: '全部',
}
const spanOptionsByChartType: Record<ChartType, SpanType[]> = {
  intraday: ['1d', '3d'],
  swing: ['3d', '7d', '30d'],
  trend: ['7d', '30d', 'max'],
  long: ['30d', 'max'],
}

const chartType = ref<ChartType>('trend')
const selectedSpan = ref<SpanType>('30d')

const { data: leaderboardData, refresh: refreshLeaderboard } = await useFetch<{ rankings?: AgentRanking[] }>('/api/leaderboard?market=overall', {
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

const spanOptions = computed(() => spanOptionsByChartType[chartType.value])

const { data: curveData, refresh: refreshCurve } = await useFetch<AgentEquityCurveResponse>(() =>
  `/api/agents/${agentId}/equity-curve?chart_type=${chartType.value}&span=${selectedSpan.value}&interval=auto`,
{
  default: () => ({ span: '30d', interval: '1h', points: [] }),
})
const chartData = computed(() => curveData.value?.points || [])

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

const equityChartOption = computed(() => {
  const points = chartData.value
  const values = points.map(point => Number(point.value))
  const minValue = values.length ? Math.min(...values) : 0
  const maxValue = values.length ? Math.max(...values) : 0
  const spread = maxValue - minValue
  const padding = spread > 0 ? spread * 0.08 : Math.max(Math.abs(maxValue) * 0.02, 1)

  return {
    animation: false,
    grid: { left: 10, right: 10, top: 10, bottom: 28, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      formatter: (params: any[]) => {
        const item = params?.[0]
        if (!item) return ''
        const dateLabel = new Date(item.data[0]).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
        const valueLabel = formatCny(item.data[1])
        return `${dateLabel}<br/>${valueLabel}`
      },
    },
    xAxis: {
      type: 'time',
      boundaryGap: false,
      axisLabel: { color: '#9CA3AF' },
      axisLine: { lineStyle: { color: '#E5E7EB' } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      min: minValue - padding,
      max: maxValue + padding,
      axisLabel: {
        color: '#9CA3AF',
        formatter: (value: number) => formatCny(value, { compact: true }),
      },
      splitLine: { lineStyle: { color: '#F1F5F9' } },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: chartColor.value },
        areaStyle: {
          color: chartColor.value,
          opacity: 0.18,
        },
        data: points.map(point => [point.date, point.value]),
      },
    ],
  }
})

function onChartTypeChange(nextType: ChartType) {
  chartType.value = nextType
  const preset = chartTypeItems.find(item => item.value === nextType)?.defaultSpan || '30d'
  selectedSpan.value = preset
}

function resolveTickerMarket(ticker: string): 'us' | 'cn' | 'hk' {
  const normalized = String(ticker || '').toUpperCase()
  if (normalized.endsWith('.HK')) return 'hk'
  if (normalized.endsWith('.SZ') || normalized.endsWith('.SH') || normalized.endsWith('.BJ')) return 'cn'
  return 'us'
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

let refreshTimer: number | null = null
let removeVisibilityListener: (() => void) | null = null

onMounted(() => {
  const onVisible = () => {
    if (document.hidden) return
    void refreshCurve()
    void refreshLeaderboard()
  }
  document.addEventListener('visibilitychange', onVisible)
  removeVisibilityListener = () => document.removeEventListener('visibilitychange', onVisible)
  refreshTimer = window.setInterval(() => {
    if (document.hidden) return
    void refreshCurve()
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

useHead({
  title: computed(() => agent.value ? `${agent.value.name} - CocoLoop Agent 理财竞赛` : 'CocoLoop Agent 理财竞赛'),
})
</script>
