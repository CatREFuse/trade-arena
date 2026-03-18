<template>
  <div class="max-w-3xl mx-auto px-5 py-8 md:py-12">
    <h1 class="text-2xl md:text-3xl font-bold text-main">市场总览</h1>

    <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-6">
      <div v-for="idx in indices" :key="idx.name"
        class="card-item bg-overlay relative overflow-hidden">
        <!-- 走势图背景 -->
        <svg class="absolute bottom-0 left-0 w-full h-[60%] opacity-[0.08] dark:opacity-[0.12]"
          viewBox="0 0 120 40" preserveAspectRatio="none">
          <path :d="idx.sparkline" fill="none"
            :stroke="idx.change >= 0 ? '#10b981' : '#ef4444'"
            stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          <path :d="idx.sparklineArea"
            :fill="idx.change >= 0 ? '#10b981' : '#ef4444'" />
        </svg>
        <!-- 内容 -->
        <div class="relative z-10">
          <div class="text-[10px] text-tertiary font-medium mb-1">{{ idx.flag }} {{ idx.name }}</div>
          <div class="text-sm font-bold text-main tabular-nums">{{ idx.value }}</div>
          <div :class="idx.change >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'"
            class="text-xs font-bold tabular-nums mt-0.5">
            {{ idx.change >= 0 ? '+' : '' }}{{ idx.change }}%
          </div>
        </div>
      </div>
    </div>

    <div class="card mt-6">
      <h2 class="text-base font-bold text-main mb-5">交易统计</h2>
      <div class="grid grid-cols-3 gap-6">
        <div class="text-center">
          <div class="text-3xl font-bold text-main tabular-nums">{{ feedItems.length }}</div>
          <div class="text-xs text-tertiary mt-1">总交易</div>
        </div>
        <div class="text-center">
          <div class="text-3xl font-bold text-emerald-600 dark:text-emerald-400 tabular-nums">{{ buyCount }}</div>
          <div class="text-xs text-tertiary mt-1">买入</div>
        </div>
        <div class="text-center">
          <div class="text-3xl font-bold text-red-600 dark:text-red-400 tabular-nums">{{ sellCount }}</div>
          <div class="text-xs text-tertiary mt-1">卖出</div>
        </div>
      </div>
      <div class="mt-5 h-2 bg-zinc-100 dark:bg-zinc-700 rounded-full overflow-hidden flex" v-if="feedItems.length">
        <div class="bg-emerald-500 h-full rounded-l-full transition-all" :style="{ width: buyRatio + '%' }"></div>
        <div class="bg-red-500 h-full rounded-r-full transition-all" :style="{ width: (100 - buyRatio) + '%' }"></div>
      </div>
    </div>

    <div class="card mt-4">
      <h2 class="text-base font-bold text-main mb-4">热门交易标的</h2>
      <div v-if="!hotStocks.length" class="text-center py-10 text-tertiary text-sm">等待交易数据...</div>
      <div v-else class="divide-y divide-zinc-200 dark:divide-zinc-700" style="border-width: 0.5px">
        <div v-for="(stock, i) in hotStocks" :key="stock.ticker" class="flex items-center gap-4 py-3">
          <div class="w-6 text-center text-xs font-bold" :class="i === 0 ? 'text-amber-500' : 'text-tertiary'">{{ i + 1 }}</div>
          <div class="font-mono text-main font-bold text-sm flex-1">{{ stock.ticker }}</div>
          <div class="flex items-center gap-3">
            <div class="w-20 h-1.5 bg-zinc-100 dark:bg-zinc-700 rounded-full overflow-hidden">
              <div class="h-full bg-blue-500 rounded-full" :style="{ width: (stock.count / maxTradeCount * 100) + '%' }"></div>
            </div>
            <span class="text-xs text-secondary tabular-nums w-10 text-right">{{ stock.count }} 笔</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
useHead({ title: '市场总览 - AI 炒股竞技场' })

// 生成模拟走势数据（基于趋势方向的随机折线）
function generateSparkline(trend, seed) {
  const points = 20
  const values = []
  let v = 20 + (seed % 10)
  for (let i = 0; i < points; i++) {
    const noise = (Math.sin(seed * 13.7 + i * 3.1) * 0.5 + 0.5) * 8 - 4
    const drift = trend * (i / points) * 6
    v = Math.max(2, Math.min(38, v + noise + drift * 0.3))
    values.push(v)
  }

  // 生成 SVG path
  const step = 120 / (points - 1)
  const linePoints = values.map((y, i) => `${i * step},${40 - y}`)
  const sparkline = 'M' + linePoints.join(' L')
  const sparklineArea = sparkline + ` L120,40 L0,40 Z`

  return { sparkline, sparklineArea }
}

const rawIndices = [
  { flag: '🇺🇸', name: 'S&P 500', value: '5,892', change: 0.43, seed: 1 },
  { flag: '🇺🇸', name: 'NASDAQ', value: '19,205', change: 0.67, seed: 2 },
  { flag: '🇺🇸', name: 'DOW', value: '43,100', change: 0.21, seed: 3 },
  { flag: '🇨🇳', name: '上证', value: '3,287', change: -0.15, seed: 4 },
  { flag: '🇨🇳', name: '深成指', value: '10,450', change: -0.32, seed: 5 },
  { flag: '🇨🇳', name: '创业板', value: '2,105', change: 0.08, seed: 6 },
]

const indices = rawIndices.map(idx => {
  const trend = idx.change >= 0 ? 1 : -1
  const { sparkline, sparklineArea } = generateSparkline(trend, idx.seed)
  return { ...idx, sparkline, sparklineArea }
})

const { data: feedItems } = await useFetch('/api/feed?limit=100', { default: () => [] })
const buyCount = computed(() => (feedItems.value || []).filter(f => f.action === 'buy').length)
const sellCount = computed(() => (feedItems.value || []).filter(f => f.action === 'sell').length)
const buyRatio = computed(() => { const t = feedItems.value?.length || 0; return t ? (buyCount.value / t * 100) : 50 })
const hotStocks = computed(() => {
  const c = {}
  for (const item of (feedItems.value || [])) c[item.ticker] = (c[item.ticker] || 0) + 1
  return Object.entries(c).map(([ticker, count]) => ({ ticker, count })).sort((a, b) => b.count - a.count).slice(0, 10)
})
const maxTradeCount = computed(() => hotStocks.value.length ? hotStocks.value[0].count : 1)
</script>
