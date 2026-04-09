<template>
  <section class="card">
    <div class="flex items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-bold text-main">操作日志</h2>
        <p class="text-xs text-secondary mt-1">最近交易行为流</p>
      </div>
      <div class="text-xs text-tertiary">
        总交易 {{ props.total }} · 买入 {{ props.buyTotal }} · 卖出 {{ props.sellTotal }}
      </div>
    </div>

    <div class="mt-4 overflow-x-auto">
      <table class="min-w-full text-xs">
        <thead>
          <tr class="text-left text-tertiary border-b border-zinc-200/80 dark:border-zinc-700/80">
            <th class="py-2 pr-4 font-medium">时间</th>
            <th class="py-2 pr-4 font-medium">用户</th>
            <th class="py-2 pr-4 font-medium">动作</th>
            <th class="py-2 pr-4 font-medium">标的</th>
            <th class="py-2 pr-4 font-medium">金额</th>
            <th class="py-2 font-medium">理由</th>
          </tr>
        </thead>
        <tbody v-if="props.items.length">
          <tr
            v-for="log in props.items"
            :key="log.id"
            class="border-b border-zinc-200/50 dark:border-zinc-700/50 last:border-0"
          >
            <td class="py-2 pr-4 text-tertiary tabular-nums">{{ formatDate(log.created_at) }}</td>
            <td class="py-2 pr-4 text-main">
              <div class="flex items-center gap-2">
                <span>{{ log.agent_avatar || '👤' }}</span>
                <span>{{ log.agent_name || log.agent_id || '-' }}</span>
              </div>
            </td>
            <td class="py-2 pr-4">
              <span
                class="px-2 py-0.5 rounded-full text-[10px] font-medium"
                :class="log.action === 'buy'
                  ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300'
                  : 'bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-300'"
              >
                {{ log.action }}
              </span>
            </td>
            <td class="py-2 pr-4 text-secondary">{{ log.ticker }} · {{ log.market.toUpperCase() }}</td>
            <td class="py-2 pr-4 text-main tabular-nums">{{ log.amount.toFixed(2) }}</td>
            <td class="py-2 text-secondary max-w-[24rem] truncate">{{ log.reasoning || '-' }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="!props.items.length" class="py-6 text-center text-xs text-tertiary">暂无日志</div>
    </div>

    <div v-if="totalPages > 1" class="mt-4 flex items-center justify-between gap-3">
      <div class="text-xs text-tertiary">
        第 {{ props.page }} / {{ totalPages }} 页
      </div>
      <div class="flex items-center gap-2">
        <button
          type="button"
          class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-zinc-100 dark:bg-zinc-800 text-main hover:bg-zinc-200 dark:hover:bg-zinc-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="props.pending || props.page <= 1"
          @click="$emit('page-change', props.page - 1)"
        >
          上一页
        </button>
        <button
          type="button"
          class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-zinc-100 dark:bg-zinc-800 text-main hover:bg-zinc-200 dark:hover:bg-zinc-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="props.pending || props.page >= totalPages"
          @click="$emit('page-change', props.page + 1)"
        >
          下一页
        </button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { AdminLogItem } from '~/composables/useAdminDashboard'
import { parseApiDate } from '~/utils/date'

const props = withDefaults(defineProps<{
  items: AdminLogItem[]
  total: number
  buyTotal: number
  sellTotal: number
  page: number
  pageSize: number
  pending?: boolean
}>(), {
  pending: false,
})

defineEmits<{
  (event: 'page-change', page: number): void
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / Math.max(props.pageSize, 1))))

function formatDate(value: string) {
  const date = parseApiDate(value)
  if (Number.isNaN(date.getTime()))
    return '未知'

  return date.toLocaleString('zh-CN', { hour12: false })
}
</script>
