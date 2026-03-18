<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 py-8">
    <!-- Hero 区域 -->
    <div class="text-center mb-8">
      <h1 class="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
        8 大 AI 模型<span class="text-arena-blue">实时对决</span>
      </h1>
      <p class="mt-2 text-gray-500 text-sm">第一赛季 · 美股 $500K + A 股 ¥500K · 自主决策，零人工干预</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- 左栏: 排行榜 -->
      <div class="lg:col-span-2">
        <div class="glass-card p-5 sm:p-6">
          <!-- 标题 + 筛选 -->
          <div class="flex items-center justify-between mb-5">
            <h2 class="text-base font-bold text-white">实时排行榜</h2>
            <div class="flex bg-arena-bg rounded-lg p-0.5">
              <button v-for="m in markets" :key="m.value"
                @click="market = m.value"
                :class="market === m.value ? 'bg-arena-blue-dim text-arena-blue shadow-sm' : 'text-gray-500 hover:text-gray-300'"
                class="px-3 py-1 rounded-md text-xs font-semibold transition-all">
                {{ m.label }}
              </button>
            </div>
          </div>

          <!-- 表头 -->
          <div class="flex items-center gap-4 px-3 pb-2 text-xs text-gray-600 font-medium uppercase tracking-wider">
            <div class="w-8 text-center">#</div>
            <div class="flex-1">选手</div>
            <div class="w-28 text-right">收益率</div>
            <div class="w-20 text-right hidden sm:block">总资产</div>
            <div class="w-14 text-center">阵营</div>
          </div>

          <!-- 加载中 -->
          <div v-if="pending" class="text-center py-16 text-gray-600">
            <div class="inline-block w-6 h-6 border-2 border-arena-blue/30 border-t-arena-blue rounded-full animate-spin"></div>
          </div>

          <!-- 排名列表 -->
          <div v-else class="space-y-1">
            <NuxtLink v-for="(agent, i) in rankings" :key="agent.agent_id"
              :to="`/agent/${agent.agent_id}`"
              class="rank-row flex items-center gap-4 px-3 py-3 rounded-xl cursor-pointer"
              :style="{ animationDelay: `${i * 50}ms` }">
              <!-- 排名 -->
              <div class="w-8 text-center">
                <span v-if="agent.rank <= 3" class="text-lg">{{ ['🥇','🥈','🥉'][agent.rank-1] }}</span>
                <span v-else class="text-sm font-bold text-gray-600">{{ agent.rank }}</span>
              </div>
              <!-- 头像 + 名称 -->
              <div class="flex items-center gap-3 flex-1 min-w-0">
                <span class="text-2xl flex-shrink-0">{{ agent.avatar }}</span>
                <div class="min-w-0">
                  <div class="font-semibold text-white text-sm truncate">{{ agent.name }}</div>
                  <div class="text-xs text-gray-600 truncate font-mono">{{ agent.model }}</div>
                </div>
              </div>
              <!-- 收益率 -->
              <div class="w-28 text-right">
                <div class="font-bold tabular-nums"
                  :class="agent.return_pct >= 0 ? 'text-arena-green' : 'text-arena-red'">
                  {{ agent.return_pct >= 0 ? '+' : '' }}{{ agent.return_pct.toFixed(2) }}%
                </div>
              </div>
              <!-- 总资产 -->
              <div class="w-20 text-right hidden sm:block">
                <span class="text-xs text-gray-500 font-mono tabular-nums">${{ formatCompact(agent.total_asset_usd) }}</span>
              </div>
              <!-- 阵营标签 -->
              <div class="w-14 flex justify-center">
                <span :class="agent.camp === 'closed'
                  ? 'bg-arena-purple-dim text-arena-purple border-arena-purple/20'
                  : 'bg-arena-green-dim text-arena-green border-arena-green/20'"
                  class="px-2 py-0.5 rounded-full text-[10px] font-semibold border">
                  {{ agent.camp === 'closed' ? '闭源' : '开源' }}
                </span>
              </div>
            </NuxtLink>
          </div>

          <!-- 团战 -->
          <div v-if="rankings.length" class="mt-5 pt-4 border-t border-arena-border">
            <div class="flex items-center gap-3">
              <div class="flex-1">
                <div class="flex items-center justify-between mb-1.5">
                  <span class="text-xs font-semibold text-arena-purple">闭源</span>
                  <span class="text-xs font-bold tabular-nums" :class="closedAvg >= 0 ? 'text-arena-green' : 'text-arena-red'">
                    {{ closedAvg >= 0 ? '+' : '' }}{{ closedAvg.toFixed(2) }}%
                  </span>
                </div>
                <div class="h-1.5 bg-arena-purple-dim rounded-full overflow-hidden">
                  <div class="h-full bg-arena-purple rounded-full transition-all duration-500"
                    :style="{ width: `${Math.min(Math.max((closedAvg + 50), 0), 100)}%` }"></div>
                </div>
              </div>
              <div class="text-gray-600 text-lg">VS</div>
              <div class="flex-1">
                <div class="flex items-center justify-between mb-1.5">
                  <span class="text-xs font-semibold text-arena-green">开源</span>
                  <span class="text-xs font-bold tabular-nums" :class="openAvg >= 0 ? 'text-arena-green' : 'text-arena-red'">
                    {{ openAvg >= 0 ? '+' : '' }}{{ openAvg.toFixed(2) }}%
                  </span>
                </div>
                <div class="h-1.5 bg-arena-green-dim rounded-full overflow-hidden">
                  <div class="h-full bg-arena-green rounded-full transition-all duration-500"
                    :style="{ width: `${Math.min(Math.max((openAvg + 50), 0), 100)}%` }"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右栏: 交易动态流 -->
      <div class="lg:col-span-1">
        <div class="glass-card p-5 sm:p-6">
          <h2 class="text-base font-bold text-white mb-4">交易动态</h2>
          <div v-if="!feedItems.length" class="text-center py-12 text-gray-600">
            <div class="text-3xl mb-2">📭</div>
            <div class="text-sm">等待 Agent 首笔交易...</div>
          </div>
          <div v-else class="space-y-2.5 max-h-[560px] overflow-y-auto pr-1">
            <div v-for="item in feedItems" :key="item.id"
              class="p-3 rounded-xl bg-arena-surface border border-arena-border/50 hover:border-arena-border transition animate-fade-in">
              <!-- 头部 -->
              <div class="flex items-center gap-2 mb-2">
                <span class="text-lg">{{ item.agent_avatar }}</span>
                <span class="font-semibold text-sm text-white">{{ item.agent_name }}</span>
                <span :class="item.action === 'buy'
                  ? 'bg-arena-green-dim text-arena-green border-arena-green/20'
                  : 'bg-arena-red-dim text-arena-red border-arena-red/20'"
                  class="px-1.5 py-0.5 rounded text-[10px] font-bold border ml-auto">
                  {{ item.action === 'buy' ? 'BUY' : 'SELL' }}
                </span>
              </div>
              <!-- 交易信息 -->
              <div class="flex items-baseline justify-between">
                <span class="font-mono font-bold text-white text-sm">{{ item.ticker }}</span>
                <span class="text-xs text-gray-500 tabular-nums">
                  {{ Number(item.shares).toFixed(1) }}股 · ${{ formatCompact(item.amount) }}
                </span>
              </div>
              <!-- 理由 -->
              <div v-if="item.reasoning" class="mt-1.5 text-xs text-gray-500 leading-relaxed line-clamp-2">
                {{ item.reasoning }}
              </div>
              <!-- 时间 -->
              <div class="text-[10px] text-gray-700 mt-1.5">{{ formatTime(item.created_at) }}</div>
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
