<template>
  <article class="card">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <span class="text-2xl">{{ emoji }}</span>
        <div>
          <div class="label">{{ badge }}</div>
          <div class="flex items-center gap-2">
            <div class="font-body text-body-sm text-primary">{{ title }}</div>
            <span
              class="inline-flex items-center border rounded-sm px-2 py-[2px] font-mono text-[10px] leading-none tracking-[0.08em]"
              :class="getMarketStatusBadgeClass(summary?.market_status)"
            >
              {{ formatMarketStatus(summary?.market_status) }}
            </span>
            <span
              class="inline-flex items-center border border-border-visible bg-transparent px-2 py-[2px] font-mono text-[10px] leading-none tracking-[0.08em] text-secondary"
            >
              交易时段 {{ formatSessionWindows(summary?.session_windows) }}
            </span>
          </div>
        </div>
      </div>
      <NuxtLink
        :to="`/market-detail/${marketType}`"
        class="font-mono text-caption text-secondary hover:text-primary transition-colors"
      >
        查看 →
      </NuxtLink>
    </div>

    <!-- Stats Grid -->
    <div class="grid grid-cols-4 gap-4 mb-6">
      <div>
        <div class="label mb-1">股票数</div>
        <div class="font-mono type-subheading numeric text-primary">{{ summary?.stock_count || 0 }}</div>
      </div>
      <div>
        <div class="label mb-1">上涨</div>
        <div class="font-mono type-subheading numeric" :class="isCN ? 'text-success' : 'text-accent'">
          {{ summary?.up_count || 0 }}
        </div>
      </div>
      <div>
        <div class="label mb-1">下跌</div>
        <div class="font-mono type-subheading numeric" :class="isCN ? 'text-accent' : 'text-success'">
          {{ summary?.down_count || 0 }}
        </div>
      </div>
      <div>
        <div class="label mb-1">平盘</div>
        <div class="font-mono type-subheading numeric text-primary">{{ summary?.flat_count || 0 }}</div>
      </div>
    </div>

    <!-- Indices -->
    <div class="grid grid-cols-3 gap-3 mb-6 pt-4 border-t border-border">
      <div
        v-for="index in indices"
        :key="index.symbol"
      >
        <div class="label mb-1">{{ index.shortLabel }}</div>
        <div class="font-mono text-body-sm numeric text-primary">{{ index.value }}</div>
        <div
          class="font-mono text-caption numeric"
          :class="getChangeColor(index.changePct)"
        >
          {{ formatPercent(index.changePct) }}
        </div>
      </div>
    </div>

    <!-- Leader / Laggard -->
    <div class="grid grid-cols-2 gap-4 pt-4 border-t border-border">
      <!-- Leader -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="label" :class="isCN ? 'text-success' : 'text-accent'">领涨</span>
          <NuxtLink
            v-if="summary?.leader?.ticker"
            :to="`/market-detail/${marketType}/${summary.leader.ticker}`"
            class="font-mono text-body-sm text-primary hover:text-display"
          >
            {{ summary.leader.ticker }}
          </NuxtLink>
          <span v-else class="font-mono text-body-sm text-disabled">--</span>
        </div>
        <span class="font-mono text-caption numeric" :class="isCN ? 'text-success' : 'text-accent'">
          {{ summary?.leader ? formatPercent(summary.leader.change_pct) : '--' }}
        </span>
      </div>
      <!-- Laggard -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="label" :class="isCN ? 'text-accent' : 'text-success'">领跌</span>
          <NuxtLink
            v-if="summary?.laggard?.ticker"
            :to="`/market-detail/${marketType}/${summary.laggard.ticker}`"
            class="font-mono text-body-sm text-primary hover:text-display"
          >
            {{ summary.laggard.ticker }}
          </NuxtLink>
          <span v-else class="font-mono text-body-sm text-disabled">--</span>
        </div>
        <span class="font-mono text-caption numeric" :class="isCN ? 'text-accent' : 'text-success'">
          {{ summary?.laggard ? formatPercent(summary.laggard.change_pct) : '--' }}
        </span>
      </div>
    </div>

    <div class="mt-5 pt-4 border-t border-border">
      <div class="label mb-3">热门个股</div>
      <div v-if="boardItems.length" class="divide-y divide-border">
        <NuxtLink
          v-for="item in boardItems"
          :key="item.ticker"
          :to="`/market-detail/${marketType}/${item.ticker}`"
          class="flex items-center justify-between gap-3 py-2.5 hover:bg-overlay-2 transition-colors"
        >
          <div class="min-w-0">
            <div class="font-mono text-body-sm text-primary truncate">{{ item.ticker }}</div>
            <div class="text-[11px] text-secondary truncate">{{ item.name }}</div>
          </div>
          <div class="text-right flex-shrink-0">
            <div class="font-mono text-caption text-primary numeric">{{ formatPrice(item.price) }}</div>
            <div class="font-mono text-caption numeric" :class="getChangeColor(item.change_pct)">
              {{ formatPercent(item.change_pct) }}
            </div>
          </div>
        </NuxtLink>
      </div>
      <div v-else class="font-mono text-caption text-disabled">暂无个股数据</div>
    </div>
  </article>
</template>

<script setup lang="ts">
interface IndexSnapshot {
  symbol: string
  shortLabel: string
  value: string
  changePct: number | null
}

interface BoardItem {
  ticker: string
  name: string
  price: number | string
  change_pct: number
}

interface MarketSummary {
  market_status?: string
  timezone?: string
  session_windows?: string[]
  now_local?: string | null
  next_open_local?: string | null
  stock_count: number
  up_count: number
  down_count: number
  flat_count: number
  leader?: BoardItem | null
  laggard?: BoardItem | null
}

const props = withDefaults(defineProps<{
  title: string
  emoji: string
  badge: string
  summary?: MarketSummary
  indices: IndexSnapshot[]
  marketType: string
  isCN?: boolean
  boardItems?: BoardItem[]
}>(), {
  boardItems: () => [],
})

function getChangeColor(change: number | null): string {
  if (change === null || change === undefined || Number.isNaN(change)) return 'text-disabled'
  if (props.isCN) {
    return change >= 0 ? 'text-success' : 'text-accent'
  }
  return change >= 0 ? 'text-accent' : 'text-success'
}

function formatPercent(value: number | undefined | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function formatPrice(value: number | string): string {
  const num = Number(value)
  if (!Number.isFinite(num)) return '--'
  return num.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatMarketStatus(status: string | undefined): string {
  if (status === 'open') return '开盘'
  if (status === 'closed') return '休市'
  return '--'
}

function getMarketStatusBadgeClass(status: string | undefined): string {
  if (status === 'open') return 'text-[#8EE4A7] border-[#2E5E3A] bg-[#122017]'
  if (status === 'closed') return 'text-secondary border-border-visible bg-overlay-2'
  return 'text-disabled border-border-visible bg-overlay-2'
}

function formatSessionWindows(sessionWindows: string[] | undefined): string {
  if (!sessionWindows?.length) return '--'
  return sessionWindows.join(' / ')
}

</script>
