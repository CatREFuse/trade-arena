<template>
  <section class="card">
    <div class="flex items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-bold text-main">访问统计</h2>
        <p class="text-xs text-secondary mt-1">页面浏览量与 IP 来源（最近 {{ stats.window_days }} 天）</p>
      </div>
    </div>

    <div class="mt-4 grid grid-cols-2 md:grid-cols-4 gap-2">
      <div class="rounded-xl bg-overlay-2 px-3 py-2">
        <div class="text-[10px] text-tertiary uppercase tracking-widest">总 PV</div>
        <div class="text-sm font-bold text-main tabular-nums mt-1">{{ stats.total_pv }}</div>
      </div>
      <div class="rounded-xl bg-overlay-2 px-3 py-2">
        <div class="text-[10px] text-tertiary uppercase tracking-widest">今日 PV</div>
        <div class="text-sm font-bold text-main tabular-nums mt-1">{{ stats.today_pv }}</div>
      </div>
      <div class="rounded-xl bg-overlay-2 px-3 py-2">
        <div class="text-[10px] text-tertiary uppercase tracking-widest">页面数</div>
        <div class="text-sm font-bold text-main tabular-nums mt-1">{{ stats.unique_page_count }}</div>
      </div>
      <div class="rounded-xl bg-overlay-2 px-3 py-2">
        <div class="text-[10px] text-tertiary uppercase tracking-widest">IP 数</div>
        <div class="text-sm font-bold text-main tabular-nums mt-1">{{ stats.unique_ip_count }}</div>
      </div>
    </div>

    <div class="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
      <div class="rounded-2xl bg-overlay-2 px-4 py-3">
        <div class="text-[11px] uppercase tracking-widest text-tertiary mb-2">页面 PV TOP</div>
        <table class="min-w-full text-xs">
          <thead>
            <tr class="text-left text-tertiary border-b border-zinc-200/80 dark:border-zinc-700/80">
              <th class="py-2 pr-4 font-medium">页面</th>
              <th class="py-2 font-medium text-right">PV</th>
            </tr>
          </thead>
          <tbody v-if="stats.top_pages.length">
            <tr
              v-for="item in stats.top_pages"
              :key="item.path"
              class="border-b border-zinc-200/50 dark:border-zinc-700/50 last:border-0"
            >
              <td class="py-2 pr-4 text-secondary truncate max-w-[18rem]">{{ item.path }}</td>
              <td class="py-2 text-right text-main tabular-nums">{{ item.pv }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="!stats.top_pages.length" class="py-3 text-center text-xs text-tertiary">暂无数据</div>
      </div>

      <div class="rounded-2xl bg-overlay-2 px-4 py-3">
        <div class="text-[11px] uppercase tracking-widest text-tertiary mb-2">IP 来源 TOP</div>
        <table class="min-w-full text-xs">
          <thead>
            <tr class="text-left text-tertiary border-b border-zinc-200/80 dark:border-zinc-700/80">
              <th class="py-2 pr-4 font-medium">IP</th>
              <th class="py-2 pr-4 font-medium">地理位置</th>
              <th class="py-2 font-medium text-right">PV</th>
            </tr>
          </thead>
          <tbody v-if="stats.top_ips.length">
            <tr
              v-for="item in stats.top_ips"
              :key="item.ip"
              class="border-b border-zinc-200/50 dark:border-zinc-700/50 last:border-0"
            >
              <td class="py-2 pr-4 text-secondary">{{ item.ip }}</td>
              <td class="py-2 pr-4 text-secondary">{{ item.geo_label }}</td>
              <td class="py-2 text-right text-main tabular-nums">{{ item.pv }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="!stats.top_ips.length" class="py-3 text-center text-xs text-tertiary">暂无数据</div>
      </div>

      <div class="rounded-2xl bg-overlay-2 px-4 py-3">
        <div class="text-[11px] uppercase tracking-widest text-tertiary mb-2">地域统计（省/国家）</div>
        <table class="min-w-full text-xs">
          <thead>
            <tr class="text-left text-tertiary border-b border-zinc-200/80 dark:border-zinc-700/80">
              <th class="py-2 pr-4 font-medium">地区</th>
              <th class="py-2 pr-4 font-medium">级别</th>
              <th class="py-2 font-medium text-right">PV</th>
            </tr>
          </thead>
          <tbody v-if="stats.top_regions.length">
            <tr
              v-for="item in stats.top_regions"
              :key="`${item.level}-${item.region}`"
              class="border-b border-zinc-200/50 dark:border-zinc-700/50 last:border-0"
            >
              <td class="py-2 pr-4 text-secondary">{{ item.region }}</td>
              <td class="py-2 pr-4 text-secondary">{{ formatLevel(item.level) }}</td>
              <td class="py-2 text-right text-main tabular-nums">{{ item.pv }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="!stats.top_regions.length" class="py-3 text-center text-xs text-tertiary">暂无数据</div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { AdminTrafficStats } from '~/composables/useAdminDashboard'

defineProps<{
  stats: AdminTrafficStats
}>()

function formatLevel(level: string): string {
  if (level === 'province') return '省级'
  if (level === 'country') return '国家'
  return '未知'
}
</script>
