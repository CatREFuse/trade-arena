export interface AdminUserItem {
  id: string
  name: string
  email: string
  avatar: string
  model: string
  style: string
  created_at: string
  account_count: number
  trade_count: number
  asset_cny?: number
  asset_usd?: number
}

export interface AdminLogItem {
  id: number
  created_at: string
  action: 'buy' | 'sell' | string
  ticker: string
  shares: number
  price: number
  amount: number
  fee: number
  reasoning: string
  account_id: string
  market: string
  agent_id: string
  agent_name: string
  agent_avatar: string
}

export interface AdminProbeItem {
  name: string
  ok: boolean
  latency_ms: number
  detail: string
}

export interface AdminProviderCircuitItem {
  data_type: string
  market: string
  provider: string
  failures: number
  circuit_open: boolean
  cooldown_remaining_seconds: number
}

export interface AdminDataSourceStatus {
  db: { ok: boolean, detail: string }
  redis: { ok: boolean, detail: string }
  probes: AdminProbeItem[]
  provider_chains: Record<string, string[]>
  provider_circuits: AdminProviderCircuitItem[]
  cache: Record<string, { present: boolean, updated_at: string }>
}

export interface AdminMarketSnapshot {
  updated_at: string
  indices: Array<{
    symbol: string
    name: string
    price: number
    change_pct: number
    market: string
  }>
  market_summary: Array<{
    market: string
    name: string
    stock_count: number
    up_count: number
    down_count: number
    flat_count: number
    avg_change_pct: number
  }>
  boards: Record<string, Array<{
    ticker: string
    name: string
    market: string
    price: number
    change_pct: number
    volume: number
    market_status: string
  }>>
}

export interface AdminTradeStats {
  totals: {
    trade_count: number
    trade_amount: number
    buy_count: number
    sell_count: number
    recent_24h_count: number
  }
  by_market: Record<string, { count: number, amount: number }>
  daily: Array<{
    date: string
    count: number
    amount: number
    buy_count: number
    sell_count: number
  }>
  top_tickers: Array<{
    ticker: string
    count: number
    amount: number
  }>
}

export interface AdminDashboardResponse {
  generated_at: string
  users: {
    total: number
    items: AdminUserItem[]
  }
  logs: {
    items: AdminLogItem[]
  }
  data_sources: AdminDataSourceStatus
  market: AdminMarketSnapshot
  trade_stats: AdminTradeStats
}

function createDefaultDashboard(): AdminDashboardResponse {
  return {
    generated_at: '',
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
  }
}

export function useAdminDashboard() {
  const {
    data,
    pending,
    error,
    refresh,
  } = useFetch<AdminDashboardResponse>('/api/admin/dashboard', {
    default: createDefaultDashboard,
  })

  const generatedAtLabel = computed(() => {
    if (!data.value?.generated_at)
      return '未知'

    const date = new Date(data.value.generated_at)
    if (Number.isNaN(date.getTime()))
      return '未知'

    return date.toLocaleString('zh-CN', { hour12: false })
  })

  return {
    data,
    pending,
    error,
    refresh,
    generatedAtLabel,
  }
}
