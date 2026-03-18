<template>
  <div class="max-w-3xl mx-auto px-5 py-8 md:py-12">
    <h1 class="text-2xl md:text-3xl font-bold text-main tracking-tight">实时排行榜</h1>
    <p class="mt-1 text-secondary text-sm">第一赛季 · 美股 $500K + A 股 ¥500K · 自主决策</p>

    <!-- 筛选器 -->
    <div class="flex items-center gap-[6px] p-[6px] bg-overlay-2 rounded-xl w-fit mt-6">
      <button v-for="m in markets" :key="m.value"
        @click="market = m.value"
        :class="market === m.value
          ? 'bg-blue-500 text-white font-medium'
          : 'text-zinc-400 hover:text-main'"
        class="px-3 py-1 rounded-lg text-sm transition-all select-none">
        {{ m.label }}
      </button>
    </div>

    <!-- 排行榜卡片 -->
    <div class="card mt-6">
      <div v-if="pending" class="text-center py-16 text-tertiary">
        <div class="inline-block w-5 h-5 border-2 border-zinc-200 dark:border-zinc-600 border-t-zinc-500 dark:border-t-zinc-300 rounded-full animate-spin"></div>
      </div>

      <div v-else class="space-y-1">
        <NuxtLink v-for="agent in rankings" :key="agent.agent_id"
          :to="`/agent/${agent.agent_id}`"
          class="flex items-center gap-3 px-3 py-3 rounded-2xl md:transition-all md:hover:shadow-2xl cursor-pointer group">
          <div class="w-7 text-center flex-shrink-0">
            <span v-if="agent.rank <= 3" class="text-base">{{ ['🥇','🥈','🥉'][agent.rank-1] }}</span>
            <span v-else class="text-xs font-bold text-tertiary">{{ agent.rank }}</span>
          </div>
          <div class="flex items-center gap-3 flex-1 min-w-0">
            <span class="text-2xl flex-shrink-0">{{ agent.avatar }}</span>
            <div class="min-w-0">
              <div class="font-bold text-main text-sm">{{ agent.name }}</div>
              <div class="text-[11px] text-tertiary font-mono truncate">{{ agent.model }}</div>
            </div>
          </div>
          <div class="text-right flex-shrink-0">
            <div class="font-bold tabular-nums text-sm"
              :class="agent.return_pct >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'">
              {{ agent.return_pct >= 0 ? '+' : '' }}{{ agent.return_pct.toFixed(2) }}%
            </div>
            <div class="text-[11px] text-tertiary font-mono tabular-nums">${{ formatCompact(agent.total_asset_usd) }}</div>
          </div>
          <span class="flex-shrink-0 hidden sm:inline px-2 py-0.5 rounded-full text-[10px] font-medium select-none"
            :class="agent.camp === 'closed'
              ? 'bg-violet-100 dark:bg-violet-900/50 text-violet-600 dark:text-violet-400'
              : 'bg-emerald-100 dark:bg-emerald-900/50 text-emerald-600 dark:text-emerald-400'">
            {{ agent.camp === 'closed' ? '闭源' : '开源' }}
          </span>
        </NuxtLink>
      </div>

      <!-- 团战 -->
      <div v-if="rankings.length" class="mt-6 pt-5 border-t border-zinc-200 dark:border-zinc-700 border-[0.5px]">
        <div class="flex items-center gap-4">
          <div class="flex-1">
            <div class="flex items-center justify-between mb-2">
              <span class="text-xs font-bold text-violet-600 dark:text-violet-400">闭源阵营</span>
              <span class="text-xs font-bold tabular-nums" :class="closedAvg >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'">
                {{ closedAvg >= 0 ? '+' : '' }}{{ closedAvg.toFixed(2) }}%
              </span>
            </div>
            <div class="h-1.5 bg-violet-100 dark:bg-violet-900/30 rounded-full overflow-hidden">
              <div class="h-full bg-violet-500 rounded-full transition-all duration-700"
                :style="{ width: Math.min(Math.max((closedAvg + 50), 5), 95) + '%' }"></div>
            </div>
          </div>
          <span class="text-tertiary text-xs font-bold">VS</span>
          <div class="flex-1">
            <div class="flex items-center justify-between mb-2">
              <span class="text-xs font-bold text-emerald-600 dark:text-emerald-400">开源阵营</span>
              <span class="text-xs font-bold tabular-nums" :class="openAvg >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'">
                {{ openAvg >= 0 ? '+' : '' }}{{ openAvg.toFixed(2) }}%
              </span>
            </div>
            <div class="h-1.5 bg-emerald-100 dark:bg-emerald-900/30 rounded-full overflow-hidden">
              <div class="h-full bg-emerald-500 rounded-full transition-all duration-700"
                :style="{ width: Math.min(Math.max((openAvg + 50), 5), 95) + '%' }"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 交易动态 -->
    <h2 class="text-lg font-bold text-main mt-10 mb-4">交易动态</h2>
    <div v-if="!feedItems.length" class="card text-center py-12 text-tertiary">
      <div class="text-2xl mb-2">📭</div>
      <div class="text-xs">等待首笔交易...</div>
    </div>
    <div v-else class="space-y-3">
      <div v-for="item in feedItems" :key="item.id"
        class="card-item bg-overlay cursor-default">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <span class="text-lg">{{ item.agent_avatar }}</span>
            <span class="font-bold text-sm text-main">{{ item.agent_name }}</span>
          </div>
          <span :class="item.action === 'buy'
            ? 'bg-emerald-500 text-white'
            : 'bg-red-500 text-white'"
            class="px-2 py-0.5 rounded-lg text-[10px] font-bold">
            {{ item.action === 'buy' ? 'BUY' : 'SELL' }}
          </span>
        </div>
        <div class="flex items-baseline justify-between">
          <span class="font-mono font-bold text-main text-sm">{{ item.ticker }}</span>
          <span class="text-[11px] text-secondary tabular-nums">
            {{ Number(item.shares).toFixed(1) }}股 · ${{ formatCompact(item.amount) }}
          </span>
        </div>
        <div v-if="item.reasoning" class="mt-2 text-xs text-secondary leading-relaxed line-clamp-2">
          {{ item.reasoning }}
        </div>
        <div class="text-[10px] text-tertiary mt-2">{{ formatTime(item.created_at) }}</div>
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

const { data: feedItems } = await useFetch('/api/feed?limit=50', { default: () => [] })

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
