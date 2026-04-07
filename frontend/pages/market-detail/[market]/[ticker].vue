<template>
  <div class="max-w-5xl mx-auto px-5 py-8 md:py-12">
    <div class="flex items-center justify-between gap-3">
      <div>
        <NuxtLink :to="`/market-detail/${marketKey}`" class="text-xs font-medium text-tertiary hover:text-main transition">
          ← 返回市场详情
        </NuxtLink>
        <h1 class="mt-2 text-2xl md:text-3xl font-bold text-main tracking-tight">
          {{ stockName }}
        </h1>
        <p class="mt-1 text-sm text-secondary">
          {{ ticker }} · {{ marketLabel }} · 上市时间 {{ listedAtLabel }}
        </p>
        <div class="mt-2">
          <MarketDataTimestamp :timestamp="latestUpdatedAt" />
        </div>
      </div>
      <div class="text-right">
        <div class="text-sm font-bold tabular-nums text-main">{{ formatPrice(quotePrice) }}</div>
        <div class="text-lg font-bold tabular-nums" :class="cc.textClass(quoteChangePct)">
          {{ formatPercent(quoteChangePct) }}
        </div>
        <div class="text-[10px] text-tertiary mt-0.5">
          {{ quoteStatusLabel }}
        </div>
      </div>
    </div>

    <div class="card mt-5">
      <div class="flex items-center justify-between gap-3 mb-4">
        <div>
          <h2 class="text-base font-bold text-main">走势与 K 线</h2>
          <p class="mt-1 text-xs text-tertiary">
            数据来源：{{ activeChartSourceLabel }}
          </p>
        </div>
        <div class="flex flex-col items-end gap-2">
          <div class="inline-flex rounded-xl bg-overlay-2 p-1">
            <button
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition"
              :class="chartMode === 'line' ? 'bg-white dark:bg-zinc-800 text-main shadow-sm' : 'text-secondary hover:text-main'"
              @click="setChartMode('line')"
            >
              实时走势
            </button>
            <button
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition"
              :class="chartMode === 'candlestick' ? 'bg-white dark:bg-zinc-800 text-main shadow-sm' : 'text-secondary hover:text-main'"
              @click="setChartMode('candlestick')"
            >
              K 线图
            </button>
          </div>
          <div class="inline-flex rounded-xl bg-overlay-2 p-1">
            <button
              v-for="spanOption in activeSpanOptions"
              :key="spanOption.value"
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition"
              :class="activeSpanValue === spanOption.value ? 'bg-white dark:bg-zinc-800 text-main shadow-sm' : 'text-secondary hover:text-main'"
              @click="setChartSpan(spanOption.value)"
            >
              {{ spanOption.label }}
            </button>
          </div>
        </div>
      </div>
      <ClientOnly>
        <VChart :option="stockChartOption" autoresize class="h-[340px] w-full rounded-xl bg-white dark:bg-zinc-950" />
      </ClientOnly>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
      <div class="rounded-2xl bg-overlay-2 px-4 py-3">
        <div class="text-[10px] uppercase tracking-widest text-tertiary">1日收益</div>
        <div class="mt-1 text-lg font-bold tabular-nums" :class="resolveReturnClass(returnStats.r1d)">
          {{ formatPercent(returnStats.r1d) }}
        </div>
      </div>
      <div class="rounded-2xl bg-overlay-2 px-4 py-3">
        <div class="text-[10px] uppercase tracking-widest text-tertiary">5日收益</div>
        <div class="mt-1 text-lg font-bold tabular-nums" :class="resolveReturnClass(returnStats.r5d)">
          {{ formatPercent(returnStats.r5d) }}
        </div>
      </div>
      <div class="rounded-2xl bg-overlay-2 px-4 py-3">
        <div class="text-[10px] uppercase tracking-widest text-tertiary">30日收益</div>
        <div class="mt-1 text-lg font-bold tabular-nums" :class="resolveReturnClass(returnStats.r30d)">
          {{ formatPercent(returnStats.r30d) }}
        </div>
      </div>
      <div class="rounded-2xl bg-overlay-2 px-4 py-3">
        <div class="text-[10px] uppercase tracking-widest text-tertiary">90日收益</div>
        <div class="mt-1 text-lg font-bold tabular-nums" :class="resolveReturnClass(returnStats.r90d)">
          {{ formatPercent(returnStats.r90d) }}
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
      <div class="card">
        <div class="text-[10px] uppercase tracking-widest text-tertiary">总操作次数</div>
        <div class="mt-1 text-2xl font-bold tabular-nums text-main">{{ siteStats.total_trade_count }}</div>
      </div>
      <div class="card">
        <div class="text-[10px] uppercase tracking-widest text-tertiary">参与 Agent</div>
        <div class="mt-1 text-2xl font-bold tabular-nums text-main">{{ siteStats.unique_agent_count }}</div>
      </div>
      <div class="card">
        <div class="text-[10px] uppercase tracking-widest text-tertiary">站内成交额(CNY)</div>
        <div class="mt-1 text-2xl font-bold tabular-nums text-main">{{ formatMoney(siteStats.total_amount_cny) }}</div>
      </div>
    </div>

    <section class="card mt-4">
      <div class="flex items-center justify-between gap-3 mb-4">
        <div>
          <h2 class="text-base font-bold text-main">Agent 操作记录</h2>
        </div>
      </div>

      <div v-if="!recentTrades.length" class="rounded-2xl bg-overlay-2 px-4 py-8 text-center text-sm text-tertiary">
        暂无操作记录
      </div>
      <div v-else class="divide-y divide-border">
        <div v-for="trade in recentTrades" :key="trade.trade_id" class="flex items-center gap-4 py-3">
          <div class="text-xl">{{ trade.agent_avatar }}</div>
          <div class="min-w-0 flex-1">
            <div class="text-sm font-semibold text-main truncate">{{ trade.agent_name }}</div>
            <div class="text-xs text-tertiary mt-0.5">
              {{ trade.action === 'buy' ? '买入' : '卖出' }} {{ trade.shares }} 股 · {{ formatPrice(Number(trade.price)) }}
            </div>
            <div class="text-[11px] text-tertiary mt-0.5">{{ formatTime(trade.created_at) }}</div>
          </div>
          <div class="text-right">
            <div class="text-sm font-bold tabular-nums text-main">{{ formatMoney(trade.amount_cny ?? trade.amount) }}</div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { use as useECharts } from 'echarts/core'
import { CandlestickChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import MarketDataTimestamp from '~/components/market/MarketDataTimestamp.vue'

const VChart = defineAsyncComponent(() => import('vue-echarts'))
useECharts([LineChart, CandlestickChart, GridComponent, TooltipComponent, CanvasRenderer])

interface StockHistoryPoint {
  ts: number
  date: string
  open: number
  high: number
  low: number
  close: number
  volume?: number | null
}

interface StockRecentTrade {
  trade_id: number
  agent_id: string
  agent_name: string
  agent_avatar: string
  market: string
  action: string
  shares: string
  price: string
  amount: string
  amount_cny?: string | null
  created_at: string
}

interface StockSiteStats {
  total_trade_count: number
  buy_trade_count: number
  sell_trade_count: number
  total_amount: string
  total_amount_cny: string
  unique_agent_count: number
  last_trade_at?: string | null
}

interface StockDetailResponse {
  ticker: string
  name?: string | null
  market: string
  days: number
  listed_at?: string | null
  history_source?: string | null
  quote: {
    ticker: string
    price: string | number
    change_pct: number
    market_status: string
  }
  history: StockHistoryPoint[]
  site_stats: StockSiteStats
  recent_trades: StockRecentTrade[]
  updated_at: string
}

interface StockIntradayResponse {
  ticker: string
  interval: string
  span: string
  source?: string | null
  points: Array<{
    ts: number
    time: string
    open: number
    high: number
    low: number
    close: number
    volume?: number | null
  }>
  updated_at: string
}

type IntradaySpan = '1d' | '5d'
type CandleSpanDays = 30 | 90 | 180

const REFRESH_INTERVAL_MS = 5 * 60 * 1000

const route = useRoute()
const cc = useColorConvention()
const { isDark } = useAppearance()
const rawMarket = String(route.params.market || '').toLowerCase()
if (rawMarket !== 'us' && rawMarket !== 'cn' && rawMarket !== 'hk') {
  throw createError({ statusCode: 404, statusMessage: '市场不存在' })
}
const marketKey = rawMarket as 'us' | 'cn' | 'hk'
const ticker = computed(() => String(route.params.ticker || '').toUpperCase())
const intradaySpan = ref<IntradaySpan>('1d')
const candleSpanDays = ref<CandleSpanDays>(90)

const { data: detailData, refresh: refreshDetail } = await useFetch<StockDetailResponse>(
  () => `/api/market/stocks/${ticker.value}?days=180&trade_limit=50`,
  { default: () => ({ history: [], recent_trades: [], site_stats: {
    total_trade_count: 0,
    buy_trade_count: 0,
    sell_trade_count: 0,
    total_amount: '0',
    total_amount_cny: '0',
    unique_agent_count: 0,
  }, quote: { ticker: ticker.value, price: 0, change_pct: 0, market_status: 'closed' }, ticker: ticker.value, market: marketKey, days: 180, updated_at: '' }) },
)

const { data: intradayData, refresh: refreshIntraday } = await useFetch<StockIntradayResponse>(
  () => `/api/market/stocks/${ticker.value}/intraday?span=${intradaySpan.value}&interval=5m`,
  { default: () => ({ ticker: ticker.value, interval: '5m', span: '1d', points: [], updated_at: '' }) },
)

const marketLabel = computed(() => marketKey === 'us' ? '美股' : marketKey === 'cn' ? 'A股' : '港股')
const stockName = computed(() => detailData.value?.name || ticker.value)
const listedAtLabel = computed(() => detailData.value?.listed_at || '--')
const quotePrice = computed(() => Number(detailData.value?.quote?.price || 0))
const quoteChangePct = computed(() => Number(detailData.value?.quote?.change_pct || 0))
const quoteStatusLabel = computed(() => detailData.value?.quote?.market_status === 'open' ? '开盘中' : '休市')
const siteStats = computed(() => detailData.value?.site_stats || {
  total_trade_count: 0,
  buy_trade_count: 0,
  sell_trade_count: 0,
  total_amount: '0',
  total_amount_cny: '0',
  unique_agent_count: 0,
})
const recentTrades = computed(() => detailData.value?.recent_trades || [])
const chartMode = ref<'line' | 'candlestick'>('line')
const latestUpdatedAt = computed(() => intradayData.value?.updated_at || detailData.value?.updated_at || '')
const activeChartSource = computed(() => (
  chartMode.value === 'line'
    ? String(intradayData.value?.source || '')
    : String(detailData.value?.history_source || '')
))
const activeChartSourceLabel = computed(() => {
  return formatChartSourceLabel(activeChartSource.value)
})
let refreshWorker: number | null = null
let removeVisibilityListener: (() => void) | null = null

const lineSpanOptions: Array<{ value: IntradaySpan; label: string }> = [
  { value: '1d', label: '1D' },
  { value: '5d', label: '5D' },
]

const candleSpanOptions: Array<{ value: CandleSpanDays; label: string }> = [
  { value: 30, label: '1M' },
  { value: 90, label: '3M' },
  { value: 180, label: '6M' },
]

const activeSpanOptions = computed<Array<{ value: string; label: string }>>(() => {
  if (chartMode.value === 'line') {
    return lineSpanOptions.map((option) => ({
      value: option.value,
      label: option.label,
    }))
  }
  return candleSpanOptions.map((option) => ({
    value: String(option.value),
    label: option.label,
  }))
})

const activeSpanValue = computed(() => (
  chartMode.value === 'line' ? intradaySpan.value : String(candleSpanDays.value)
))

const lineSeriesData = computed(() => {
  return (intradayData.value?.points || [])
    .map((point) => ({
      ts: Number(point.ts),
      value: Number(point.close),
    }))
    .filter((point) => Number.isFinite(point.ts) && Number.isFinite(point.value))
})

const candleSeriesData = computed(() => {
  const cutoffTs = Date.now() - candleSpanDays.value * 24 * 60 * 60 * 1000
  const selectedHistory = (detailData.value?.history || []).filter((point) => point.ts >= cutoffTs)
  const sourceHistory = selectedHistory.length ? selectedHistory : (detailData.value?.history || [])
  return sourceHistory
    .map((point) => ({
      ts: Number(point.ts),
      open: Number(point.open),
      high: Number(point.high),
      low: Number(point.low),
      close: Number(point.close),
    }))
    .filter((point) =>
      Number.isFinite(point.ts) &&
      Number.isFinite(point.open) &&
      Number.isFinite(point.high) &&
      Number.isFinite(point.low) &&
      Number.isFinite(point.close)
    )
})

const hasMeaningfulHistory = computed(() => {
  const history = detailData.value?.history || []
  if (history.length < 8) return false
  const closeSet = new Set(
    history
      .map(point => Number(point.close))
      .filter(value => Number.isFinite(value))
      .map(value => value.toFixed(4))
  )
  return closeSet.size >= 4
})

const chartTheme = computed(() => {
  if (isDark.value) {
    return {
      axisLabelColor: '#A1A1AA',
      axisLineColor: 'rgba(113, 113, 122, 0.26)',
      splitLineColor: 'rgba(113, 113, 122, 0.14)',
    }
  }
  return {
    axisLabelColor: '#9CA3AF',
    axisLineColor: '#E5E7EB',
    splitLineColor: '#F1F5F9',
  }
})

const stockChartOption = computed(() => {
  const isLine = chartMode.value === 'line'
  const linePoints = lineSeriesData.value
  const candlePoints = candleSeriesData.value
  const sourcePoints = isLine ? linePoints : candlePoints
  const categories = sourcePoints.map((point) => formatChartTimeLabel(point.ts, isLine))
  const hasData = categories.length > 0

  const emptyOption = {
    animation: false,
    grid: { left: 44, right: 16, top: 18, bottom: 34 },
    xAxis: {
      type: 'category',
      data: [],
      axisLabel: { color: chartTheme.value.axisLabelColor, fontSize: 11 },
      axisLine: { lineStyle: { color: chartTheme.value.axisLineColor } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { color: chartTheme.value.axisLabelColor, fontSize: 11 },
      splitLine: { lineStyle: { color: chartTheme.value.splitLineColor } },
    },
    series: [],
  }
  if (!hasData) return emptyOption

  return {
    animation: false,
    grid: { left: 44, right: 16, top: 18, bottom: 34 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any[]) => {
        const item = params?.[0]
        if (!item) return ''
        const index = Number(item.dataIndex || 0)
        const label = categories[index] || ''
        if (isLine) {
          const value = Number(linePoints[index]?.value || 0)
          return `${label}<br/>${formatPrice(value)}`
        }
        const row = candlePoints[index]
        if (!row) return label
        return `${label}<br/>开 ${formatPrice(row.open)} 高 ${formatPrice(row.high)}<br/>低 ${formatPrice(row.low)} 收 ${formatPrice(row.close)}`
      },
    },
    xAxis: {
      type: 'category',
      data: categories,
      axisLabel: { color: chartTheme.value.axisLabelColor, fontSize: 11 },
      axisLine: { lineStyle: { color: chartTheme.value.axisLineColor } },
      splitLine: { show: false },
      boundaryGap: isLine,
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: {
        color: chartTheme.value.axisLabelColor,
        fontSize: 11,
      },
      splitLine: { lineStyle: { color: chartTheme.value.splitLineColor } },
    },
    series: isLine
      ? [
          {
            type: 'line',
            smooth: 0.2,
            showSymbol: false,
            data: linePoints.map(point => Number(point.value)),
            lineStyle: { width: 2, color: '#2563EB' },
            areaStyle: { color: 'rgba(37, 99, 235, 0.16)' },
          },
        ]
      : [
          {
            type: 'candlestick',
            data: candlePoints.map(point => [point.open, point.close, point.low, point.high]),
            itemStyle: {
              color: '#16A34A',
              color0: '#EF4444',
              borderColor: '#16A34A',
              borderColor0: '#EF4444',
            },
          },
        ],
  }
})

function computeReturn(days: number): number | null {
  const history = detailData.value?.history || []
  if (days > 1 && !hasMeaningfulHistory.value) return null
  if (!history.length) return null
  const sorted = [...history].sort((a, b) => a.ts - b.ts)
  if (sorted.length < 2) return null
  const lastClose = quotePrice.value || Number(sorted[sorted.length - 1]?.close || 0)
  if (!lastClose) return null
  const totalSpanDays = (sorted[sorted.length - 1].ts - sorted[0].ts) / 86_400_000
  if (sorted.length < Math.max(8, Math.floor(days / 2)) && totalSpanDays > days * 4) {
    return null
  }
  const targetTs = Date.now() - days * 24 * 60 * 60 * 1000
  const fallbackBase = Number(sorted[0]?.close || 0)
  const targetBase = [...sorted].reverse().find(point => point.ts <= targetTs)
  const base = Number(targetBase?.close || fallbackBase)
  if (!base) return null
  return ((lastClose - base) / base) * 100
}

const returnStats = computed(() => ({
  r1d: quoteChangePct.value,
  r5d: computeReturn(5),
  r30d: computeReturn(30),
  r90d: computeReturn(90),
}))

function formatPrice(value: number) {
  const prefix = marketKey === 'us' ? '$' : marketKey === 'hk' ? 'HK$' : '¥'
  return `${prefix}${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatMoney(value: string | number) {
  const n = Number(value || 0)
  return `¥${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatPercent(value: number | null) {
  if (value === null || !Number.isFinite(value)) return '--'
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

function resolveReturnClass(value: number | null) {
  if (value === null || !Number.isFinite(value)) return 'text-main'
  return cc.textClass(value)
}

function formatTime(value: string) {
  return new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
}

function setChartMode(mode: 'line' | 'candlestick') {
  chartMode.value = mode
  if (mode === 'line') {
    void refreshIntraday()
  }
}

function setChartSpan(value: string) {
  if (chartMode.value === 'line') {
    if (value === '1d' || value === '5d') {
      intradaySpan.value = value
      void refreshIntraday()
    }
    return
  }
  if (value === '30' || value === '90' || value === '180') {
    candleSpanDays.value = Number(value) as CandleSpanDays
  }
}

function formatChartTimeLabel(ts: number, isLine: boolean) {
  const date = new Date(ts)
  if (isLine) {
    return date.toLocaleString('zh-CN', {
      timeZone: 'Asia/Shanghai',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  }
  return date.toLocaleDateString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
  })
}

function formatChartSourceLabel(value: string) {
  switch (value) {
    case 'yahoo_chart':
      return 'Yahoo Finance'
    case 'tencent_kline':
      return '腾讯行情'
    case 'nasdaq_historical':
      return 'NASDAQ Historical'
    case 'nasdaq_chart':
      return 'NASDAQ Chart'
    case 'stooq_csv':
      return 'Stooq'
    case 'history_projection':
      return '历史收盘投影'
    case 'quote_flat':
      return '最新报价回填'
    case 'route_fallback':
      return '站内兜底数据'
    default:
      return '聚合行情'
  }
}

function stopWorker() {
  if (refreshWorker !== null) {
    window.clearInterval(refreshWorker)
    refreshWorker = null
  }
}

function shouldRunWorker() {
  return detailData.value?.quote?.market_status === 'open' && !document.hidden
}

function ensureWorker() {
  stopWorker()
  if (!shouldRunWorker()) return
  refreshWorker = window.setInterval(async () => {
    if (!shouldRunWorker()) {
      stopWorker()
      return
    }
    await Promise.all([refreshIntraday(), refreshDetail()])
  }, REFRESH_INTERVAL_MS)
}

watch(() => detailData.value?.quote?.market_status, () => {
  ensureWorker()
}, { immediate: true })

onMounted(() => {
  const onVisible = () => {
    if (document.hidden) {
      stopWorker()
      return
    }
    void refreshIntraday()
    void refreshDetail()
    ensureWorker()
  }
  document.addEventListener('visibilitychange', onVisible)
  removeVisibilityListener = () => document.removeEventListener('visibilitychange', onVisible)
})

onBeforeUnmount(() => {
  stopWorker()
  removeVisibilityListener?.()
  removeVisibilityListener = null
})

useHead({
  title: computed(() => `${ticker.value} · ${stockName.value} - 市场详情`),
})
</script>
