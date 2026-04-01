<template>
  <div class="card bg-overlay overflow-hidden">
    <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        <div class="text-[11px] uppercase tracking-[0.2em] text-tertiary">行情预览</div>
        <h2 class="mt-2 text-2xl font-bold text-main tracking-tight">市场总览</h2>
        <p class="mt-2 max-w-2xl text-sm leading-7 text-secondary">
          美股、A 股、港股主要指数与盘口快照。
        </p>
        <div class="mt-2">
          <MarketDataTimestamp :timestamp="overviewData.updated_at" />
        </div>
      </div>
      <NuxtLink
        to="/market"
        class="inline-flex items-center justify-center rounded-2xl bg-overlay-2 px-4 py-3 text-sm font-semibold text-main transition hover:-translate-y-0.5"
      >
        查看完整行情
      </NuxtLink>
    </div>

    <!-- Simple US/CN Markets List -->
    <div class="mt-6">
      <div v-if="overviewPending && !marketSections.length" class="space-y-2">
        <div v-for="n in 3" :key="n" class="flex items-center gap-4 px-4 py-3 rounded-2xl bg-overlay-2 animate-pulse">
          <div class="h-4 w-16 rounded bg-zinc-200 dark:bg-zinc-700"></div>
          <div class="flex-1 h-4 rounded bg-zinc-200 dark:bg-zinc-700"></div>
          <div class="h-4 w-24 rounded bg-zinc-200 dark:bg-zinc-700"></div>
        </div>
      </div>

      <div v-else class="space-y-2">
        <div
          v-for="section in marketSections"
          :key="section.key"
          class="rounded-3xl border px-5 py-5"
          :class="section.cardTone"
        >
          <div class="flex items-start justify-between gap-4">
            <div>
              <div>
                <span class="inline-flex items-center rounded-full border border-white/40 bg-white/30 px-2 py-0.5 text-[10px] uppercase tracking-widest text-zinc-700 backdrop-blur-md dark:border-zinc-700/60 dark:bg-zinc-900/35 dark:text-zinc-200">
                  {{ section.badge }}
                </span>
              </div>
              <div class="mt-2 text-base font-bold text-main">{{ section.title }}</div>
            </div>

            <NuxtLink
              :to="`/market-detail/${section.key}`"
              class="flex-shrink-0 text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline"
            >
              查看详情 →
            </NuxtLink>
          </div>

          <div class="mt-5 space-y-5">
            <div class="grid grid-cols-2 gap-x-8 gap-y-5 sm:grid-cols-4">
              <div>
                <div class="text-[10px] uppercase tracking-[0.16em] text-tertiary">股票数</div>
                <div class="numeric-mono mt-2 text-3xl leading-none text-main">{{ section.stockCount }}</div>
              </div>
              <div>
                <div class="text-[10px] uppercase tracking-[0.16em] text-tertiary">上涨</div>
                <div class="numeric-mono mt-2 text-3xl leading-none text-emerald-600 dark:text-emerald-400">{{ section.upCount }}</div>
              </div>
              <div>
                <div class="text-[10px] uppercase tracking-[0.16em] text-tertiary">下跌</div>
                <div class="numeric-mono mt-2 text-3xl leading-none text-rose-600 dark:text-rose-400">{{ section.downCount }}</div>
              </div>
              <div>
                <div class="text-[10px] uppercase tracking-[0.16em] text-tertiary">平盘</div>
                <div class="numeric-mono mt-2 text-3xl leading-none text-main">{{ section.flatCount }}</div>
              </div>
            </div>

            <div class="grid grid-cols-1 gap-x-12 gap-y-4 border-t border-zinc-200/60 pt-4 sm:grid-cols-3 dark:border-zinc-800/60">
              <div
                v-for="index in section.indices.slice(0, 3)"
                :key="index.symbol"
                class="min-w-0"
              >
                <div class="text-[10px] uppercase tracking-[0.16em] text-tertiary">{{ index.shortLabel }}</div>
                <div class="numeric-mono mt-2 text-[16px] leading-tight text-main">{{ index.value }}</div>
                <div
                  class="numeric-mono mt-1 text-xs leading-none"
                  :class="index.changePct == null ? 'text-tertiary' : cc.textClass(index.changePct)"
                >
                  {{ index.changePct == null ? '--' : formatPercent(index.changePct) }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Market Panel Section -->
    <section class="mt-6 rounded-3xl border border-zinc-200/70 bg-white/75 p-5 dark:border-zinc-800/70 dark:bg-zinc-950/50">
      <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div class="text-[11px] uppercase tracking-[0.2em] text-tertiary">市场看盘</div>
          <h3 class="mt-2 text-xl font-bold text-main tracking-tight">{{ panelTitle }}</h3>
          <div class="mt-2">
            <MarketDataTimestamp :timestamp="overviewData.updated_at" />
          </div>
        </div>
        <div class="flex items-center gap-2 text-xs text-tertiary">
          <span>{{ panelStatLabel }}</span>
          <button
            type="button"
            class="rounded-xl bg-overlay-2 px-3 py-2 font-medium text-secondary transition hover:text-main"
            @click="toggleSort"
          >
            {{ sortButtonLabel }}
          </button>
        </div>
      </div>

      <div class="mt-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div class="flex flex-wrap items-center gap-3">
          <div class="flex items-center gap-[6px] rounded-xl bg-overlay-2 p-[6px] w-fit">
            <button
              v-for="option in marketOptions"
              :key="option.value"
              type="button"
              class="px-3 py-1 rounded-lg text-sm transition-all select-none"
              :class="selectedMarket === option.value ? 'bg-blue-600 text-white font-medium' : 'text-zinc-400 hover:text-main'"
              @click="selectedMarket = option.value"
            >
              {{ option.label }}
            </button>
          </div>
          <div class="flex items-center gap-[6px] rounded-xl bg-overlay-2 p-[6px] w-fit">
            <button
              v-for="option in panelOptions"
              :key="option.value"
              type="button"
              class="px-3 py-1 rounded-lg text-sm transition-all select-none"
              :class="panelMode === option.value ? 'bg-blue-600 text-white font-medium' : 'text-zinc-400 hover:text-main'"
              @click="panelMode = option.value"
            >
              {{ option.label }}
            </button>
          </div>
        </div>

        <NuxtLink
          :to="`/market-detail/${selectedMarket}`"
          class="inline-flex items-center justify-center rounded-2xl bg-overlay-2 px-4 py-3 text-sm font-semibold text-main transition hover:-translate-y-0.5"
        >
          进入当前市场看盘
        </NuxtLink>
      </div>

      <div v-if="panelPending" class="mt-5 space-y-2">
        <div v-for="n in 6" :key="n" class="rounded-2xl bg-overlay-2/60 px-4 py-3 animate-pulse">
          <div class="flex items-center justify-between gap-4">
            <div class="space-y-2">
              <div class="h-3 w-16 rounded bg-zinc-200 dark:bg-zinc-700"></div>
              <div class="h-2.5 w-24 rounded bg-zinc-200 dark:bg-zinc-700"></div>
            </div>
            <div class="space-y-2 text-right">
              <div class="h-3 w-14 rounded bg-zinc-200 dark:bg-zinc-700 ml-auto"></div>
              <div class="h-2.5 w-12 rounded bg-zinc-200 dark:bg-zinc-700 ml-auto"></div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="mt-5 divide-y divide-zinc-200 dark:divide-zinc-700">
        <template v-if="panelMode === 'movers'">
          <div v-for="(item, index) in sortedBoardItems.slice(0, 6)" :key="item.ticker" class="flex items-center gap-3 py-3">
            <div class="w-6 text-center text-xs font-bold flex-shrink-0" :class="index < 3 ? 'text-amber-500' : 'text-tertiary'">
              {{ index + 1 }}
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="font-mono text-main font-bold text-sm">{{ item.ticker }}</span>
                <span class="h-1.5 w-1.5 rounded-full" :class="item.market_status === 'open' ? 'bg-emerald-500' : 'bg-zinc-300 dark:bg-zinc-600'"></span>
              </div>
              <div class="truncate text-[10px] text-tertiary">{{ item.name }}</div>
            </div>
            <div class="hidden sm:block flex-shrink-0">
              <MarketTrendSparkline :seed="item.ticker" :change="item.change_pct" />
            </div>
            <div class="text-right flex-shrink-0">
              <div class="text-sm font-bold text-main tabular-nums">{{ formatPrice(item.price, selectedMarket) }}</div>
              <div class="text-xs font-bold tabular-nums" :class="cc.textClass(item.change_pct)">
                {{ formatPercent(item.change_pct) }}
              </div>
            </div>
          </div>
        </template>

        <template v-else>
          <div v-if="!filteredHotActivityItems.length" class="py-12 text-center text-sm text-tertiary">
            当前还没有足够的 Agent 操作热度数据。
          </div>
          <div v-for="(item, index) in filteredHotActivityItems.slice(0, 6)" :key="`${selectedMarket}-${item.ticker}`" class="flex items-center gap-3 py-3">
            <div class="w-6 text-center text-xs font-bold flex-shrink-0" :class="index < 3 ? 'text-amber-500' : 'text-tertiary'">
              {{ index + 1 }}
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="font-mono text-main font-bold text-sm">{{ item.ticker }}</span>
                <span class="rounded-full bg-overlay-2 px-2 py-0.5 text-[10px] text-tertiary">{{ item.tradeCount }} 笔</span>
              </div>
              <div class="mt-1 truncate text-[10px] text-tertiary">{{ item.name }}</div>
              <div class="mt-1 truncate text-[10px] text-secondary">{{ item.agentSampleLabel }}</div>
            </div>
            <div class="text-right flex-shrink-0">
              <div class="text-sm font-bold text-main tabular-nums">{{ formatPrice(item.lastPrice, selectedMarket) }}</div>
              <div class="mt-1 text-xs text-secondary tabular-nums">买入 {{ item.buyCount }} / 卖出 {{ item.sellCount }}</div>
              <div class="mt-1 text-xs font-bold tabular-nums" :class="cc.textClass(item.changePct)">
                {{ formatPercent(item.changePct) }}
              </div>
            </div>
          </div>
        </template>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import MarketTrendSparkline from '../market/MarketTrendSparkline.vue'
import MarketDataTimestamp from '../market/MarketDataTimestamp.vue'

type MarketKey = 'us' | 'cn' | 'hk'
type PanelMode = 'movers' | 'activity'
type SortDirection = 'desc' | 'asc'

interface BoardItem {
  ticker: string
  name: string
  market: MarketKey
  price: number
  change_pct: number
  volume: number | null
  market_status: string
}

interface MarketSummary {
  market: MarketKey
  name: string
  stock_count: number
  up_count: number
  down_count: number
  flat_count: number
  avg_change_pct: number
  leader?: BoardItem | null
  laggard?: BoardItem | null
}

interface IndexSnapshot {
  symbol: string
  name: string
  price: number
  change_pct: number
  market: MarketKey
}

interface MarketOverviewResponse {
  indices: IndexSnapshot[]
  boards: Record<MarketKey, BoardItem[]>
  markets: MarketSummary[]
  updated_at?: string
}

interface FeedItem {
  id: number
  agent_id: string
  agent_name: string
  agent_avatar: string
  action: 'buy' | 'sell'
  ticker: string
  amount: number
  created_at: string
}

interface HotActivityItem {
  ticker: string
  name: string
  tradeCount: number
  buyCount: number
  sellCount: number
  amountTotal: number
  lastPrice: number
  changePct: number
  agentSampleLabel: string
}

const cc = useColorConvention()

const marketOptions = [
  { label: '美股', value: 'us' },
  { label: 'A 股', value: 'cn' },
  { label: '港股', value: 'hk' },
] as const

const panelOptions = [
  { label: '盘口强弱', value: 'movers' },
  { label: 'Agent 热门操作', value: 'activity' },
] as const

const MARKET_META: Record<MarketKey, { badge: string; title: string; shortTitle: string; cardTone: string }> = {
  us: {
    badge: 'UNITED STATES',
    title: '美股市场',
    shortTitle: '美股',
    cardTone: 'border-blue-200/70 bg-blue-50/45 dark:border-blue-900/40 dark:bg-blue-950/20',
  },
  cn: {
    badge: 'CHINA MAINLAND',
    title: 'A 股市场',
    shortTitle: 'A 股',
    cardTone: 'border-rose-200/70 bg-rose-50/45 dark:border-rose-900/40 dark:bg-rose-950/20',
  },
  hk: {
    badge: 'HONG KONG',
    title: '港股市场',
    shortTitle: '港股',
    cardTone: 'border-emerald-200/70 bg-emerald-50/45 dark:border-emerald-900/40 dark:bg-emerald-950/20',
  },
}

const INDEX_META: Record<string, { shortLabel: string }> = {
  SPX: { shortLabel: '标普 500' },
  NDX: { shortLabel: '纳指' },
  DJI: { shortLabel: '道指' },
  SH: { shortLabel: '上证' },
  SZ: { shortLabel: '深成指' },
  CY: { shortLabel: '创业板' },
  HSI: { shortLabel: '恒生指数' },
  HSCEI: { shortLabel: '恒生国企' },
}

const MARKET_INDEX_ORDER: Record<MarketKey, string[]> = {
  us: ['SPX', 'NDX', 'DJI'],
  cn: ['SH', 'SZ', 'CY'],
  hk: ['HSI', 'HSCEI'],
}

const { data: overviewData, pending: overviewPending } = useLazyFetch<MarketOverviewResponse>('/api/market/overview', {
  key: 'home-market-overview',
  default: () => ({
    indices: [],
    boards: { us: [], cn: [], hk: [] },
    markets: [],
    updated_at: '',
  }),
  deep: false,
})

const {
  data: feedItems,
  pending: feedPending,
  refresh: refreshFeedItems,
} = useLazyFetch<FeedItem[]>('/api/feed', {
  key: 'home-market-activity-feed',
  query: { limit: 80 },
  default: () => [],
  immediate: false,
  deep: false,
})

const selectedMarket = shallowRef<MarketKey>('us')
const panelMode = shallowRef<PanelMode>('movers')
const sortDirection = shallowRef<SortDirection>('desc')
const hasRequestedFeed = shallowRef(false)

const boardItems = computed(() => overviewData.value.boards?.[selectedMarket.value] || [])
const boardItemMap = computed(() => new Map(boardItems.value.map(item => [item.ticker, item])))
const boardTickerSet = computed(() => new Set(boardItems.value.map(item => item.ticker)))

const marketSections = computed(() => {
  return (Object.keys(MARKET_META) as MarketKey[]).map((key) => {
    const summary = overviewData.value.markets?.find(item => item.market === key)
    const marketIndexMap = new Map(
      (overviewData.value.indices || [])
        .filter(item => item.market === key)
        .map(item => [item.symbol, item]),
    )

    const fallbackSymbols = MARKET_INDEX_ORDER[key] || []
    const indices = fallbackSymbols.map((symbol) => {
      const item = marketIndexMap.get(symbol)
      return {
        symbol,
        shortLabel: INDEX_META[symbol]?.shortLabel || symbol,
        value: item ? formatIndexValue(item.price) : '--',
        changePct: item?.change_pct ?? null,
      }
    })

    return {
      key,
      ...MARKET_META[key],
      stockCount: summary?.stock_count || 0,
      upCount: summary?.up_count || 0,
      downCount: summary?.down_count || 0,
      flatCount: summary?.flat_count || 0,
      avgChangePct: summary?.avg_change_pct || 0,
      leader: summary?.leader || null,
      laggard: summary?.laggard || null,
      indices,
    }
  })
})

const sortedBoardItems = computed(() => {
  const direction = sortDirection.value === 'desc' ? -1 : 1
  return [...boardItems.value].sort((a, b) => {
    if (a.change_pct === b.change_pct) return a.ticker.localeCompare(b.ticker)
    return (a.change_pct - b.change_pct) * direction
  })
})

const hotActivityItems = computed<HotActivityItem[]>(() => {
  const grouped = new Map<string, HotActivityItem & { agentNames: Set<string> }>()

  for (const item of feedItems.value) {
    if (!boardTickerSet.value.has(item.ticker)) continue

    const boardItem = boardItemMap.value.get(item.ticker)
    const existing = grouped.get(item.ticker) || {
      ticker: item.ticker,
      name: boardItem?.name || item.ticker,
      tradeCount: 0,
      buyCount: 0,
      sellCount: 0,
      amountTotal: 0,
      lastPrice: Number(boardItem?.price || 0),
      changePct: Number(boardItem?.change_pct || 0),
      agentSampleLabel: '',
      agentNames: new Set<string>(),
    }

    existing.tradeCount += 1
    existing.amountTotal += Number(item.amount || 0)
    existing.lastPrice = Number(boardItem?.price || existing.lastPrice || 0)
    existing.changePct = Number(boardItem?.change_pct || existing.changePct || 0)
    existing.agentNames.add(item.agent_name)
    if (item.action === 'buy') existing.buyCount += 1
    else existing.sellCount += 1

    grouped.set(item.ticker, existing)
  }

  return Array.from(grouped.values()).map((item) => {
    const names = Array.from(item.agentNames)
    return {
      ticker: item.ticker,
      name: item.name,
      tradeCount: item.tradeCount,
      buyCount: item.buyCount,
      sellCount: item.sellCount,
      amountTotal: item.amountTotal,
      lastPrice: item.lastPrice,
      changePct: item.changePct,
      agentSampleLabel: names.length > 2 ? `${names.slice(0, 2).join('、')} 等 ${names.length} 位 Agent` : names.join('、'),
    }
  })
})

const filteredHotActivityItems = computed(() => {
  const direction = sortDirection.value === 'desc' ? -1 : 1
  return [...hotActivityItems.value].sort((a, b) => {
    if (a.tradeCount === b.tradeCount) {
      return (a.amountTotal - b.amountTotal) * direction
    }
    return (a.tradeCount - b.tradeCount) * direction
  })
})

const panelPending = computed(() => panelMode.value === 'activity' ? feedPending.value : overviewPending.value)
const panelTitle = computed(() => panelMode.value === 'activity' ? 'Agent 热门操作' : '盘口强弱')
const panelStatLabel = computed(() => {
  if (panelMode.value === 'activity') {
    return `热门标的 ${filteredHotActivityItems.value.length} 只`
  }
  return `当前市场 ${sortedBoardItems.value.length} 只股票`
})
const sortButtonLabel = computed(() => {
  if (panelMode.value === 'activity') {
    return sortDirection.value === 'desc' ? '热度优先' : '冷门优先'
  }
  return sortDirection.value === 'desc' ? '涨幅优先' : '跌幅优先'
})

watch(panelMode, async (mode) => {
  if (mode !== 'activity' || hasRequestedFeed.value) {
    return
  }

  hasRequestedFeed.value = true
  await refreshFeedItems()
}, { immediate: true })

function toggleSort() {
  sortDirection.value = sortDirection.value === 'desc' ? 'asc' : 'desc'
}

function formatPercent(value?: number | null) {
  const numeric = Number(value || 0)
  return `${numeric >= 0 ? '+' : ''}${numeric.toFixed(2)}%`
}

function formatPrice(
  value: number,
  market: MarketKey,
  options: Intl.NumberFormatOptions = { minimumFractionDigits: 2, maximumFractionDigits: 2 },
) {
  const currency = market === 'us' ? '$' : market === 'hk' ? 'HK$' : '¥'
  return `${currency}${Number(value).toLocaleString('en-US', options)}`
}

function formatIndexValue(value: number) {
  return Number(value).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}
</script>

<style scoped>
.numeric-mono {
  font-family: ui-monospace, "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum" 1;
  letter-spacing: 0;
  font-weight: 700;
}
</style>
