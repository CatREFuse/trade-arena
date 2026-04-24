<template>
  <section class="card">
    <div class="flex items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-bold text-main">数据源总览</h2>
        <p class="text-xs text-secondary mt-1">基础设施、缓存、上游探活与 Provider 状态</p>
      </div>
      <div class="text-xs text-tertiary">
        {{ pending ? '刷新中' : `共 ${rows.length} 项` }}
      </div>
    </div>

    <div class="mt-4 overflow-x-auto">
      <table class="min-w-full text-xs">
        <thead>
          <tr class="text-left text-tertiary border-b border-zinc-200/80 dark:border-zinc-700/80">
            <th class="py-2 pr-4 font-medium">分类</th>
            <th class="py-2 pr-4 font-medium">名称</th>
            <th class="py-2 pr-4 font-medium">状态</th>
            <th class="py-2 pr-4 font-medium">详情</th>
            <th class="py-2 font-medium">指标</th>
          </tr>
        </thead>
        <tbody v-if="rows.length">
          <tr
            v-for="row in rows"
            :key="row.id"
            class="border-b border-zinc-200/50 dark:border-zinc-700/50 last:border-0"
          >
            <td class="py-2 pr-4 text-secondary">{{ row.category }}</td>
            <td class="py-2 pr-4 text-main">{{ row.name }}</td>
            <td class="py-2 pr-4">
                <span
                class="px-2 py-0.5 rounded-full text-[10px] font-medium"
                :class="stateClass(row.ok)"
              >
                {{ stateLabel(row.ok) }}
              </span>
            </td>
            <td class="py-2 pr-4 text-secondary max-w-[24rem] truncate">{{ row.detail || '-' }}</td>
            <td class="py-2 text-main tabular-nums">{{ row.metric || '-' }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="!rows.length" class="py-4 text-center text-xs text-tertiary">{{ pending ? '载入中' : '暂未返回' }}</div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { AdminDataSourceStatus } from '~/composables/useAdminDashboard'

interface DataSourceRow {
  id: string
  category: string
  name: string
  ok: boolean | null
  detail: string
  metric: string
}

const props = defineProps<{
  status: AdminDataSourceStatus
  pending?: boolean
}>()

function stateClass(ok: boolean | null) {
  if (ok === null)
    return 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300'
  return ok
    ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300'
    : 'bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-300'
}

function stateLabel(ok: boolean | null) {
  if (ok === null)
    return '未获取'
  return ok ? '正常' : '异常'
}

const rows = computed<DataSourceRow[]>(() => {
  const list: DataSourceRow[] = []

  list.push({
    id: 'infra-db',
    category: '基础设施',
    name: 'PostgreSQL',
    ok: props.status.db.ok,
    detail: props.status.db.detail || '',
    metric: '-',
  })
  list.push({
    id: 'infra-redis',
    category: '基础设施',
    name: 'Redis',
    ok: props.status.redis.ok,
    detail: props.status.redis.detail || '',
    metric: '-',
  })

  for (const [cacheKey, cacheValue] of Object.entries(props.status.cache || {})) {
    list.push({
      id: `cache-${cacheKey}`,
      category: '缓存',
      name: cacheKey,
      ok: Boolean(cacheValue.present),
      detail: cacheValue.updated_at ? `更新时间 ${cacheValue.updated_at}` : '',
      metric: cacheValue.present ? '命中' : '空',
    })
  }

  for (const probe of props.status.probes || []) {
    list.push({
      id: `probe-${probe.name}`,
      category: '上游探活',
      name: probe.name,
      ok: Boolean(probe.ok),
      detail: probe.detail || '',
      metric: `${probe.latency_ms}ms`,
    })
  }

  for (const [key, chain] of Object.entries(props.status.provider_chains || {})) {
    const chainList = Array.isArray(chain) ? chain : []
    list.push({
      id: `chain-${key}`,
      category: 'Provider 链路',
      name: key,
      ok: chainList.length > 0,
      detail: chainList.join(' -> '),
      metric: `${chainList.length} 个`,
    })
  }

  for (const item of props.status.provider_circuits || []) {
    list.push({
      id: `circuit-${item.data_type}-${item.market}-${item.provider}`,
      category: '熔断状态',
      name: `${item.provider} (${item.market}/${item.data_type})`,
      ok: !item.circuit_open,
      detail: `失败 ${item.failures} 次`,
      metric: `${item.cooldown_remaining_seconds}s`,
    })
  }

  return list
})
</script>
