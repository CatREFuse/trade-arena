<template>
  <div class="max-w-4xl mx-auto px-5 py-8 md:py-12">
    <div class="flex items-center justify-between gap-3">
      <div>
        <NuxtLink to="/market" class="text-xs font-medium text-tertiary hover:text-main transition">
          ← 返回市场总览
        </NuxtLink>
        <h1 class="mt-2 text-2xl md:text-3xl font-bold text-main tracking-tight">
          {{ detail.meta.label }}
        </h1>
        <p class="mt-1 text-sm text-secondary">
          {{ detail.meta.subtitle }}
        </p>
        <div class="mt-2">
          <MarketDataTimestamp :timestamp="detail.updatedAt.value" />
        </div>
      </div>
      <div class="hidden sm:block text-right">
        <div>
          <span class="inline-flex items-center rounded-full border border-white/40 bg-white/30 px-2 py-0.5 text-[10px] uppercase tracking-[0.3em] text-zinc-700 backdrop-blur-md dark:border-zinc-700/60 dark:bg-zinc-900/35 dark:text-zinc-200">
            {{ detail.meta.badge }}
          </span>
        </div>
        <div class="mt-1 text-sm font-semibold text-main">{{ stockCount }} 只股票</div>
      </div>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6">
      <div class="rounded-2xl bg-overlay-2 px-4 py-3">
        <div class="text-[10px] uppercase tracking-widest text-tertiary">覆盖股票</div>
        <div class="mt-1 text-xl font-bold text-main tabular-nums">{{ stockCount }}</div>
      </div>
      <div class="rounded-2xl bg-overlay-2 px-4 py-3">
        <div class="text-[10px] uppercase tracking-widest text-tertiary">上涨</div>
        <div class="mt-1 text-xl font-bold tabular-nums" :class="cc.upText.value">{{ detail.positiveCount }}</div>
      </div>
      <div class="rounded-2xl bg-overlay-2 px-4 py-3">
        <div class="text-[10px] uppercase tracking-widest text-tertiary">下跌</div>
        <div class="mt-1 text-xl font-bold tabular-nums" :class="cc.downText.value">{{ detail.negativeCount }}</div>
      </div>
      <div class="rounded-2xl bg-overlay-2 px-4 py-3">
        <div class="text-[10px] uppercase tracking-widest text-tertiary">平均收益</div>
        <div class="mt-1 text-xl font-bold tabular-nums" :class="cc.textClass(detail.averageReturn.value)">
          {{ detail.formatPercent(detail.averageReturn.value) }}
        </div>
      </div>
    </div>

    <div class="card mt-4">
      <div class="flex items-start justify-between gap-4">
        <div>
          <h2 class="text-base font-bold text-main">当前收益分布</h2>
          <p class="text-xs text-secondary mt-1">
            这是基于当前行情快照生成的市场热度曲线，不是历史分钟线。
          </p>
          <div class="mt-2">
            <MarketDataTimestamp :timestamp="detail.updatedAt.value" />
          </div>
        </div>
        <div class="text-right">
          <div class="text-[10px] uppercase tracking-widest text-tertiary">当前排序</div>
          <div class="text-sm font-semibold text-main mt-1">
            {{ detail.sortDirection.value === 'desc' ? '收益率降序' : '收益率升序' }}
          </div>
        </div>
      </div>

      <div class="mt-5 flex items-end gap-3">
        <svg class="w-full h-[84px]" viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">
          <path :d="detail.marketPulse.value.area" fill="currentColor" opacity="0.08" class="text-blue-500" />
          <path
            :d="detail.marketPulse.value.line"
            fill="none"
            class="text-blue-500"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
            opacity="0.6"
          />
        </svg>
      </div>
    </div>

    <MarketMoversSection
      class="mt-4"
      :items="detail.sortedItems.value"
      :pending="detail.pending.value"
      :error="detail.error.value"
      :updated-at="detail.updatedAt.value"
      :sort-direction="detail.sortDirection.value"
      :market="marketKey"
      :format-price="detail.formatPrice"
      :format-percent="detail.formatPercent"
      @toggle-sort="detail.toggleSort"
    />

    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
      <div class="card">
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="text-[10px] uppercase tracking-widest text-tertiary">最高收益</div>
            <div class="mt-2">
              <MarketDataTimestamp :timestamp="detail.updatedAt.value" />
            </div>
          </div>
        </div>
        <div class="mt-2 flex items-center justify-between gap-3">
          <div class="min-w-0">
            <div class="font-bold text-main truncate">{{ detail.bestMover.value?.ticker || 'N/A' }}</div>
            <div class="text-xs text-secondary truncate">{{ detail.bestMover.value?.name || '暂无数据' }}</div>
          </div>
          <div class="text-right flex-shrink-0">
            <div class="text-lg font-bold tabular-nums" :class="cc.textClass(detail.bestMover.value?.change_pct || 0)">
              {{ detail.formatPercent(detail.bestMover.value?.change_pct || 0) }}
            </div>
            <div class="text-[10px] text-tertiary">最高涨幅</div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="text-[10px] uppercase tracking-widest text-tertiary">最低收益</div>
            <div class="mt-2">
              <MarketDataTimestamp :timestamp="detail.updatedAt.value" />
            </div>
          </div>
        </div>
        <div class="mt-2 flex items-center justify-between gap-3">
          <div class="min-w-0">
            <div class="font-bold text-main truncate">{{ detail.worstMover.value?.ticker || 'N/A' }}</div>
            <div class="text-xs text-secondary truncate">{{ detail.worstMover.value?.name || '暂无数据' }}</div>
          </div>
          <div class="text-right flex-shrink-0">
            <div class="text-lg font-bold tabular-nums" :class="cc.textClass(detail.worstMover.value?.change_pct || 0)">
              {{ detail.formatPercent(detail.worstMover.value?.change_pct || 0) }}
            </div>
            <div class="text-[10px] text-tertiary">最低涨幅</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MarketDataTimestamp from '~/components/market/MarketDataTimestamp.vue'
import MarketMoversSection from '~/components/market/MarketMoversSection.vue'
import { useMarketDetail, type MarketKey } from '~/composables/useMarketDetail'

const route = useRoute()
const cc = useColorConvention()

const rawMarket = String(route.params.market || '').toLowerCase()
if (rawMarket !== 'us' && rawMarket !== 'cn' && rawMarket !== 'hk') {
  throw createError({ statusCode: 404, statusMessage: '市场不存在' })
}

const marketKey = rawMarket as MarketKey
const detail = await useMarketDetail(marketKey)

useHead(() => ({
  title: `${detail.meta.value.title} · 市场详情 - CocoLoop Agent 理财竞赛`,
}))

const stockCount = computed(() => detail.items.value.length)
</script>
