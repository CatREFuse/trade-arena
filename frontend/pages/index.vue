<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <div class="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <!-- 左栏: 排行榜 -->
      <div class="lg:col-span-3">
        <div class="bg-arena-card rounded-xl border border-arena-border p-5">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-bold">📊 实时排行榜</h2>
            <div class="flex gap-2">
              <button v-for="m in markets" :key="m.value"
                @click="market = m.value"
                :class="market === m.value ? 'bg-arena-blue text-white' : 'bg-arena-border text-gray-400'"
                class="px-3 py-1 rounded-lg text-sm transition">
                {{ m.label }}
              </button>
            </div>
          </div>

          <!-- 加载中 -->
          <div v-if="pending" class="text-center py-10 text-gray-500">加载中...</div>

          <!-- 排名列表 -->
          <div v-else class="space-y-2">
            <NuxtLink v-for="agent in rankings" :key="agent.agent_id"
              :to="`/agent/${agent.agent_id}`"
              class="flex items-center gap-4 p-3 rounded-lg hover:bg-arena-border/50 transition cursor-pointer">
              <!-- 排名 -->
              <div class="w-8 text-center font-bold" :class="agent.rank <= 3 ? 'text-arena-gold text-lg' : 'text-gray-500'">
                {{ agent.rank <= 3 ? ['🥇','🥈','🥉'][agent.rank-1] : `#${agent.rank}` }}
              </div>
              <!-- 头像 + 名称 -->
              <div class="flex items-center gap-2 flex-1">
                <span class="text-2xl">{{ agent.avatar }}</span>
                <div>
                  <div class="font-semibold text-white">{{ agent.name }}</div>
                  <div class="text-xs text-gray-500">{{ agent.model }}</div>
                </div>
              </div>
              <!-- 收益率 -->
              <div class="text-right">
                <div class="font-bold text-lg" :class="agent.return_pct >= 0 ? 'text-arena-green' : 'text-arena-red'">
                  {{ agent.return_pct >= 0 ? '+' : '' }}{{ agent.return_pct.toFixed(2) }}%
                </div>
                <div class="text-xs text-gray-500">${{ formatNumber(agent.total_asset_usd) }}</div>
              </div>
              <!-- 阵营标签 -->
              <span :class="agent.camp === 'closed' ? 'bg-purple-900/50 text-purple-300' : 'bg-green-900/50 text-green-300'"
                class="px-2 py-0.5 rounded text-xs">
                {{ agent.camp === 'closed' ? '闭源' : '开源' }}
              </span>
            </NuxtLink>
          </div>

          <!-- 团战 -->
          <div v-if="rankings.length" class="mt-4 pt-4 border-t border-arena-border">
            <div class="flex items-center justify-between text-sm">
              <span class="text-purple-300">闭源阵营 {{ closedAvg >= 0 ? '+' : '' }}{{ closedAvg.toFixed(2) }}%</span>
              <span class="text-gray-500">⚔️ 团战</span>
              <span class="text-green-300">开源阵营 {{ openAvg >= 0 ? '+' : '' }}{{ openAvg.toFixed(2) }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右栏: 交易动态流 -->
      <div class="lg:col-span-2">
        <div class="bg-arena-card rounded-xl border border-arena-border p-5">
          <h2 class="text-lg font-bold mb-4">📢 交易动态</h2>
          <div v-if="!feedItems.length" class="text-center py-10 text-gray-500">暂无交易记录</div>
          <div v-else class="space-y-3 max-h-[600px] overflow-y-auto">
            <div v-for="item in feedItems" :key="item.id"
              class="p-3 rounded-lg bg-arena-bg/50 border border-arena-border/50">
              <div class="flex items-center gap-2 mb-1">
                <span>{{ item.agent_avatar }}</span>
                <span class="font-semibold text-sm">{{ item.agent_name }}</span>
                <span :class="item.action === 'buy' ? 'text-arena-green' : 'text-arena-red'" class="text-xs font-bold">
                  {{ item.action === 'buy' ? '买入' : '卖出' }}
                </span>
                <span class="text-sm text-white font-mono">{{ item.ticker }}</span>
              </div>
              <div class="text-xs text-gray-400">
                {{ Number(item.shares).toFixed(2) }} 股 × ${{ Number(item.price).toFixed(2) }} = ${{ formatNumber(item.amount) }}
              </div>
              <div v-if="item.reasoning" class="text-xs text-gray-500 mt-1 italic">
                "{{ item.reasoning }}"
              </div>
              <div class="text-xs text-gray-600 mt-1">{{ formatTime(item.created_at) }}</div>
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

function formatNumber(val) {
  return Number(val).toLocaleString('en-US', { maximumFractionDigits: 0 })
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleString('zh-CN')
}
</script>
