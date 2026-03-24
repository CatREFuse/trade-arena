<template>
  <section class="card">
    <div class="flex items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-bold text-main">数据源状态</h2>
        <p class="text-xs text-secondary mt-1">基础设施、上游连通性和缓存状态</p>
      </div>
    </div>

    <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
      <div class="rounded-2xl bg-overlay-2 px-4 py-3">
        <div class="text-[11px] uppercase tracking-widest text-tertiary">基础设施</div>
        <div class="mt-2 text-xs text-main flex items-center gap-3">
          <span :class="statusClass(status.db.ok)">DB {{ status.db.ok ? '正常' : '异常' }}</span>
          <span :class="statusClass(status.redis.ok)">Redis {{ status.redis.ok ? '正常' : '异常' }}</span>
        </div>
      </div>
      <div class="rounded-2xl bg-overlay-2 px-4 py-3">
        <div class="text-[11px] uppercase tracking-widest text-tertiary">缓存</div>
        <div class="mt-2 text-xs text-main flex flex-wrap gap-2">
          <span
            v-for="(cache, key) in status.cache"
            :key="key"
            class="px-2 py-1 rounded-lg"
            :class="statusClass(cache.present)"
          >
            {{ key }} {{ cache.present ? '命中' : '空' }}
          </span>
        </div>
      </div>
    </div>

    <div class="mt-4">
      <div class="text-[11px] uppercase tracking-widest text-tertiary mb-2">上游探活</div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
        <div
          v-for="probe in status.probes"
          :key="probe.name"
          class="rounded-xl bg-overlay-2 px-3 py-2 text-xs flex items-center justify-between gap-3"
        >
          <span class="text-secondary truncate">{{ probe.name }}</span>
          <span :class="statusClass(probe.ok)" class="tabular-nums">{{ probe.latency_ms }}ms</span>
        </div>
      </div>
    </div>

    <div class="mt-4 overflow-x-auto">
      <div class="text-[11px] uppercase tracking-widest text-tertiary mb-2">Provider 熔断状态</div>
      <table class="min-w-full text-xs">
        <thead>
          <tr class="text-left text-tertiary border-b border-zinc-200/80 dark:border-zinc-700/80">
            <th class="py-2 pr-4 font-medium">类型</th>
            <th class="py-2 pr-4 font-medium">市场</th>
            <th class="py-2 pr-4 font-medium">Provider</th>
            <th class="py-2 pr-4 font-medium">失败次数</th>
            <th class="py-2 font-medium">熔断剩余(s)</th>
          </tr>
        </thead>
        <tbody v-if="status.provider_circuits.length">
          <tr
            v-for="item in status.provider_circuits"
            :key="`${item.data_type}-${item.market}-${item.provider}`"
            class="border-b border-zinc-200/50 dark:border-zinc-700/50 last:border-0"
          >
            <td class="py-2 pr-4 text-secondary">{{ item.data_type }}</td>
            <td class="py-2 pr-4 text-secondary">{{ item.market }}</td>
            <td class="py-2 pr-4 text-main">{{ item.provider }}</td>
            <td class="py-2 pr-4 text-main tabular-nums">{{ item.failures }}</td>
            <td class="py-2" :class="statusClass(!item.circuit_open)">
              {{ item.cooldown_remaining_seconds }}
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!status.provider_circuits.length" class="py-4 text-center text-xs text-tertiary">
        当前无熔断记录
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { AdminDataSourceStatus } from '~/composables/useAdminDashboard'

defineProps<{
  status: AdminDataSourceStatus
}>()

function statusClass(ok: boolean) {
  return ok
    ? 'text-emerald-700 dark:text-emerald-300 bg-emerald-100/70 dark:bg-emerald-900/30'
    : 'text-rose-700 dark:text-rose-300 bg-rose-100/70 dark:bg-rose-900/30'
}
</script>
