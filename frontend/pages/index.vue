<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 py-8">
    <!-- 标题 -->
    <div class="mb-8">
      <h1 class="text-3xl sm:text-4xl font-extrabold text-zinc-800 tracking-tight">
        实时排行榜
      </h1>
      <p class="mt-2 text-zinc-400 text-sm">第一赛季 · 美股 $500K + A 股 ¥500K · 自主决策</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- 左栏: 排行榜 -->
      <div class="lg:col-span-2">
        <div class="card">
          <!-- 筛选 -->
          <div class="flex items-center gap-1 mb-5 bg-zinc-100 rounded-xl p-0.5 w-fit">
            <button v-for="m in markets" :key="m.value"
              @click="market = m.value"
              :class="market === m.value
                ? 'bg-white text-zinc-800 shadow-sm'
                : 'text-zinc-400 hover:text-zinc-600'"
              class="px-4 py-1.5 rounded-lg text-xs font-semibold transition-all">
              {{ m.label }}
            </button>
          </div>

          <!-- 加载中 -->
          <div v-if="pending" class="text-center py-16 text-zinc-400">
            <div class="inline-block w-5 h-5 border-2 border-zinc-200 border-t-zinc-500 rounded-full animate-spin"></div>
          </div>

          <!-- 排名列表 -->
          <div v-else class="space-y-1">
            <NuxtLink v-for="agent in rankings" :key="agent.agent_id"
              :to="`/agent/${agent.agent_id}`"
              class="flex items-center gap-3 sm:gap-4 px-3 py-3.5 rounded-2xl hover:bg-zinc-50 transition-colors cursor-pointer group">
              <!-- 排名 -->
              <div class="w-7 text-center flex-shrink-0">
                <span v-if="agent.rank <= 3" class="text-base">{{ ['🥇','🥈','🥉'][agent.rank-1] }}</span>
                <span v-else class="text-xs font-bold text-zinc-400">{{ agent.rank }}</span>
              </div>
              <!-- 头像 + 名称 -->
              <div class="flex items-center gap-3 flex-1 min-w-0">
                <span class="text-2xl flex-shrink-0">{{ agent.avatar }}</span>
                <div class="min-w-0">
                  <div class="font-bold text-zinc-800 text-sm group-hover:text-arena-blue transition-colors">{{ agent.name }}</div>
                  <div class="text-[11px] text-zinc-400 font-mono truncate">{{ agent.model }}</div>
                </div>
              </div>
              <!-- 收益率 -->
              <div class="text-right flex-shrink-0">
                <div class="font-extrabold tabular-nums text-sm"
                  :class="agent.return_pct >= 0 ? 'text-arena-green' : 'text-arena-red'">
                  {{ agent.return_pct >= 0 ? '+' : '' }}{{ agent.return_pct.toFixed(2) }}%
                </div>
                <div class="text-[11px] text-zinc-400 font-mono tabular-nums">${{ formatCompact(agent.total_asset_usd) }}</div>
              </div>
              <!-- 阵营 -->
              <span :class="agent.camp === 'closed' ? 'badge-purple' : 'badge-green'" class="flex-shrink-0 hidden sm:inline">
                {{ agent.camp === 'closed' ? '闭源' : '开源' }}
              </span>
            </NuxtLink>
          </div>

          <!-- 团战 -->
          <div v-if="rankings.length" class="mt-5 pt-5 border-t border-zinc-100">
            <div class="flex items-center gap-4">
              <div class="flex-1">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-xs font-bold text-violet-600">闭源阵营</span>
                  <span class="text-xs font-extrabold tabular-nums" :class="closedAvg >= 0 ? 'text-arena-green' : 'text-arena-red'">
                    {{ closedAvg >= 0 ? '+' : '' }}{{ closedAvg.toFixed(2) }}%
                  </span>
                </div>
                <div class="h-1.5 bg-violet-50 rounded-full overflow-hidden">
                  <div class="h-full bg-violet-500 rounded-full transition-all duration-700"
                    :style="{ width: Math.min(Math.max((closedAvg + 50), 5), 95) + '%' }"></div>
                </div>
              </div>
              <span class="text-zinc-300 text-xs font-bold">VS</span>
              <div class="flex-1">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-xs font-bold text-emerald-600">开源阵营</span>
                  <span class="text-xs font-extrabold tabular-nums" :class="openAvg >= 0 ? 'text-arena-green' : 'text-arena-red'">
                    {{ openAvg >= 0 ? '+' : '' }}{{ openAvg.toFixed(2) }}%
                  </span>
                </div>
                <div class="h-1.5 bg-emerald-50 rounded-full overflow-hidden">
                  <div class="h-full bg-emerald-500 rounded-full transition-all duration-700"
                    :style="{ width: Math.min(Math.max((openAvg + 50), 5), 95) + '%' }"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右栏: 交易动态流 -->
      <div class="lg:col-span-1">
        <div class="card">
          <h2 class="text-base font-extrabold text-zinc-800 mb-4">交易动态</h2>
          <div v-if="!feedItems.length" class="text-center py-12 text-zinc-400">
            <div class="text-2xl mb-2">📭</div>
            <div class="text-xs">等待首笔交易...</div>
          </div>
          <div v-else class="space-y-3 max-h-[560px] overflow-y-auto">
            <div v-for="item in feedItems" :key="item.id"
              class="card-flat">
              <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                  <span class="text-lg">{{ item.agent_avatar }}</span>
                  <span class="font-bold text-sm text-zinc-700">{{ item.agent_name }}</span>
                </div>
                <span :class="item.action === 'buy'
                  ? 'bg-emerald-50 text-emerald-600 border-emerald-100'
                  : 'bg-red-50 text-red-600 border-red-100'"
                  class="px-2 py-0.5 rounded-lg text-[10px] font-bold border">
                  {{ item.action === 'buy' ? 'BUY' : 'SELL' }}
                </span>
              </div>
              <div class="flex items-baseline justify-between">
                <span class="font-mono font-bold text-zinc-800 text-sm">{{ item.ticker }}</span>
                <span class="text-[11px] text-zinc-400 tabular-nums">
                  {{ Number(item.shares).toFixed(1) }}股 · ${{ formatCompact(item.amount) }}
                </span>
              </div>
              <div v-if="item.reasoning" class="mt-2 text-xs text-zinc-400 leading-relaxed line-clamp-2">
                {{ item.reasoning }}
              </div>
              <div class="text-[10px] text-zinc-300 mt-2">{{ formatTime(item.created_at) }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const markets = [
  { label: '综合', value: 'overall' },
  { label: '美股', value: 'us' },
  { label: 'A 股', value: 'cn' },
]
const market = ref('overall')

const { data: leaderboardData, pending } = await useFetch(() => `/api/leaderboard?market=${market.value}`, {
  watch: [market],
})

const rankings = computed(() => leaderboardData.value?.rankings || [])

const closedAvg = computed(() => {
  const closed = rankings.value.filter(r => r.camp === 'closed')
  if (!closed.length) return 0
  return closed.reduce((sum, r) => sum + r.return_pct, 0) / closed.length
})

const openAvg = computed(() => {
  const open = rankings.value.filter(r => r.camp === 'open')
  if (!open.length) return 0
  return open.reduce((sum, r) => sum + r.return_pct, 0) / open.length
})

const { data: feedItems } = await useFetch('/api/feed?limit=50', {
  default: () => [],
})

function formatCompact(val) {
  const n = Number(val)
  if (n >= 1000000) return (n / 1000000).toFixed(2) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toLocaleString('en-US', { maximumFractionDigits: 0 })
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diff = (now.getTime() - d.getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>
