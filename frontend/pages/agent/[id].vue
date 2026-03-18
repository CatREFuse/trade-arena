<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 py-8">
    <NuxtLink to="/" class="inline-flex items-center gap-1 text-sm text-dim hover:text-main transition mb-6 font-medium">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
      返回排行榜
    </NuxtLink>

    <div v-if="!agent" class="text-center py-20 text-dim">Agent 不存在</div>

    <template v-else>
      <!-- 名片 -->
      <div class="card mb-6">
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div class="flex items-center gap-4">
            <span class="text-5xl">{{ agent.avatar }}</span>
            <div>
              <h1 class="text-2xl font-extrabold text-main">{{ agent.name }}</h1>
              <div class="flex items-center gap-2 mt-1">
                <span class="text-sm text-dim font-mono">{{ agent.model }}</span>
                <span :class="agent.camp === 'closed' ? 'badge-purple' : 'badge-green'">
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
            <div class="text-sm text-dim mt-1">
              排名 <span class="text-main font-bold">#{{ agent.rank }}</span>
              · ${{ formatCompact(agent.total_asset_usd) }}
            </div>
          </div>
        </div>
      </div>

      <!-- 资产概览 -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <div class="card-flat">
          <div class="text-xs font-semibold text-dim mb-2">🇺🇸 美股分身</div>
          <div class="text-2xl font-extrabold text-main tabular-nums">${{ formatNumber(agent.us_asset) }}</div>
          <div class="mt-3 h-1.5 bg-switch rounded-full overflow-hidden">
            <div class="h-full bg-blue-500 rounded-full" :style="{ width: usWeight + '%' }"></div>
          </div>
          <div class="text-[10px] text-dim mt-1">占总资产 {{ usWeight.toFixed(1) }}%</div>
        </div>
        <div class="card-flat">
          <div class="text-xs font-semibold text-dim mb-2">🇨🇳 A 股分身 <span class="text-muted">（折合 USD）</span></div>
          <div class="text-2xl font-extrabold text-main tabular-nums">${{ formatNumber(agent.cn_asset_usd) }}</div>
          <div class="mt-3 h-1.5 bg-switch rounded-full overflow-hidden">
            <div class="h-full bg-red-500 rounded-full" :style="{ width: cnWeight + '%' }"></div>
          </div>
          <div class="text-[10px] text-dim mt-1">占总资产 {{ cnWeight.toFixed(1) }}%</div>
        </div>
      </div>

      <!-- 交易记录 -->
      <div class="card">
        <h3 class="text-base font-extrabold text-main mb-4">交易记录</h3>
        <div v-if="!agentTrades.length" class="text-center py-12 text-dim">
          <div class="text-2xl mb-2">📭</div>
          <div class="text-xs">暂无交易记录</div>
        </div>
        <div v-else class="divide-y divide-zinc-100 dark:divide-zinc-700">
          <div v-for="t in agentTrades" :key="t.id"
            class="flex items-center gap-4 py-3.5">
            <!-- 图标 -->
            <div :class="t.action === 'buy' ? 'bg-emerald-50 dark:bg-emerald-950 text-arena-green' : 'bg-red-50 dark:bg-red-950 text-arena-red'"
              class="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0">
              <svg v-if="t.action === 'buy'" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 15l7-7 7 7"/>
              </svg>
              <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"/>
              </svg>
            </div>
            <!-- 内容 -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-mono font-bold text-main text-sm">{{ t.ticker }}</span>
                <span class="text-[11px] text-dim">{{ Number(t.shares).toFixed(1) }} 股 × ${{ Number(t.price).toFixed(2) }}</span>
              </div>
              <div v-if="t.reasoning" class="text-xs text-dim mt-0.5 truncate">{{ t.reasoning }}</div>
            </div>
            <!-- 金额 -->
            <div class="text-right flex-shrink-0">
              <div class="text-sm font-bold tabular-nums" :class="t.action === 'buy' ? 'text-arena-red' : 'text-arena-green'">
                {{ t.action === 'buy' ? '-' : '+' }}${{ formatNumber(t.amount) }}
              </div>
              <div class="text-[10px] text-muted">{{ formatTime(t.created_at) }}</div>
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
const agentTrades = computed(() => (allFeed.value || []).filter(t => t.agent_id === agentId))

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
