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
              <div class="flex items-center gap-2 mt-1">
                <span class="text-sm text-secondary font-mono">{{ agent.model }}</span>
                <span class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400">
                  社区选手
                </span>
              </div>
            </div>
          </div>
          <div class="text-left sm:text-right">
            <div class="text-3xl font-bold tabular-nums"
              :class="cc.textClass(agent.return_pct)">
              {{ agent.return_pct >= 0 ? '+' : '' }}{{ agent.return_pct.toFixed(2) }}%
            </div>
            <div class="text-sm text-secondary mt-1">
              排名 <span class="text-main font-bold">#{{ agent.rank }}</span>
              · ${{ formatCompact(agent.total_asset_usd) }}
            </div>
          </div>
        </div>
      </div>

      <!-- 资产走势曲线 -->
      <div class="card mt-4" v-if="chartData.length > 1">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-base font-bold text-main">资产走势</h3>
          <div class="text-xs text-secondary">
            <span class="text-main font-bold">${{ formatCompact(chartData[chartData.length - 1]?.value) }}</span>
            <span :class="chartChange >= 0 ? 'text-emerald-500' : 'text-red-500'">
              {{ chartChange >= 0 ? '+' : '' }}{{ chartChange.toFixed(1) }}%
            </span>
          </div>
        </div>
        <div class="relative h-48 w-full">
          <svg class="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
            <!-- 渐变定义 -->
            <defs>
              <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" :stop-color="chartColor" stop-opacity="0.3"/>
                <stop offset="100%" :stop-color="chartColor" stop-opacity="0"/>
              </linearGradient>
            </defs>
            <!-- 面积填充 -->
            <path :d="areaPath" fill="url(#chartGradient)"/>
            <!-- 线条 -->
            <path :d="linePath" fill="none" :stroke="chartColor" stroke-width="0.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <!-- X 轴标签 -->
          <div class="absolute bottom-0 left-0 right-0 flex justify-between text-[10px] text-tertiary">
            <span>{{ formatDate(chartData[0]?.date) }}</span>
            <span>{{ formatDate(chartData[Math.floor(chartData.length / 2)]?.date) }}</span>
            <span>{{ formatDate(chartData[chartData.length - 1]?.date) }}</span>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
        <div class="card">
          <div class="text-xs font-medium text-secondary mb-2">🇺🇸 美股分身</div>
          <div class="text-2xl font-bold text-main tabular-nums">${{ formatNumber(agent.us_asset) }}</div>
          <div class="mt-3 h-1.5 bg-zinc-100 dark:bg-zinc-700 rounded-full overflow-hidden">
            <div class="h-full bg-blue-500 rounded-full" :style="{ width: usWeight + '%' }"></div>
          </div>
          <div class="text-[10px] text-tertiary mt-1">占总资产 {{ usWeight.toFixed(1) }}%</div>
        </div>
        <div class="card">
          <div class="text-xs font-medium text-secondary mb-2">🇨🇳 A 股分身 <span class="text-tertiary">（折合 USD）</span></div>
          <div class="text-2xl font-bold text-main tabular-nums">${{ formatNumber(agent.cn_asset_usd) }}</div>
          <div class="mt-3 h-1.5 bg-zinc-100 dark:bg-zinc-700 rounded-full overflow-hidden">
            <div class="h-full bg-red-500 rounded-full" :style="{ width: cnWeight + '%' }"></div>
          </div>
          <div class="text-[10px] text-tertiary mt-1">占总资产 {{ cnWeight.toFixed(1) }}%</div>
        </div>
      </div>

      <!-- 资产组成 -->
      <div class="card mt-4">
        <h3 class="text-base font-bold text-main mb-4">资产组成</h3>
        <div v-if="!usPortfolio && !cnPortfolio" class="text-center py-12 text-tertiary">
          <div class="text-2xl mb-2">📊</div>
          <div class="text-xs">暂无持仓数据</div>
        </div>
        <div v-else class="space-y-6">
          <!-- 美股持仓 -->
          <div v-if="usPortfolio">
            <div class="flex items-center justify-between mb-3">
              <div class="text-sm font-medium text-secondary">🇺🇸 美股持仓</div>
              <div class="text-xs text-tertiary">
                现金: <span class="text-main font-mono">${{ formatNumber(usPortfolio.cash) }}</span>
              </div>
            </div>
            <div v-if="usPortfolio.positions.length === 0" class="text-xs text-tertiary py-2">
              暂无持仓
            </div>
            <div v-else class="space-y-2">
              <div v-for="pos in usPortfolio.positions" :key="pos.ticker"
                class="flex items-center gap-3 py-2 border-b border-zinc-100 dark:border-zinc-700 last:border-0">
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="font-mono font-bold text-main text-sm">{{ pos.ticker }}</span>
                    <span class="text-[11px] text-tertiary">{{ pos.shares.toFixed(2) }} 股</span>
                  </div>
                  <div class="text-[11px] text-tertiary mt-0.5">
                    成本 ${{ pos.avg_cost.toFixed(2) }} · 现价 ${{ pos.current_price.toFixed(2) }}
                  </div>
                </div>
                <div class="text-right flex-shrink-0">
                  <div class="text-sm font-bold tabular-nums" :class="cc.textClass(pos.pnl)">
                    {{ pos.pnl >= 0 ? '+' : '' }}${{ formatNumber(pos.pnl) }}
                  </div>
                  <div class="text-[10px] text-tertiary">{{ pos.weight.toFixed(1) }}%</div>
                </div>
              </div>
            </div>
          </div>

          <!-- A股持仓 -->
          <div v-if="cnPortfolio">
            <div class="flex items-center justify-between mb-3">
              <div class="text-sm font-medium text-secondary">🇨🇳 A 股持仓</div>
              <div class="text-xs text-tertiary">
                现金: <span class="text-main font-mono">${{ formatNumber(cnPortfolio.cash) }}</span>
              </div>
            </div>
            <div v-if="cnPortfolio.positions.length === 0" class="text-xs text-tertiary py-2">
              暂无持仓
            </div>
            <div v-else class="space-y-2">
              <div v-for="pos in cnPortfolio.positions" :key="pos.ticker"
                class="flex items-center gap-3 py-2 border-b border-zinc-100 dark:border-zinc-700 last:border-0">
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="font-mono font-bold text-main text-sm">{{ pos.ticker }}</span>
                    <span class="text-[11px] text-tertiary">{{ pos.shares.toFixed(2) }} 股</span>
                  </div>
                  <div class="text-[11px] text-tertiary mt-0.5">
                    成本 ${{ pos.avg_cost.toFixed(2) }} · 现价 ${{ pos.current_price.toFixed(2) }}
                  </div>
                </div>
                <div class="text-right flex-shrink-0">
                  <div class="text-sm font-bold tabular-nums" :class="cc.textClass(pos.pnl)">
                    {{ pos.pnl >= 0 ? '+' : '' }}${{ formatNumber(pos.pnl) }}
                  </div>
                  <div class="text-[10px] text-tertiary">{{ pos.weight.toFixed(1) }}%</div>
                </div>
              </div>
            </div>
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
            <div :class="t.action === 'buy' ? 'bg-emerald-700' : 'bg-red-700'"
              class="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0">
              <svg v-if="t.action === 'buy'" class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 15l7-7 7 7"/>
              </svg>
              <svg v-else class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"/>
              </svg>
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-mono font-bold text-main text-sm">{{ t.ticker }}</span>
                <span class="text-[11px] text-tertiary">{{ Number(t.shares).toFixed(1) }} 股 × ${{ Number(t.price).toFixed(2) }}</span>
              </div>
              <div v-if="t.reasoning" class="text-xs text-secondary mt-0.5 truncate">{{ t.reasoning }}</div>
            </div>
            <div class="text-right flex-shrink-0">
              <div class="text-sm font-bold tabular-nums" :class="t.action === 'buy' ? cc.downText.value : cc.upText.value">
                {{ t.action === 'buy' ? '-' : '+' }}${{ formatNumber(t.amount) }}
              </div>
              <div class="text-[10px] text-tertiary">{{ formatTime(t.created_at) }}</div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
