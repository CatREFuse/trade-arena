import { computed, shallowRef, toValue, type MaybeRefOrGetter } from 'vue'

export type MarketKey = 'us' | 'cn'
export type SortDirection = 'desc' | 'asc'

export interface MarketBoardItem {
  ticker: string
  name: string
  market: MarketKey
  price: number
  change_pct: number
  volume: number
  market_status: string
}

export interface MarketBoardSnapshot {
  items: MarketBoardItem[]
  updated_at?: string
}

export interface MarketPulsePoint {
  x: number
  y: number
}

export interface MarketPulseShape {
  line: string
  area: string
}

export interface MarketDetailMeta {
  key: MarketKey
  label: string
  shortLabel: string
  title: string
  subtitle: string
  badge: string
  counterpart: MarketKey
}

const MARKET_META: Record<MarketKey, MarketDetailMeta> = {
  us: {
    key: 'us',
    label: '美股市场',
    shortLabel: '美股',
    title: '美国市场',
    subtitle: '围绕大型科技、指数成分和热点主题的收益分布',
    badge: 'US MARKET',
    counterpart: 'cn',
  },
  cn: {
    key: 'cn',
    label: 'A 股市场',
    shortLabel: 'A 股',
    title: 'A 股市场',
    subtitle: '围绕核心宽基、权重股和行业龙头的收益分布',
    badge: 'CN MARKET',
    counterpart: 'us',
  },
}

export async function useMarketDetail(marketKey: MaybeRefOrGetter<MarketKey>) {
  const resolvedMarket = computed<MarketKey>(() => {
    const raw = toValue(marketKey)
    return raw === 'cn' ? 'cn' : 'us'
  })

  const meta = computed(() => MARKET_META[resolvedMarket.value])
  const sortDirection = shallowRef<SortDirection>('desc')

  const { data: boardData, pending, error, refresh } = await useFetch(
    () => `/api/market/board?market=${resolvedMarket.value}`,
    {
      watch: [resolvedMarket],
      default: () => ({ items: [], updated_at: '' }),
      transform: (snapshot: MarketBoardSnapshot = { items: [], updated_at: '' }) => snapshot,
    },
  )

  const items = computed<MarketBoardItem[]>(() => boardData.value?.items || [])
  const updatedAt = computed(() => boardData.value?.updated_at || '')

  const sortedItems = computed(() => {
    const direction = sortDirection.value === 'desc' ? -1 : 1
    return [...items.value].sort((a, b) => {
      if (a.change_pct === b.change_pct) {
        return a.ticker.localeCompare(b.ticker)
      }
      return (a.change_pct - b.change_pct) * direction
    })
  })

  const positiveCount = computed(() => items.value.filter(item => item.change_pct >= 0).length)
  const negativeCount = computed(() => items.value.filter(item => item.change_pct < 0).length)

  const averageReturn = computed(() => {
    if (!items.value.length) return 0
    return items.value.reduce((sum, item) => sum + item.change_pct, 0) / items.value.length
  })

  const bestMover = computed(() => {
    if (!items.value.length) return null
    return [...items.value].sort((a, b) => b.change_pct - a.change_pct)[0]
  })

  const worstMover = computed(() => {
    if (!items.value.length) return null
    return [...items.value].sort((a, b) => a.change_pct - b.change_pct)[0]
  })

  const marketPulse = computed<MarketPulseShape>(() => buildMarketPulse(sortedItems.value))

  function toggleSort() {
    sortDirection.value = sortDirection.value === 'desc' ? 'asc' : 'desc'
  }

  function formatPercent(value: number) {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
  }

  function formatPrice(value: number, market: MarketKey = resolvedMarket.value) {
    const symbol = market === 'us' ? '$' : '¥'
    return `${symbol}${Number(value).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`
  }

  return {
    meta,
    items,
    sortedItems,
    pending,
    error,
    refresh,
    updatedAt,
    sortDirection,
    toggleSort,
    positiveCount,
    negativeCount,
    averageReturn,
    bestMover,
    worstMover,
    marketPulse,
    formatPercent,
    formatPrice,
  }
}

function buildMarketPulse(items: MarketBoardItem[]): MarketPulseShape {
  if (!items.length) {
    return {
      line: 'M0,24 L100,24',
      area: 'M0,24 L100,24 L100,32 L0,32 Z',
    }
  }

  const values = items.map((item, index) => {
    const seed = hashSeed(item.ticker)
    const base = 12 + Math.min(10, Math.abs(item.change_pct) * 1.3)
    const trend = item.change_pct >= 0 ? 1 : -1
    const wave = Math.sin(seed * 0.017 + index * 0.7) * 1.4
    return Math.max(2, Math.min(24, base + wave + trend * (index / Math.max(items.length - 1, 1)) * 4))
  })

  return pointsToPath(values, 100, 24)
}

function hashSeed(value: string) {
  let hash = 0
  for (let i = 0; i < value.length; i++) {
    hash = ((hash << 5) - hash + value.charCodeAt(i)) | 0
  }
  return Math.abs(hash)
}

function pointsToPath(values: number[], width: number, height: number): MarketPulseShape {
  const points = values.length
  const step = width / Math.max(points - 1, 1)
  const linePoints = values.map((y, index) => `${(index * step).toFixed(1)},${(height - y).toFixed(1)}`)
  const line = `M${linePoints.join(' L')}`
  const area = `${line} L${width},${height} L0,${height} Z`
  return { line, area }
}
