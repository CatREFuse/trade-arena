<template>
  <article class="card">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <span class="text-2xl">{{ emoji }}</span>
        <div>
          <div class="label">{{ badge }}</div>
          <div class="font-body text-body-sm text-primary">{{ title }}</div>
        </div>
      </div>
      <NuxtLink
        :to="`/market-detail/${marketType}`"
        class="font-mono text-caption text-secondary hover:text-primary transition-colors"
      >
        VIEW →
      </NuxtLink>
    </div>

    <!-- Stats Grid -->
    <div class="grid grid-cols-4 gap-4 mb-6">
      <div>
        <div class="label mb-1">STOCKS</div>
        <div class="font-mono type-subheading numeric text-primary">{{ summary?.stock_count || 0 }}</div>
      </div>
      <div>
        <div class="label mb-1">UP</div>
        <div class="font-mono type-subheading numeric" :class="isCN ? 'text-success' : 'text-accent'">
          {{ summary?.up_count || 0 }}
        </div>
      </div>
      <div>
        <div class="label mb-1">DOWN</div>
        <div class="font-mono type-subheading numeric" :class="isCN ? 'text-accent' : 'text-success'">
          {{ summary?.down_count || 0 }}
        </div>
      </div>
      <div>
        <div class="label mb-1">FLAT</div>
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
          <span class="label" :class="isCN ? 'text-success' : 'text-accent'">LEADER</span>
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
          <span class="label" :class="isCN ? 'text-accent' : 'text-success'">LAGGARD</span>
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
  change_pct: number
}

interface MarketSummary {
  stock_count: number
  up_count: number
  down_count: number
  flat_count: number
  leader?: BoardItem | null
  laggard?: BoardItem | null
}

const props = defineProps<{
  title: string
  emoji: string
  badge: string
  summary?: MarketSummary
  indices: IndexSnapshot[]
  marketType: string
  isCN: boolean
}>()

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
</script>
