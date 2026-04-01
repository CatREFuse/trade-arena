<template>
  <section class="card">
    <div class="flex items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-bold text-main">用户信息</h2>
        <p class="text-xs text-secondary mt-1">注册用户、账户与交易活跃度</p>
      </div>
      <div class="text-xs text-tertiary">总数 {{ total }}</div>
    </div>

    <div class="mt-4 overflow-x-auto">
      <table class="min-w-full text-xs">
        <thead>
          <tr class="text-left text-tertiary border-b border-zinc-200/80 dark:border-zinc-700/80">
            <th class="py-2 pr-4 font-medium">用户</th>
            <th class="py-2 pr-4 font-medium">邮箱</th>
            <th class="py-2 pr-4 font-medium">模型</th>
            <th class="py-2 pr-4 font-medium">账户数</th>
            <th class="py-2 pr-4 font-medium">交易数</th>
            <th class="py-2 pr-4 font-medium">资产（人民币）</th>
            <th class="py-2 font-medium">注册时间</th>
          </tr>
        </thead>
        <tbody v-if="items.length">
          <tr
            v-for="user in items"
            :key="user.id"
            class="border-b border-zinc-200/50 dark:border-zinc-700/50 last:border-0"
          >
            <td class="py-2 pr-4 text-main">
              <div class="flex items-center gap-2">
                <span>{{ user.avatar }}</span>
                <span class="font-medium">{{ user.name }}</span>
              </div>
            </td>
            <td class="py-2 pr-4 text-secondary">{{ user.email || '-' }}</td>
            <td class="py-2 pr-4 text-secondary">{{ user.model }}</td>
            <td class="py-2 pr-4 text-secondary">{{ user.account_count }}</td>
            <td class="py-2 pr-4 text-secondary">{{ user.trade_count }}</td>
            <td class="py-2 pr-4 text-main tabular-nums">{{ formatCny(user.asset_cny ?? user.asset_usd) }}</td>
            <td class="py-2 text-tertiary tabular-nums">{{ formatDate(user.created_at) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="!items.length" class="py-6 text-center text-xs text-tertiary">暂无数据</div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { AdminUserItem } from '~/composables/useAdminDashboard'

defineProps<{
  total: number
  items: AdminUserItem[]
}>()

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime()))
    return '未知'

  return date.toLocaleString('zh-CN', { hour12: false })
}
</script>
