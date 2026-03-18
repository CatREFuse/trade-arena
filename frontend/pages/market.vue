<template>
  <div class="max-w-5xl mx-auto px-4 py-6">
    <h1 class="text-2xl font-bold mb-6">📈 市场总览</h1>

    <!-- 大盘指数 -->
    <div class="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
      <div v-for="idx in indices" :key="idx.name"
        class="bg-arena-card rounded-xl border border-arena-border p-4">
        <div class="text-xs text-gray-500 mb-1">{{ idx.flag }} {{ idx.name }}</div>
        <div class="text-lg font-bold text-white">{{ idx.value }}</div>
        <div :class="idx.change >= 0 ? 'text-arena-green' : 'text-arena-red'" class="text-sm">
          {{ idx.change >= 0 ? '+' : '' }}{{ idx.change }}%
        </div>
      </div>
    </div>

    <!-- 今日交易统计 -->
    <div class="bg-arena-card rounded-xl border border-arena-border p-5 mb-6">
      <h2 class="text-lg font-bold mb-4">📊 交易统计</h2>
      <div class="grid grid-cols-3 gap-4 text-center">
        <div>
          <div class="text-2xl font-bold text-white">{{ feedItems.length }}</div>
          <div class="text-xs text-gray-500">总交易数</div>
        </div>
        <div>
          <div class="text-2xl font-bold text-arena-green">{{ buyCount }}</div>
          <div class="text-xs text-gray-500">买入</div>
        </div>
        <div>
          <div class="text-2xl font-bold text-arena-red">{{ sellCount }}</div>
          <div class="text-xs text-gray-500">卖出</div>
        </div>
      </div>
    </div>

    <!-- 热门股票（从 feed 统计） -->
    <div class="bg-arena-card rounded-xl border border-arena-border p-5">
      <h2 class="text-lg font-bold mb-4">🔥 热门交易股票</h2>
      <div v-if="!hotStocks.length" class="text-center py-6 text-gray-500">暂无数据</div>
      <div v-else class="space-y-2">
        <div v-for="stock in hotStocks" :key="stock.ticker"
          class="flex items-center justify-between p-3 rounded-lg bg-arena-bg/50">
          <div class="font-mono text-white font-bold">{{ stock.ticker }}</div>
          <div class="text-sm text-gray-400">{{ stock.count }} 笔交易</div>
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
  { flag: '🇨🇳', name: '上证指数', value: '3,287', change: -0.15 },
  { flag: '🇨🇳', name: '深证成指', value: '10,450', change: -0.32 },
  { flag: '🇨🇳', name: '创业板指', value: '2,105', change: 0.08 },
]

const { data: feedItems } = await useFetch('/api/feed?limit=100', { default: () => [] })

const buyCount = computed(() => (feedItems.value || []).filter(f => f.action === 'buy').length)
const sellCount = computed(() => (feedItems.value || []).filter(f => f.action === 'sell').length)

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
</script>
