<template>
  <section class="card">
        <div class="flex items-start justify-between gap-3 mb-5">
      <div>
        <h2 class="text-base font-bold text-main">市场详情</h2>
        <p class="text-xs text-secondary mt-1">
          按收益率排序，支持反转查看强势和弱势分布。
        </p>
        <div class="mt-2">
          <MarketDataTimestamp :timestamp="updatedAt" />
        </div>
      </div>
      <button
        class="px-3 py-1.5 rounded-xl text-xs font-medium bg-overlay-2 text-secondary hover:text-main transition"
        @click="$emit('toggle-sort')"
      >
        {{ sortDirection === 'desc' ? '收益率降序' : '收益率升序' }}
      </button>
    </div>

    <div v-if="pending && !items.length" class="space-y-2">
      <div v-for="n in 8" :key="n" class="rounded-2xl bg-overlay-2/60 px-4 py-3 animate-pulse">
        <div class="flex items-center justify-between gap-4">
          <div class="space-y-2">
            <div class="h-3 w-16 rounded bg-zinc-200 dark:bg-zinc-700"></div>
            <div class="h-2.5 w-24 rounded bg-zinc-200 dark:bg-zinc-700"></div>
          </div>
          <div class="space-y-2 text-right">
            <div class="h-3 w-14 rounded bg-zinc-200 dark:bg-zinc-700 ml-auto"></div>
            <div class="h-2.5 w-12 rounded bg-zinc-200 dark:bg-zinc-700 ml-auto"></div>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="error" class="rounded-2xl bg-red-50 dark:bg-red-950/30 px-4 py-5 text-sm text-red-700 dark:text-red-300">
      市场详情加载失败，请稍后重试。
    </div>

    <div v-else-if="!items.length" class="rounded-2xl bg-overlay-2 px-4 py-8 text-center text-sm text-tertiary">
      当前市场没有可展示的股票。
    </div>

    <div v-else class="divide-y divide-zinc-200 dark:divide-zinc-700">
      <div v-for="(item, index) in items" :key="item.ticker" class="flex items-center gap-4 py-3">
        <div class="w-7 text-center text-xs font-bold flex-shrink-0" :class="index < 3 ? 'text-amber-500' : 'text-tertiary'">
          {{ index + 1 }}
        </div>
        <div class="flex items-center gap-3 min-w-0 flex-1">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-mono text-main font-bold text-sm">{{ item.ticker }}</span>
              <span
                class="w-1.5 h-1.5 rounded-full flex-shrink-0"
                :class="item.market_status === 'open' ? 'bg-emerald-500' : 'bg-zinc-300 dark:bg-zinc-600'"
              ></span>
            </div>
            <div class="text-[10px] text-tertiary truncate">{{ item.name }}</div>
          </div>
        </div>

        <div class="hidden sm:block flex-shrink-0">
          <MarketTrendSparkline :seed="item.ticker" :change="item.change_pct" />
        </div>

        <div class="text-right flex-shrink-0">
          <div class="text-sm font-bold text-main tabular-nums">{{ formatPrice(item.price, market) }}</div>
          <div class="text-xs font-bold tabular-nums" :class="cc.textClass(item.change_pct)">
            {{ formatPercent(item.change_pct) }}
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import MarketDataTimestamp from './MarketDataTimestamp.vue'
import MarketTrendSparkline from './MarketTrendSparkline.vue'

interface MarketListItem {
  ticker: string
  name: string
  price: number
  change_pct: number
  market_status: string
}

defineProps<{
  items: MarketListItem[]
  pending: boolean
  error: unknown
  updatedAt?: string | null
  sortDirection: 'asc' | 'desc'
  market: 'us' | 'cn'
  formatPrice: (value: number, market: 'us' | 'cn') => string
  formatPercent: (value: number) => string
}>()

defineEmits<{
  (event: 'toggle-sort'): void
}>()

const cc = useColorConvention()
</script>
