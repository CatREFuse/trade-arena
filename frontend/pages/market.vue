<template>
  <div class="max-w-4xl mx-auto px-6 py-12 md:py-16">
    <!-- Header -->
    <section class="mb-12">
      <div class="label mb-4">MARKET OVERVIEW</div>
      <h1 class="type-display-md mb-4">三地市场，一页看清</h1>
      <p class="type-body text-secondary max-w-xl mb-6">
        美股、A 股、港股主要指数与盘口快照
      </p>

      <div class="flex items-center gap-4">
        <MarketDataTimestamp :timestamp="overviewData.updated_at" />
        <button
          type="button"
          class="btn-secondary"
          :disabled="isLoading"
          @click="manualRefresh"
        >
          {{ isLoading ? 'LOADING...' : 'REFRESH' }}
        </button>
      </div>
    </section>

    <!-- FX Section -->
    <section class="card mb-8">
      <div class="flex items-center justify-between mb-6">
        <h2 class="type-heading">FOREX</h2>
        <MarketDataTimestamp :timestamp="fxOverview.updated_at" />
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div
          v-for="pair in fxOverview.pairs"
          :key="pair.pair"
          class="card-raised"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="label">{{ pair.pair }}</span>
            <span
              class="numeric font-mono text-body-sm"
              :class="getChangeColor(pair.change_pct_24h)"
            >
              {{ formatPercent(pair.change_pct_24h) }}
            </span>
          </div>
          <div class="numeric font-mono type-display-lg">
            {{ formatFxRate(pair.rate) }}
          </div>
          <div v-if="pair.history_source || pair.source" class="mt-2 font-mono text-caption text-disabled">
            Source: {{ formatFxSource(pair.history_source || pair.source) }}
          </div>
        </div>
      </div>
    </section>

    <!-- US Market -->
    <MarketCard
      title="美股市场"
      emoji="🇺🇸"
      badge="UNITED STATES"
      :summary="usSummary"
      :indices="usIndices"
      market-type="us"
      :is-cn="isCN"
    />

    <!-- CN Market -->
    <MarketCard
      title="A 股市场"
      emoji="🇨🇳"
      badge="CHINA MAINLAND"
      :summary="cnSummary"
      :indices="cnIndices"
      market-type="cn"
      :is-cn="isCN"
      class="mt-6"
    />

    <!-- HK Market -->
    <MarketCard
      title="港股市场"
      emoji="🇭🇰"
      badge="HONG KONG"
      :summary="hkSummary"
      :indices="hkIndices"
      market-type="hk"
      :is-cn="isCN"
      class="mt-6"
    />
  </div>
</template>

<script setup lang="ts">
useHead({
  title: 'MARKET - CocoLoop Trade Arena',
})

const { isCN } = useColorConvention()

const { data: overviewData, pending: isLoading } = useLazyFetch('/api/market/overview', {
  default: () => ({
    us: { summary: {}, indices: [] },
    cn: { summary: {}, indices: [] },
    hk: { summary: {}, indices: [] },
    updated_at: null,
  }),
})

const { data: fxOverview } = useLazyFetch('/api/market/fx-overview', {
  default: () => ({ pairs: [], updated_at: null }),
})

const usSummary = computed(() => overviewData.value?.us?.summary || {})
const cnSummary = computed(() => overviewData.value?.cn?.summary || {})
const hkSummary = computed(() => overviewData.value?.hk?.summary || {})

const usIndices = computed(() => getMarketIndices('us'))
const cnIndices = computed(() => getMarketIndices('cn'))
const hkIndices = computed(() => getMarketIndices('hk'))

type MarketKey = 'us' | 'cn' | 'hk'

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

interface IndexSnapshot {
  symbol: string
  name: string
  price: number
  change_pct: number
  market: MarketKey
}

interface MarketOverviewResponse {
  indices: IndexSnapshot[]
  markets: Array<{
    market: MarketKey
    summary: any
  }>
  updated_at?: string
}

function getMarketIndices(market: MarketKey) {
  const marketIndexMap = new Map(
    (overviewData.value.indices || [])
      .filter((item: IndexSnapshot) => item.market === market)
      .map((item: IndexSnapshot) => [item.symbol, item]),
  )

  const fallbackSymbols = MARKET_INDEX_ORDER[market] || []
  return fallbackSymbols.map((symbol) => {
    const item = marketIndexMap.get(symbol)
    return {
      symbol,
      shortLabel: INDEX_META[symbol]?.shortLabel || symbol,
      value: item ? formatIndexValue(item.price) : '--',
      changePct: item?.change_pct ?? null,
    }
  })
}

function manualRefresh() {
  refreshNuxtData()
}

function formatFxRate(rate: number | undefined | null): string {
  if (rate == null || Number.isNaN(rate)) return '--'
  return rate.toFixed(4)
}

function formatPercent(value: number | undefined | null): string {
  if (value == null || Number.isNaN(value)) return '--'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function formatFxSource(source: string): string {
  const sourceMap: Record<string, string> = {
    'yahoo': 'Yahoo Finance',
    'alphavantage': 'Alpha Vantage',
    'exchangerate': 'Exchange Rate API',
    'fallback': 'Fallback',
  }
  return sourceMap[source] || source
}

function getChangeColor(change: number | undefined | null): string {
  if (change == null || Number.isNaN(change)) return 'text-disabled'
  if (isCN.value) {
    return change >= 0 ? 'text-success' : 'text-accent'
  }
  return change >= 0 ? 'text-accent' : 'text-success'
}

function formatIndexValue(value: number) {
  return Number(value).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}
</script>
