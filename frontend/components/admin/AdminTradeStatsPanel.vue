<template>
  <section class="card">
    <div class="flex items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-bold text-main">交易统计</h2>
        <p class="text-xs text-secondary mt-1">成交规模、市场分布与热门标的</p>
      </div>
    </div>

    <div class="mt-4 grid grid-cols-2 md:grid-cols-5 gap-2">
      <div class="rounded-xl bg-overlay-2 px-3 py-2">
        <div class="text-[10px] text-tertiary uppercase tracking-widest">总笔数</div>
        <div class="text-sm font-bold text-main tabular-nums mt-1">{{ stats.totals.trade_count }}</div>
      </div>
      <div class="rounded-xl bg-overlay-2 px-3 py-2">
        <div class="text-[10px] text-tertiary uppercase tracking-widest">总成交额</div>
        <div class="text-sm font-bold text-main tabular-nums mt-1">{{ stats.totals.trade_amount.toFixed(2) }}</div>
      </div>
      <div class="rounded-xl bg-overlay-2 px-3 py-2">
        <div class="text-[10px] text-tertiary uppercase tracking-widest">买入</div>
        <div class="text-sm font-bold text-emerald-600 dark:text-emerald-400 tabular-nums mt-1">{{ stats.totals.buy_count }}</div>
      </div>
      <div class="rounded-xl bg-overlay-2 px-3 py-2">
        <div class="text-[10px] text-tertiary uppercase tracking-widest">卖出</div>
        <div class="text-sm font-bold text-rose-600 dark:text-rose-400 tabular-nums mt-1">{{ stats.totals.sell_count }}</div>
      </div>
      <div class="rounded-xl bg-overlay-2 px-3 py-2">
        <div class="text-[10px] text-tertiary uppercase tracking-widest">24H</div>
        <div class="text-sm font-bold text-main tabular-nums mt-1">{{ stats.totals.recent_24h_count }}</div>
      </div>
    </div>

    <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
      <div class="rounded-2xl bg-overlay-2 px-4 py-3">
        <div class="text-[11px] uppercase tracking-widest text-tertiary mb-2">按市场</div>
        <div class="space-y-2">
          <div
            v-for="(item, market) in stats.by_market"
            :key="market"
            class="flex items-center justify-between text-xs"
          >
            <span class="text-secondary uppercase">{{ market }}</span>
            <span class="text-main tabular-nums">{{ item.count }} / {{ item.amount.toFixed(2) }}</span>
          </div>
        </div>
      </div>
      <div class="rounded-2xl bg-overlay-2 px-4 py-3">
        <div class="text-[11px] uppercase tracking-widest text-tertiary mb-2">热门标的</div>
        <div class="space-y-2">
          <div
            v-for="item in stats.top_tickers.slice(0, 6)"
            :key="item.ticker"
            class="flex items-center justify-between text-xs"
          >
            <span class="text-secondary">{{ item.ticker }}</span>
            <span class="text-main tabular-nums">{{ item.count }} / {{ item.amount.toFixed(2) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="mt-4 overflow-x-auto">
      <table class="min-w-full text-xs">
        <thead>
          <tr class="text-left text-tertiary border-b border-zinc-200/80 dark:border-zinc-700/80">
            <th class="py-2 pr-4 font-medium">日期</th>
            <th class="py-2 pr-4 font-medium">笔数</th>
            <th class="py-2 pr-4 font-medium">买入</th>
            <th class="py-2 pr-4 font-medium">卖出</th>
            <th class="py-2 font-medium">成交额</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in stats.daily"
            :key="item.date"
            class="border-b border-zinc-200/50 dark:border-zinc-700/50 last:border-0"
          >
            <td class="py-2 pr-4 text-secondary tabular-nums">{{ item.date }}</td>
            <td class="py-2 pr-4 text-main tabular-nums">{{ item.count }}</td>
            <td class="py-2 pr-4 text-emerald-600 dark:text-emerald-400 tabular-nums">{{ item.buy_count }}</td>
            <td class="py-2 pr-4 text-rose-600 dark:text-rose-400 tabular-nums">{{ item.sell_count }}</td>
            <td class="py-2 text-main tabular-nums">{{ item.amount.toFixed(2) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="!stats.daily.length" class="py-4 text-center text-xs text-tertiary">暂无统计数据</div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { AdminTradeStats } from '~/composables/useAdminDashboard'

defineProps<{
  stats: AdminTradeStats
}>()
</script>
