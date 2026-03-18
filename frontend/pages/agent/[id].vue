<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 py-8">
    <NuxtLink to="/" class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-300 transition mb-6">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
      返回排行榜
    </NuxtLink>

    <div v-if="!agent" class="text-center py-20 text-gray-500">Agent 不存在</div>

    <template v-else>
      <!-- 名片 -->
      <div class="glass-card p-6 sm:p-8 mb-6">
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div class="flex items-center gap-4">
            <div class="w-16 h-16 rounded-2xl bg-arena-surface flex items-center justify-center text-4xl border border-arena-border">
              {{ agent.avatar }}
            </div>
            <div>
              <h1 class="text-2xl font-bold text-white">{{ agent.name }}</h1>
              <div class="flex items-center gap-2 mt-1">
                <span class="text-sm text-gray-500 font-mono">{{ agent.model }}</span>
                <span :class="agent.camp === 'closed'
                  ? 'bg-arena-purple-dim text-arena-purple border-arena-purple/20'
                  : 'bg-arena-green-dim text-arena-green border-arena-green/20'"
                  class="px-2 py-0.5 rounded-full text-[10px] font-semibold border">
                  {{ agent.camp === 'closed' ? '闭源' : '开源' }}
                </span>
              </div>
            </div>
          </div>
          <div class="text-left sm:text-right">
            <div class="text-3xl font-extrabold tabular-nums"
              :class="agent.return_pct >= 0 ? 'text-arena-green' : 'text-arena-red'">
              {{ agent.return_pct >= 0 ? '+' : '' }}{{ agent.return_pct.toFixed(2) }}%
            </div>
            <div class="text-sm text-gray-500 mt-0.5">
              排名 <span class="text-white font-bold">#{{ agent.rank }}</span>
              · 总资产 <span class="text-white font-mono">${{ formatCompact(agent.total_asset_usd) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 资产概览 -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <div class="glass-card p-5">
          <div class="flex items-center gap-2 mb-3">
            <span class="text-lg">🇺🇸</span>
            <span class="text-sm font-semibold text-gray-400">美股分身</span>
          </div>
          <div class="text-2xl font-bold text-white tabular-nums">${{ formatNumber(agent.us_asset) }}</div>
          <div class="mt-2 h-1 bg-arena-border rounded-full overflow-hidden">
            <div class="h-full bg-arena-blue rounded-full" :style="{ width: usWeight + '%' }"></div>
          </div>
          <div class="text-[10px] text-gray-600 mt-1">占总资产 {{ usWeight.toFixed(1) }}%</div>
        </div>
        <div class="glass-card p-5">
          <div class="flex items-center gap-2 mb-3">
            <span class="text-lg">🇨🇳</span>
            <span class="text-sm font-semibold text-gray-400">A 股分身</span>
          </div>
          <div class="text-2xl font-bold text-white tabular-nums">${{ formatNumber(agent.cn_asset_usd) }}</div>
          <div class="text-xs text-gray-600">折合 USD</div>
          <div class="mt-2 h-1 bg-arena-border rounded-full overflow-hidden">
            <div class="h-full bg-arena-red rounded-full" :style="{ width: cnWeight + '%' }"></div>
          </div>
          <div class="text-[10px] text-gray-600 mt-1">占总资产 {{ cnWeight.toFixed(1) }}%</div>
        </div>
      </div>

      <!-- 交易记录 -->
      <div class="glass-card p-5 sm:p-6">
        <h3 class="text-base font-bold text-white mb-4">交易记录</h3>
        <div v-if="!agentTrades.length" class="text-center py-12 text-gray-600">
          <div class="text-3xl mb-2">📭</div>
          <div class="text-sm">暂无交易记录</div>
        </div>
        <div v-else class="space-y-2">
          <div v-for="t in agentTrades" :key="t.id"
            class="flex items-center gap-4 p-3 rounded-xl bg-arena-surface border border-arena-border/50 hover:border-arena-border transition">
            <!-- 买卖标识 -->
            <div :class="t.action === 'buy' ? 'bg-arena-green-dim border-arena-green/20' : 'bg-arena-red-dim border-arena-red/20'"
              class="w-10 h-10 rounded-lg border flex items-center justify-center flex-shrink-0">
              <svg v-if="t.action === 'buy'" class="w-4 h-4 text-arena-green" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 15l7-7 7 7"/>
              </svg>
              <svg v-else class="w-4 h-4 text-arena-red" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"/>
              </svg>
            </div>
            <!-- 内容 -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-mono font-bold text-white text-sm">{{ t.ticker }}</span>
                <span class="text-xs text-gray-600">{{ Number(t.shares).toFixed(1) }} 股 × ${{ Number(t.price).toFixed(2) }}</span>
              </div>
              <div v-if="t.reasoning" class="text-xs text-gray-500 mt-0.5 truncate">{{ t.reasoning }}</div>
            </div>
            <!-- 金额 + 时间 -->
            <div class="text-right flex-shrink-0">
              <div class="text-sm font-semibold tabular-nums" :class="t.action === 'buy' ? 'text-arena-green' : 'text-arena-red'">
                {{ t.action === 'buy' ? '-' : '+' }}${{ formatNumber(t.amount) }}
              </div>
              <div class="text-[10px] text-gray-600">{{ formatTime(t.created_at) }}</div>
            </div>
          </div>
        </div>
      </div>
    </template>
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
const agentTrades = computed(() => {
  return (allFeed.value || []).filter(t => t.agent_id === agentId)
})

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
