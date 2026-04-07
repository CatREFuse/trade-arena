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
      title="US MARKET"
      emoji="🇺🇸"
      :summary="usSummary"
      :indices="usIndices"
      :market-type="'us'"
      :is-cn="isCN"
    />

    <!-- CN Market -->
    <MarketCard
      title="A-SHARE MARKET"
      emoji="🇨🇳"
      :summary="cnSummary"
      :indices="cnIndices"
      :market-type="'cn'"
      :is-cn="isCN"
      class="mt-6"
    />

    <!-- HK Market -->
    <MarketCard
      title="HK MARKET"
      emoji="🇭🇰"
      :summary="hkSummary"
      :indices="hkIndices"
      :market-type="'hk'"
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
const overviewData = ref({
  us: { summary: {}, indices: [] },
  cn: { summary: {}, indices: [] },
  hk: { summary: {}, indices: [] },
  updated_at: null,
})
const fxOverview = ref({ pairs: [], updated_at: null })
const isLoading = ref(false)

const usSummary = computed(() => overviewData.value.us?.summary || {})
const cnSummary = computed(() => overviewData.value.cn?.summary || {})
const hkSummary = computed(() => overviewData.value.hk?.summary || {})

const usIndices = computed(() => overviewData.value.us?.indices || [])
const cnIndices = computed(() => overviewData.value.cn?.indices || [])
const hkIndices = computed(() => overviewData.value.hk?.indices || [])

async function fetchData() {
  isLoading.value = true
  try {
    const [overviewRes, fxRes] = await Promise.all([
      $fetch('/api/market/overview'),
      $fetch('/api/market/fx-overview'),
    ])
    overviewData.value = overviewRes
    fxOverview.value = fxRes
  } finally {
    isLoading.value = false
  }
}

function manualRefresh() {
  fetchData()
}

function formatFxRate(rate: number | undefined): string {
  if (rate === undefined) return '--'
  return rate.toFixed(4)
}

function formatPercent(value: number | undefined): string {
  if (value === undefined) return '--'
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

function getChangeColor(change: number | undefined): string {
  if (change === undefined) return 'text-disabled'
  if (isCN.value) {
    return change >= 0 ? 'text-success' : 'text-accent'
  }
  return change >= 0 ? 'text-accent' : 'text-success'
}

onMounted(() => {
  fetchData()
})
</script>

<script lang="ts">
// Market Card Component
export const MarketCard = defineComponent({
  props: {
    title: { type: String, required: true },
    emoji: { type: String, required: true },
    summary: { type: Object, default: () => ({}) },
    indices: { type: Array, default: () => [] },
    marketType: { type: String, required: true },
    isCN: { type: Boolean, default: false },
  },
  setup(props) {
    const { formatPercent } = useMoneyDisplay()

    function getChangeColor(change: number | undefined): string {
      if (change === undefined) return 'text-disabled'
      if (props.isCN) {
        return change >= 0 ? 'text-success' : 'text-accent'
      }
      return change >= 0 ? 'text-accent' : 'text-success'
    }

    return () => h('article', { class: 'card' }, [
      // Header
      h('div', { class: 'flex items-center justify-between mb-6' }, [
        h('div', { class: 'flex items-center gap-3' }, [
          h('span', { class: 'text-2xl' }, props.emoji),
          h('h2', { class: 'type-heading' }, props.title),
        ]),
        h(NuxtLink, {
          to: `/market-detail/${props.marketType}`,
          class: 'btn-secondary',
        }, () => 'VIEW →'),
      ]),

      // Stats Grid
      h('div', { class: 'grid grid-cols-2 md:grid-cols-4 gap-4 mb-6' }, [
        h('div', null, [
          h('div', { class: 'label mb-1' }, 'STOCKS'),
          h('div', { class: 'numeric font-mono type-subheading' }, props.summary?.stock_count || 0),
        ]),
        h('div', null, [
          h('div', { class: 'label mb-1' }, 'UP'),
          h('div', { class: `numeric font-mono type-subheading ${props.isCN ? 'text-success' : 'text-accent'}` },
            props.summary?.up_count || 0),
        ]),
        h('div', null, [
          h('div', { class: 'label mb-1' }, 'DOWN'),
          h('div', { class: `numeric font-mono type-subheading ${props.isCN ? 'text-accent' : 'text-success'}` },
            props.summary?.down_count || 0),
        ]),
        h('div', null, [
          h('div', { class: 'label mb-1' }, 'FLAT'),
          h('div', { class: 'numeric font-mono type-subheading' }, props.summary?.flat_count || 0),
        ]),
      ]),

      // Indices
      h('div', { class: 'grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 mb-6' },
        props.indices.map((index: any) =>
          h('div', {
            key: index.symbol,
            class: 'flex items-center justify-between py-2 px-3 border border-border rounded',
          }, [
            h('span', { class: 'label' }, index.shortLabel),
            h('span', { class: 'numeric font-mono text-body-sm' }, index.value),
            h('span', { class: `numeric font-mono text-caption ${getChangeColor(index.changePct)}` },
              formatPercent(index.changePct)),
          ])
        )
      ),

      // Leader / Laggard
      h('div', { class: 'grid grid-cols-2 gap-4 pt-4 border-t border-border' }, [
        // Leader
        h('div', { class: 'flex items-center justify-between' }, [
          h('div', { class: 'flex items-center gap-2' }, [
            h('span', { class: `label ${props.isCN ? 'text-success' : 'text-accent'}` }, 'LEADER'),
            props.summary?.leader?.ticker
              ? h(NuxtLink, {
                  to: `/market-detail/${props.marketType}/${props.summary.leader.ticker}`,
                  class: 'font-mono text-body-sm text-primary hover:text-display',
                }, () => props.summary?.leader?.ticker)
              : h('span', { class: 'font-mono text-body-sm text-disabled' }, '--'),
          ]),
          h('span', { class: `numeric font-mono text-caption ${props.isCN ? 'text-success' : 'text-accent'}` },
            props.summary?.leader ? formatPercent(props.summary.leader.change_pct) : '--'),
        ]),
        // Laggard
        h('div', { class: 'flex items-center justify-between' }, [
          h('div', { class: 'flex items-center gap-2' }, [
            h('span', { class: `label ${props.isCN ? 'text-accent' : 'text-success'}` }, 'LAGGARD'),
            props.summary?.laggard?.ticker
              ? h(NuxtLink, {
                  to: `/market-detail/${props.marketType}/${props.summary.laggard.ticker}`,
                  class: 'font-mono text-body-sm text-primary hover:text-display',
                }, () => props.summary?.laggard?.ticker)
              : h('span', { class: 'font-mono text-body-sm text-disabled' }, '--'),
          ]),
          h('span', { class: `numeric font-mono text-caption ${props.isCN ? 'text-accent' : 'text-success'}` },
            props.summary?.laggard ? formatPercent(props.summary.laggard.change_pct) : '--'),
        ]),
      ]),
    ])
  },
})
</script>
