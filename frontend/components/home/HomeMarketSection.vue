<template>
  <div>
    <!-- Loading -->
    <div v-if="overviewPending && !marketSections.length" class="space-y-3">
      <div v-for="n in 3" :key="n" class="card animate-pulse">
        <div class="h-4 w-16 bg-border rounded mb-2"></div>
        <div class="h-8 w-32 bg-border rounded"></div>
      </div>
    </div>

    <!-- Markets -->
    <div v-else class="space-y-4">
      <div
        v-for="section in marketSections"
        :key="section.key"
        class="card"
      >
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center gap-3">
            <span class="text-2xl">{{ section.emoji }}</span>
            <div>
              <div class="label">{{ section.badge }}</div>
              <div class="flex items-center gap-2">
                <div class="font-body text-body-sm text-primary">{{ section.title }}</div>
                <span
                  class="inline-flex items-center border px-2 py-[2px] font-mono text-[10px] leading-none tracking-[0.08em]"
                  :class="getStatusBadgeClass(section.marketStatus)"
                >
                  {{ formatStatus(section.marketStatus) }}
                </span>
                <span
                  class="inline-flex items-center border border-border-visible bg-transparent px-2 py-[2px] font-mono text-[10px] leading-none tracking-[0.08em] text-secondary"
                >
                  交易时段 {{ section.sessionWindows }}
                </span>
              </div>
            </div>
          </div>
          <NuxtLink
            :to="`/market-detail/${section.key}`"
            class="font-mono text-caption text-secondary hover:text-primary transition-colors"
          >
            查看 →
          </NuxtLink>
        </div>

        <!-- Stats -->
        <div class="grid grid-cols-4 gap-4 mb-4">
          <div>
            <div class="label mb-1">股票数</div>
            <div class="font-mono type-subheading numeric">{{ section.stockCount }}</div>
          </div>
          <div>
            <div class="label mb-1">上涨</div>
            <div class="font-mono type-subheading numeric text-success">{{ section.upCount }}</div>
          </div>
          <div>
            <div class="label mb-1">下跌</div>
            <div class="font-mono type-subheading numeric text-accent">{{ section.downCount }}</div>
          </div>
          <div>
            <div class="label mb-1">平盘</div>
            <div class="font-mono type-subheading numeric">{{ section.flatCount }}</div>
          </div>
        </div>

        <!-- Indices -->
        <div class="grid grid-cols-3 gap-3 pt-4 border-t border-border">
          <div
            v-for="index in section.indices.slice(0, 3)"
            :key="index.symbol"
          >
            <div class="label mb-1">{{ index.shortLabel }}</div>
            <div class="font-mono text-body-sm numeric text-primary">{{ index.value }}</div>
            <div
              class="font-mono text-caption numeric"
              :class="index.changePct == null ? 'text-disabled' : getChangeColor(index.changePct)"
            >
              {{ index.changePct == null ? '--' : formatPercent(index.changePct) }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
type MarketKey = 'us' | 'cn' | 'hk'

interface IndexSnapshot {
  symbol: string
  name: string
  price: number
  change_pct: number
  market: MarketKey
}

interface MarketSummary {
  market: MarketKey
  name: string
  market_status?: string
  timezone?: string
  session_windows?: string[]
  now_local?: string | null
  next_open_local?: string | null
  stock_count: number
  up_count: number
  down_count: number
  flat_count: number
}

interface MarketOverviewResponse {
  indices: IndexSnapshot[]
  markets: MarketSummary[]
  updated_at?: string
}

const { isCN } = useColorConvention()

const MARKET_META: Record<MarketKey, { badge: string; title: string; emoji: string }> = {
  us: { badge: '美国', title: '美股市场', emoji: '🇺🇸' },
  cn: { badge: '中国内地', title: 'A 股市场', emoji: '🇨🇳' },
  hk: { badge: '中国香港', title: '港股市场', emoji: '🇭🇰' },
}

const INDEX_META: Record<string, { shortLabel: string }> = {
  SPX: { shortLabel: 'S&P 500' },
  NDX: { shortLabel: 'NASDAQ' },
  DJI: { shortLabel: 'DOW JONES' },
  SH: { shortLabel: 'SHANGHAI' },
  SZ: { shortLabel: 'SHENZHEN' },
  CY: { shortLabel: 'CHINEXT' },
  HSI: { shortLabel: 'HANG SENG' },
  HSCEI: { shortLabel: 'HSCEI' },
}

const MARKET_INDEX_ORDER: Record<MarketKey, string[]> = {
  us: ['SPX', 'NDX', 'DJI'],
  cn: ['SH', 'SZ', 'CY'],
  hk: ['HSI', 'HSCEI'],
}

const { data: overviewData, pending: overviewPending } = useLazyFetch<MarketOverviewResponse>('/api/market/overview', {
  key: 'home-market-overview',
  default: () => ({ indices: [], markets: [], updated_at: '' }),
  deep: false,
})

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
      marketStatus: summary?.market_status || 'closed',
      sessionWindows: formatSessionWindows(summary?.session_windows),
      indices,
    }
  })
})

function getChangeColor(change: number | undefined): string {
  if (change === undefined) return 'text-disabled'
  if (isCN.value) {
    return change >= 0 ? 'text-success' : 'text-accent'
  }
  return change >= 0 ? 'text-accent' : 'text-success'
}

function formatPercent(value?: number | null) {
  const numeric = Number(value || 0)
  return `${numeric >= 0 ? '+' : ''}${numeric.toFixed(2)}%`
}

function formatIndexValue(value: number) {
  return Number(value).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatStatus(status: string): string {
  if (status === 'open') return '开盘'
  if (status === 'closed') return '休市'
  return '--'
}

function getStatusBadgeClass(status: string): string {
  if (status === 'open') return 'text-white border-[#4A9E5C] bg-[#4A9E5C]'
  if (status === 'closed') return 'text-[#7a7a7a] border-[#d9d9d9] bg-[#efefef]'
  return 'text-secondary border-[#2a2a2d] bg-[#0d0e10]'
}

function formatSessionWindows(sessionWindows: string[] | undefined): string {
  if (!sessionWindows?.length) return '--'
  return sessionWindows.join(' / ')
}

</script>