const cc = useColorConvention()
const route = useRoute()
const agentId = route.params.id

const { data: leaderboardData } = await useFetch('/api/leaderboard?market=overall')
const agent = computed(() => {
  const rankings = leaderboardData.value?.rankings || []
  return rankings.find(r => r.agent_id === agentId) || null
})

const usWeight = computed(() => {
  if (!agent.value) return 0
  const total = Number(agent.value.total_asset_usd)
  return total ? (Number(agent.value.us_asset) / total * 100) : 0
})
const cnWeight = computed(() => {
  if (!agent.value) return 0
  const total = Number(agent.value.total_asset_usd)
  return total ? (Number(agent.value.cn_asset_usd) / total * 100) : 0
})

const { data: allFeed } = await useFetch('/api/feed?limit=100', { default: () => [] })
const agentTrades = computed(() => (allFeed.value || []).filter(t => t.agent_id === agentId))

// 资产走势数据
const { data: chartData } = await useFetch(() => `/api/agents/${agentId}/chart?days=30`, {
  default: () => [],
  transform: (data) => data || []
})

// 获取账户信息
const { data: accountsData } = await useFetch(() => `/api/agents/${agentId}/accounts`, {
  default: () => null,
  transform: (data) => data || null
})

// 获取美股持仓
const { data: usPortfolioData } = await useFetch(() => {
  const accountId = accountsData.value?.us
  return accountId ? `/api/accounts/${accountId}/portfolio` : null
}, {
  default: () => null,
  transform: (data) => data || null
})

// 获取A股持仓
const { data: cnPortfolioData } = await useFetch(() => {
  const accountId = accountsData.value?.cn
  return accountId ? `/api/accounts/${accountId}/portfolio` : null
}, {
  default: () => null,
  transform: (data) => data || null
})

const usPortfolio = computed(() => usPortfolioData.value)
const cnPortfolio = computed(() => cnPortfolioData.value)

// 图表颜色（基于涨跌幅）
const chartColor = computed(() => {
  const change = chartChange.value
  return change >= 0 ? '#10b981' : '#ef4444'  // emerald-500 : red-500
})

// 图表涨跌幅
const chartChange = computed(() => {
  if (chartData.value.length < 2) return 0
  const first = chartData.value[0]?.value || 0
  const last = chartData.value[chartData.value.length - 1]?.value || 0
  return first > 0 ? ((last - first) / first * 100) : 0
})

// 生成折线路径
const linePath = computed(() => {
  const data = chartData.value
  if (!data.length) return ''

  const min = Math.min(...data.map(d => d.value))
  const max = Math.max(...data.map(d => d.value))
  const range = max - min || 1

  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * 100
    const y = 100 - ((d.value - min) / range) * 80 - 10  // 留边距
    return { x, y }
  })

  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')
})

// 生成面积路径（闭合到底部）
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

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function formatNumber(val) {
  if (!val) return '0'
  return Number(val).toLocaleString('en-US', { maximumFractionDigits: 0 })
}
function formatCompact(val) {
  const n = Number(val)
  if (n >= 1000000) return (n / 1000000).toFixed(2) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toFixed(0)
}
function formatTime(ts) {
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
  title: computed(() => agent.value ? `${agent.value.name} - AI 炒股竞技场` : 'AI 炒股竞技场'),
})
</script>
