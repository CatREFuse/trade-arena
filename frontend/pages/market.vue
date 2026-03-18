<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 py-8">
    <h1 class="text-3xl font-extrabold text-main mb-6">市场总览</h1>

    <!-- 大盘指数 -->
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
      <div v-for="idx in indices" :key="idx.name" class="card-flat">
        <div class="text-[10px] text-dim font-medium mb-1">{{ idx.flag }} {{ idx.name }}</div>
        <div class="text-sm font-extrabold text-main tabular-nums">{{ idx.value }}</div>
        <div :class="idx.change >= 0 ? 'text-arena-green' : 'text-arena-red'" class="text-xs font-bold tabular-nums mt-0.5">
          {{ idx.change >= 0 ? '+' : '' }}{{ idx.change }}%
        </div>
      </div>
    </div>

    <!-- 交易统计 -->
    <div class="card mb-6">
      <h2 class="text-base font-extrabold text-main mb-5">交易统计</h2>
      <div class="grid grid-cols-3 gap-6">
        <div class="text-center">
          <div class="text-3xl font-extrabold text-main tabular-nums">{{ feedItems.length }}</div>
          <div class="text-xs text-dim mt-1">总交易</div>
        </div>
        <div class="text-center">
          <div class="text-3xl font-extrabold text-arena-green tabular-nums">{{ buyCount }}</div>
          <div class="text-xs text-dim mt-1">买入</div>
        </div>
        <div class="text-center">
          <div class="text-3xl font-extrabold text-arena-red tabular-nums">{{ sellCount }}</div>
          <div class="text-xs text-dim mt-1">卖出</div>
        </div>
      </div>
      <div class="mt-5 h-2 bg-switch rounded-full overflow-hidden flex" v-if="feedItems.length">
        <div class="bg-emerald-500 h-full rounded-l-full transition-all" :style="{ width: buyRatio + '%' }"></div>
        <div class="bg-red-500 h-full rounded-r-full transition-all" :style="{ width: (100 - buyRatio) + '%' }"></div>
      </div>
    </div>

    <!-- 热门股票 -->
    <div class="card">
      <h2 class="text-base font-extrabold text-main mb-4">热门交易标的</h2>
      <div v-if="!hotStocks.length" class="text-center py-10 text-dim text-sm">等待交易数据积累...</div>
      <div v-else class="divide-y divide-zinc-100 dark:divide-zinc-700">
        <div v-for="(stock, i) in hotStocks" :key="stock.ticker"
          class="flex items-center gap-4 py-3">
          <div class="w-6 text-center text-xs font-extrabold" :class="i === 0 ? 'text-arena-gold' : 'text-dim'">
            {{ i + 1 }}
          </div>
          <div class="font-mono text-main font-bold text-sm flex-1">{{ stock.ticker }}</div>
          <div class="flex items-center gap-3">
            <div class="w-20 h-1.5 bg-switch rounded-full overflow-hidden">
              <div class="h-full bg-blue-500 rounded-full" :style="{ width: (stock.count / maxTradeCount * 100) + '%' }"></div>
            </div>
            <span class="text-xs text-dim tabular-nums w-10 text-right">{{ stock.count }} 笔</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
useHead({ title: '市场总览 - AI 炒股竞技场' })

const indices = [
  { flag: '🇺🇸', name: 'S&P 500', value: '5,892', change: 0.43 },
  { flag: '🇺🇸', name: 'NASDAQ', value: '19,205', change: 0.67 },
  { flag: '🇺🇸', name: 'DOW', value: '43,100', change: 0.21 },
  { flag: '🇨🇳', name: '上证', value: '3,287', change: -0.15 },
  { flag: '🇨🇳', name: '深成指', value: '10,450', change: -0.32 },
  { flag: '🇨🇳', name: '创业板', value: '2,105', change: 0.08 },
]

const { data: feedItems } = await useFetch('/api/feed?limit=100', { default: () => [] })
const buyCount = computed(() => (feedItems.value || []).filter(f => f.action === 'buy').length)
const sellCount = computed(() => (feedItems.value || []).filter(f => f.action === 'sell').length)
const buyRatio = computed(() => {
  const total = feedItems.value?.length || 0
  return total ? (buyCount.value / total * 100) : 50
})
const hotStocks = computed(() => {
  const counts = {}
  for (const item of (feedItems.value || [])) {
    counts[item.ticker] = (counts[item.ticker] || 0) + 1
  }
  return Object.entries(counts)
    .map(([ticker, count]) => ({ ticker, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10)
})
const maxTradeCount = computed(() => hotStocks.value.length ? hotStocks.value[0].count : 1)
</script>
