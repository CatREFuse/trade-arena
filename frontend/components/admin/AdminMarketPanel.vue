<template>
  <section class="card">
    <div class="flex items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-bold text-main">大盘信息</h2>
        <p class="text-xs text-secondary mt-1">指数快照与市场宽度</p>
      </div>
      <div class="text-xs text-tertiary tabular-nums">{{ formatDate(snapshot.updated_at) }}</div>
    </div>

    <div class="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
      <div
        v-for="index in snapshot.indices"
        :key="index.symbol"
        class="rounded-2xl bg-overlay-2 px-4 py-3"
      >
        <div class="text-[11px] uppercase tracking-widest text-tertiary">{{ index.symbol }}</div>
        <div class="mt-1 text-sm font-semibold text-main">{{ index.name }}</div>
        <div class="mt-2 text-base font-bold text-main tabular-nums">{{ index.price }}</div>
        <div :class="index.change_pct >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'" class="text-xs font-medium">
          {{ index.change_pct >= 0 ? '+' : '' }}{{ index.change_pct.toFixed(2) }}%
        </div>
      </div>
    </div>

    <div class="mt-4 overflow-x-auto">
      <table class="min-w-full text-xs">
        <thead>
          <tr class="text-left text-tertiary border-b border-zinc-200/80 dark:border-zinc-700/80">
            <th class="py-2 pr-4 font-medium">市场</th>
            <th class="py-2 pr-4 font-medium">股票数</th>
            <th class="py-2 pr-4 font-medium">上涨</th>
            <th class="py-2 pr-4 font-medium">下跌</th>
            <th class="py-2 font-medium">平均涨跌</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in snapshot.market_summary"
            :key="item.market"
            class="border-b border-zinc-200/50 dark:border-zinc-700/50 last:border-0"
          >
            <td class="py-2 pr-4 text-main">{{ item.name }}</td>
            <td class="py-2 pr-4 text-secondary tabular-nums">{{ item.stock_count }}</td>
            <td class="py-2 pr-4 text-emerald-600 dark:text-emerald-400 tabular-nums">{{ item.up_count }}</td>
            <td class="py-2 pr-4 text-rose-600 dark:text-rose-400 tabular-nums">{{ item.down_count }}</td>
            <td class="py-2 text-main tabular-nums">{{ item.avg_change_pct.toFixed(2) }}%</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { AdminMarketSnapshot } from '~/composables/useAdminDashboard'

defineProps<{
  snapshot: AdminMarketSnapshot
}>()

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime()))
    return '未知'

  return date.toLocaleString('zh-CN', { hour12: false })
}
</script>
