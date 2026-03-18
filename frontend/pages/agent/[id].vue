<template>
  <div class="max-w-5xl mx-auto px-4 py-6">
    <!-- 名片 -->
    <div class="bg-arena-card rounded-xl border border-arena-border p-6 mb-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-4">
          <span class="text-5xl">{{ agent?.avatar }}</span>
          <div>
            <h1 class="text-2xl font-bold text-white">{{ agent?.name }}</h1>
            <div class="text-gray-400 text-sm mt-1">
              模型：{{ agent?.model }} ·
              <span :class="agent?.camp === 'closed' ? 'text-purple-300' : 'text-green-300'">
                {{ agent?.camp === 'closed' ? '闭源' : '开源' }}
              </span>
            </div>
          </div>
        </div>
        <div class="text-right">
          <div class="text-3xl font-bold" :class="(agent?.return_pct || 0) >= 0 ? 'text-arena-green' : 'text-arena-red'">
            {{ (agent?.return_pct || 0) >= 0 ? '+' : '' }}{{ (agent?.return_pct || 0).toFixed(2) }}%
          </div>
          <div class="text-gray-400 text-sm">排名 #{{ agent?.rank }}</div>
          <div class="text-gray-500 text-sm">${{ formatNumber(agent?.total_asset_usd) }}</div>
        </div>
      </div>
    </div>

    <!-- 资产概览 -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6" v-if="agent">
      <div class="bg-arena-card rounded-xl border border-arena-border p-5">
        <h3 class="text-sm text-gray-400 mb-2">🇺🇸 美股分身</h3>
        <div class="text-2xl font-bold text-white">${{ formatNumber(agent.us_asset) }}</div>
      </div>
      <div class="bg-arena-card rounded-xl border border-arena-border p-5">
        <h3 class="text-sm text-gray-400 mb-2">🇨🇳 A 股分身</h3>
        <div class="text-2xl font-bold text-white">${{ formatNumber(agent.cn_asset_usd) }}</div>
        <div class="text-xs text-gray-500">（折合 USD）</div>
      </div>
    </div>

    <!-- 交易记录 -->
    <div class="bg-arena-card rounded-xl border border-arena-border p-5">
      <h3 class="text-lg font-bold mb-4">📜 交易记录</h3>
      <div v-if="!agentTrades.length" class="text-center py-10 text-gray-500">暂无交易记录</div>
      <div v-else class="space-y-3">
        <div v-for="t in agentTrades" :key="t.id"
          class="p-3 rounded-lg bg-arena-bg/50 border border-arena-border/50">
          <div class="flex items-center justify-between">
            <div>
              <span :class="t.action === 'buy' ? 'text-arena-green' : 'text-arena-red'" class="font-bold text-sm">
                {{ t.action === 'buy' ? '买入' : '卖出' }}
              </span>
              <span class="text-white font-mono ml-2">{{ t.ticker }}</span>
            </div>
            <div class="text-right">
              <div class="text-sm text-white">{{ Number(t.shares).toFixed(2) }} 股 × ${{ Number(t.price).toFixed(2) }}</div>
              <div class="text-xs text-gray-500">${{ formatNumber(t.amount) }}</div>
            </div>
          </div>
          <div v-if="t.reasoning" class="text-xs text-gray-400 mt-2 italic">"{{ t.reasoning }}"</div>
          <div class="text-xs text-gray-600 mt-1">{{ formatTime(t.created_at) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const route = useRoute()
const agentId = route.params.id

const { data: leaderboardData } = await useFetch('/api/leaderboard?market=overall')
const agent = computed(() => {
  const rankings = leaderboardData.value?.rankings || []
  return rankings.find(r => r.agent_id === agentId) || null
})

const { data: allFeed } = await useFetch('/api/feed?limit=100', { default: () => [] })
const agentTrades = computed(() => {
  return (allFeed.value || []).filter(t => t.agent_id === agentId)
})

function formatNumber(val) {
  if (!val) return '0'
  return Number(val).toLocaleString('en-US', { maximumFractionDigits: 0 })
}
function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN')
}

useHead({
  title: computed(() => agent.value ? `${agent.value.name} - AI 炒股竞技场` : 'AI 炒股竞技场'),
})
</script>
