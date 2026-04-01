<template>
  <div class="max-w-4xl mx-auto px-5 py-8 md:py-12">
    <!-- Header -->
    <section class="card bg-overlay overflow-hidden">
      <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div class="text-[11px] uppercase tracking-[0.2em] text-tertiary">市场总览</div>
          <h1 class="mt-2 text-3xl font-bold text-main tracking-tight">三地市场，一页看清</h1>
          <p class="mt-2 max-w-2xl text-sm leading-7 text-secondary">
            美股、A 股、港股主要指数与盘口快照。
          </p>
          <div class="mt-2">
            <MarketDataTimestamp :timestamp="overviewData.updated_at" />
          </div>
        </div>
        <div class="flex items-center gap-2 text-xs text-tertiary">
          <span>最近更新 {{ updatedAtLabel }}</span>
          <button
            type="button"
            class="rounded-xl bg-overlay-2 px-3 py-2 font-medium text-secondary transition hover:text-main"
            :disabled="isLoading"
            @click="manualRefresh"
          >
            {{ isLoading ? '刷新中...' : '立即刷新' }}
          </button>
        </div>
      </div>
    </section>

    <!-- Market Cards - Flat Structure with SVG Backgrounds -->
    <section class="mt-6 space-y-4">
      <!-- US Market Card -->
      <article class="relative overflow-hidden rounded-3xl bg-white dark:bg-zinc-800 border border-zinc-200/70 dark:border-zinc-700/80">
        <!-- SVG Trend Background -->
        <div class="absolute inset-0 pointer-events-none opacity-30">
          <svg class="w-full h-full" viewBox="0 0 400 200" preserveAspectRatio="none" aria-hidden="true">
            <defs>
              <linearGradient :id="`us-trend-gradient-${usTrendId}`" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" :stop-color="usTrendColor" stop-opacity="0.4"/>
                <stop offset="100%" :stop-color="usTrendColor" stop-opacity="0"/>
              </linearGradient>
            </defs>
            <path :d="usTrendPath.area" :fill="`url(#us-trend-gradient-${usTrendId})`" />
            <path :d="usTrendPath.line" fill="none" :stroke="usTrendColor" stroke-width="1.5" opacity="0.6"/>
          </svg>
        </div>

        <div class="relative p-5 sm:p-6">
          <!-- Card Header -->
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                <span class="text-2xl leading-none">🇺🇸</span>
              </div>
              <div>
                <h2 class="text-xl font-bold text-main tracking-tight">美股市场</h2>
                <div class="mt-2">
                  <MarketDataTimestamp :timestamp="overviewData.updated_at" />
                </div>
              </div>
            </div>
            <NuxtLink
              to="/market-detail/us"
              class="inline-flex items-center justify-center rounded-xl bg-overlay-2 px-4 py-2 text-sm font-medium text-main transition hover:-translate-y-0.5"
            >
              进入美股看盘 →
            </NuxtLink>
          </div>

          <!-- Stats Row -->
          <div class="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div class="text-center sm:text-left">
              <div class="text-[10px] uppercase tracking-widest text-tertiary">股票数</div>
              <div class="mt-1 text-lg font-bold text-main tabular-nums">{{ usSummary?.stock_count || 0 }}</div>
            </div>
            <div class="text-center sm:text-left">
              <div class="text-[10px] uppercase tracking-widest text-tertiary">上涨</div>
              <div class="mt-1 text-lg font-bold text-emerald-600 dark:text-emerald-400 tabular-nums">{{ usSummary?.up_count || 0 }}</div>
            </div>
            <div class="text-center sm:text-left">
              <div class="text-[10px] uppercase tracking-widest text-tertiary">下跌</div>
              <div class="mt-1 text-lg font-bold text-red-600 dark:text-red-400 tabular-nums">{{ usSummary?.down_count || 0 }}</div>
            </div>
            <div class="text-center sm:text-left">
              <div class="text-[10px] uppercase tracking-widest text-tertiary">平盘</div>
              <div class="mt-1 text-lg font-bold text-main tabular-nums">{{ usSummary?.flat_count || 0 }}</div>
            </div>
          </div>

          <!-- Indices Row -->
          <div class="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
            <div
              v-for="index in usIndices"
              :key="index.symbol"
              class="min-w-0 flex items-center justify-between gap-2 rounded-lg border border-white/45 bg-white/20 px-3 py-2 shadow-sm backdrop-blur-xl dark:border-zinc-600/55 dark:bg-zinc-900/25"
            >
              <span class="truncate text-xs text-tertiary">{{ index.shortLabel }}</span>
              <span class="text-sm font-bold text-main tabular-nums whitespace-nowrap">{{ index.value }}</span>
              <span class="text-xs font-bold tabular-nums" :class="cc.textClass(index.changePct)">
                {{ formatPercent(index.changePct) }}
              </span>
            </div>
          </div>

          <!-- Leader/Laggard -->
          <div class="mt-4 grid grid-cols-2 gap-3">
            <div class="flex items-center justify-between gap-2 rounded-xl bg-emerald-500/5 dark:bg-emerald-500/10 px-3 py-2 border border-emerald-500/10">
              <div class="flex items-center gap-2">
                <span class="text-[10px] uppercase tracking-wider text-emerald-600 dark:text-emerald-400">领涨</span>
                <span class="text-sm font-bold text-main">{{ usSummary?.leader?.ticker || '--' }}</span>
              </div>
              <div class="text-right">
                <div class="text-xs font-bold text-emerald-600 dark:text-emerald-400 tabular-nums">
                  {{ usSummary?.leader ? formatPercent(usSummary.leader.change_pct) : '--' }}
                </div>
              </div>
            </div>
            <div class="flex items-center justify-between gap-2 rounded-xl bg-red-500/5 dark:bg-red-500/10 px-3 py-2 border border-red-500/10">
              <div class="flex items-center gap-2">
                <span class="text-[10px] uppercase tracking-wider text-red-600 dark:text-red-400">领跌</span>
                <span class="text-sm font-bold text-main">{{ usSummary?.laggard?.ticker || '--' }}</span>
              </div>
              <div class="text-right">
                <div class="text-xs font-bold text-red-600 dark:text-red-400 tabular-nums">
                  {{ usSummary?.laggard ? formatPercent(usSummary.laggard.change_pct) : '--' }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </article>

      <!-- CN Market Card -->
      <article class="relative overflow-hidden rounded-3xl bg-white dark:bg-zinc-800 border border-zinc-200/70 dark:border-zinc-700/80">
        <!-- SVG Trend Background -->
        <div class="absolute inset-0 pointer-events-none opacity-30">
          <svg class="w-full h-full" viewBox="0 0 400 200" preserveAspectRatio="none" aria-hidden="true">
            <defs>
              <linearGradient :id="`cn-trend-gradient-${cnTrendId}`" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" :stop-color="cnTrendColor" stop-opacity="0.4"/>
                <stop offset="100%" :stop-color="cnTrendColor" stop-opacity="0"/>
              </linearGradient>
            </defs>
            <path :d="cnTrendPath.area" :fill="`url(#cn-trend-gradient-${cnTrendId})`" />
            <path :d="cnTrendPath.line" fill="none" :stroke="cnTrendColor" stroke-width="1.5" opacity="0.6"/>
          </svg>
        </div>

        <div class="relative p-5 sm:p-6">
          <!-- Card Header -->
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center">
                <span class="text-2xl leading-none">🇨🇳</span>
              </div>
              <div>
                <h2 class="text-xl font-bold text-main tracking-tight">A 股市场</h2>
                <div class="mt-2">
                  <MarketDataTimestamp :timestamp="overviewData.updated_at" />
                </div>
              </div>
            </div>
            <NuxtLink
              to="/market-detail/cn"
              class="inline-flex items-center justify-center rounded-xl bg-overlay-2 px-4 py-2 text-sm font-medium text-main transition hover:-translate-y-0.5"
            >
              进入A股看盘 →
            </NuxtLink>
          </div>

          <!-- Stats Row -->
          <div class="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div class="text-center sm:text-left">
              <div class="text-[10px] uppercase tracking-widest text-tertiary">股票数</div>
              <div class="mt-1 text-lg font-bold text-main tabular-nums">{{ cnSummary?.stock_count || 0 }}</div>
            </div>
            <div class="text-center sm:text-left">
              <div class="text-[10px] uppercase tracking-widest text-tertiary">上涨</div>
              <div class="mt-1 text-lg font-bold text-red-600 dark:text-red-400 tabular-nums">{{ cnSummary?.up_count || 0 }}</div>
            </div>
            <div class="text-center sm:text-left">
              <div class="text-[10px] uppercase tracking-widest text-tertiary">下跌</div>
              <div class="mt-1 text-lg font-bold text-emerald-600 dark:text-emerald-400 tabular-nums">{{ cnSummary?.down_count || 0 }}</div>
            </div>
            <div class="text-center sm:text-left">
              <div class="text-[10px] uppercase tracking-widest text-tertiary">平盘</div>
              <div class="mt-1 text-lg font-bold text-main tabular-nums">{{ cnSummary?.flat_count || 0 }}</div>
            </div>
          </div>

          <!-- Indices Row -->
          <div class="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
            <div
              v-for="index in cnIndices"
              :key="index.symbol"
              class="min-w-0 flex items-center justify-between gap-2 rounded-lg border border-white/45 bg-white/20 px-3 py-2 shadow-sm backdrop-blur-xl dark:border-zinc-600/55 dark:bg-zinc-900/25"
            >
              <span class="truncate text-xs text-tertiary">{{ index.shortLabel }}</span>
              <span class="text-sm font-bold text-main tabular-nums whitespace-nowrap">{{ index.value }}</span>
              <span class="text-xs font-bold tabular-nums" :class="cc.textClass(index.changePct)">
                {{ formatPercent(index.changePct) }}
              </span>
            </div>
          </div>

          <!-- Leader/Laggard -->
          <div class="mt-4 grid grid-cols-2 gap-3">
            <div class="flex items-center justify-between gap-2 rounded-xl bg-red-500/5 dark:bg-red-500/10 px-3 py-2 border border-red-500/10">
              <div class="flex items-center gap-2">
                <span class="text-[10px] uppercase tracking-wider text-red-600 dark:text-red-400">领涨</span>
                <span class="text-sm font-bold text-main">{{ cnSummary?.leader?.ticker || '--' }}</span>
              </div>
              <div class="text-right">
                <div class="text-xs font-bold text-red-600 dark:text-red-400 tabular-nums">
                  {{ cnSummary?.leader ? formatPercent(cnSummary.leader.change_pct) : '--' }}
                </div>
              </div>
            </div>
            <div class="flex items-center justify-between gap-2 rounded-xl bg-emerald-500/5 dark:bg-emerald-500/10 px-3 py-2 border border-emerald-500/10">
              <div class="flex items-center gap-2">
                <span class="text-[10px] uppercase tracking-wider text-emerald-600 dark:text-emerald-400">领跌</span>
                <span class="text-sm font-bold text-main">{{ cnSummary?.laggard?.ticker || '--' }}</span>
              </div>
              <div class="text-right">
                <div class="text-xs font-bold text-emerald-600 dark:text-emerald-400 tabular-nums">
                  {{ cnSummary?.laggard ? formatPercent(cnSummary.laggard.change_pct) : '--' }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </article>

      <!-- HK Market Card -->
      <article class="relative overflow-hidden rounded-3xl bg-white dark:bg-zinc-800 border border-zinc-200/70 dark:border-zinc-700/80">
        <!-- SVG Trend Background -->
        <div class="absolute inset-0 pointer-events-none opacity-30">
          <svg class="w-full h-full" viewBox="0 0 400 200" preserveAspectRatio="none" aria-hidden="true">
            <defs>
              <linearGradient :id="`hk-trend-gradient-${hkTrendId}`" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" :stop-color="hkTrendColor" stop-opacity="0.4"/>
                <stop offset="100%" :stop-color="hkTrendColor" stop-opacity="0"/>
              </linearGradient>
            </defs>
            <path :d="hkTrendPath.area" :fill="`url(#hk-trend-gradient-${hkTrendId})`" />
            <path :d="hkTrendPath.line" fill="none" :stroke="hkTrendColor" stroke-width="1.5" opacity="0.6"/>
          </svg>
        </div>

        <div class="relative p-5 sm:p-6">
          <!-- Card Header -->
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                <span class="text-2xl leading-none">🇭🇰</span>
              </div>
              <div>
                <h2 class="text-xl font-bold text-main tracking-tight">港股市场</h2>
                <div class="mt-2">
                  <MarketDataTimestamp :timestamp="overviewData.updated_at" />
                </div>
              </div>
            </div>
            <NuxtLink
              to="/market-detail/hk"
              class="inline-flex items-center justify-center rounded-xl bg-overlay-2 px-4 py-2 text-sm font-medium text-main transition hover:-translate-y-0.5"
            >
              进入港股看盘 →
            </NuxtLink>
          </div>

          <!-- Stats Row -->
          <div class="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div class="text-center sm:text-left">
              <div class="text-[10px] uppercase tracking-widest text-tertiary">股票数</div>
              <div class="mt-1 text-lg font-bold text-main tabular-nums">{{ hkSummary?.stock_count || 0 }}</div>
            </div>
            <div class="text-center sm:text-left">
              <div class="text-[10px] uppercase tracking-widest text-tertiary">上涨</div>
              <div class="mt-1 text-lg font-bold text-emerald-600 dark:text-emerald-400 tabular-nums">{{ hkSummary?.up_count || 0 }}</div>
            </div>
            <div class="text-center sm:text-left">
              <div class="text-[10px] uppercase tracking-widest text-tertiary">下跌</div>
              <div class="mt-1 text-lg font-bold text-red-600 dark:text-red-400 tabular-nums">{{ hkSummary?.down_count || 0 }}</div>
            </div>
            <div class="text-center sm:text-left">
              <div class="text-[10px] uppercase tracking-widest text-tertiary">平盘</div>
              <div class="mt-1 text-lg font-bold text-main tabular-nums">{{ hkSummary?.flat_count || 0 }}</div>
            </div>
          </div>

          <!-- Indices Row -->
          <div class="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
            <div
              v-for="index in hkIndices"
              :key="index.symbol"
              class="min-w-0 flex items-center justify-between gap-2 rounded-lg border border-white/45 bg-white/20 px-3 py-2 shadow-sm backdrop-blur-xl dark:border-zinc-600/55 dark:bg-zinc-900/25"
            >
              <span class="truncate text-xs text-tertiary">{{ index.shortLabel }}</span>
              <span class="text-sm font-bold text-main tabular-nums whitespace-nowrap">{{ index.value }}</span>
              <span class="text-xs font-bold tabular-nums" :class="cc.textClass(index.changePct)">
                {{ formatPercent(index.changePct) }}
              </span>
            </div>
          </div>

          <!-- Leader/Laggard -->
          <div class="mt-4 grid grid-cols-2 gap-3">
            <div class="flex items-center justify-between gap-2 rounded-xl bg-emerald-500/5 dark:bg-emerald-500/10 px-3 py-2 border border-emerald-500/10">
              <div class="flex items-center gap-2">
                <span class="text-[10px] uppercase tracking-wider text-emerald-600 dark:text-emerald-400">领涨</span>
                <span class="text-sm font-bold text-main">{{ hkSummary?.leader?.ticker || '--' }}</span>
              </div>
              <div class="text-right">
                <div class="text-xs font-bold text-emerald-600 dark:text-emerald-400 tabular-nums">
                  {{ hkSummary?.leader ? formatPercent(hkSummary.leader.change_pct) : '--' }}
                </div>
              </div>
            </div>
            <div class="flex items-center justify-between gap-2 rounded-xl bg-red-500/5 dark:bg-red-500/10 px-3 py-2 border border-red-500/10">
              <div class="flex items-center gap-2">
                <span class="text-[10px] uppercase tracking-wider text-red-600 dark:text-red-400">领跌</span>
                <span class="text-sm font-bold text-main">{{ hkSummary?.laggard?.ticker || '--' }}</span>
              </div>
              <div class="text-right">
                <div class="text-xs font-bold text-red-600 dark:text-red-400 tabular-nums">
                  {{ hkSummary?.laggard ? formatPercent(hkSummary.laggard.change_pct) : '--' }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </article>
    </section>

    <!-- Stock List Section -->
    <section class="card mt-6 bg-overlay overflow-hidden">
      <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div class="text-[11px] uppercase tracking-[0.2em] text-tertiary">市场看盘</div>
          <h2 class="mt-2 text-2xl font-bold text-main tracking-tight">盘口与交易热度</h2>
          <div class="mt-2">
            <MarketDataTimestamp :timestamp="overviewData.updated_at" />
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2 text-xs text-tertiary">
          <span>当前市场共 {{ sortedBoardItems.length }} 只股票</span>
          <span v-if="panelMode === 'activity'">热门列表 {{ filteredHotActivityItems.length }} 只</span>
        </div>
      </div>

      <div class="mt-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div class="flex flex-wrap items-center gap-3">
          <div class="flex items-center gap-[6px] rounded-xl bg-overlay-2 p-[6px] w-fit">
            <button
              v-for="option in marketOptions"
              :key="option.value"
              type="button"
              class="px-3 py-1 rounded-lg text-sm transition-all select-none"
              :class="selectedMarket === option.value ? 'bg-blue-600 text-white font-medium' : 'text-zinc-400 hover:text-main'"
              @click="selectedMarket = option.value"
            >
              {{ option.label }}
            </button>
          </div>
          <div class="flex items-center gap-[6px] rounded-xl bg-overlay-2 p-[6px] w-fit">
            <button
              v-for="option in panelOptions"
              :key="option.value"
              type="button"
              class="px-3 py-1 rounded-lg text-sm transition-all select-none"
              :class="panelMode === option.value ? 'bg-blue-600 text-white font-medium' : 'text-zinc-400 hover:text-main'"
              @click="panelMode = option.value"
            >
              {{ option.label }}
            </button>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <NuxtLink
            :to="`/market-detail/${selectedMarket}`"
            class="rounded-xl bg-overlay-2 px-3 py-2 text-xs font-medium text-secondary transition hover:text-main"
          >
            打开完整看盘
          </NuxtLink>
          <button
            type="button"
            class="rounded-xl bg-overlay-2 px-3 py-2 text-xs font-medium text-secondary transition hover:text-main"
            @click="toggleSort"
          >
            {{ sortButtonLabel }}
          </button>
        </div>
      </div>

      <!-- Loading State -->
      <div v-if="isLoading" class="mt-5 space-y-2">
        <div v-for="n in 8" :key="n" class="rounded-2xl bg-overlay-2/60 px-4 py-3 animate-pulse">
          <div class="flex items-center justify-between gap-4">
            <div class="space-y-2">
              <div class="h-3 w-16 rounded bg-zinc-200 dark:bg-zinc-700"></div>
              <div class="h-2.5 w-24 rounded bg-zinc-200 dark:bg-zinc-700"></div>
            </div>
            <div class="space-y-2 text-right">
              <div class="h-3 w-16 rounded bg-zinc-200 dark:bg-zinc-700 ml-auto"></div>
              <div class="h-2.5 w-12 rounded bg-zinc-200 dark:bg-zinc-700 ml-auto"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Stock List -->
      <div
        v-else
        class="mt-5 pr-1 divide-y divide-zinc-200 dark:divide-zinc-700"
      >
        <template v-if="panelMode === 'movers'">
          <div v-for="(item, index) in paginatedBoardItems" :key="`${selectedMarket}-${item.ticker}`" class="flex items-center gap-4 py-3">
            <div class="w-7 text-center text-xs font-bold flex-shrink-0" :class="(moversPage - 1) * ITEMS_PER_PAGE + index < 3 ? 'text-amber-500' : 'text-tertiary'">
              {{ (moversPage - 1) * ITEMS_PER_PAGE + index + 1 }}
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="font-mono text-main font-bold text-sm">{{ item.ticker }}</span>
                <span class="h-1.5 w-1.5 rounded-full" :class="item.market_status === 'open' ? 'bg-emerald-500' : 'bg-zinc-300 dark:bg-zinc-600'"></span>
              </div>
              <div class="truncate text-[10px] text-tertiary">{{ item.name }}</div>
            </div>
            <div class="hidden sm:block flex-shrink-0">
              <MarketTrendSparkline :seed="item.ticker" :change="item.change_pct" />
            </div>
            <div class="text-right flex-shrink-0">
              <div class="text-sm font-bold text-main tabular-nums">{{ formatPrice(item.price, selectedMarket) }}</div>
              <div class="text-xs font-bold tabular-nums" :class="cc.textClass(item.change_pct)">
                {{ formatPercent(item.change_pct) }}
              </div>
            </div>
          </div>

          <!-- Pagination for movers -->
          <div v-if="moversTotalPages > 1" class="py-4 flex items-center justify-center gap-2">
            <button
              type="button"
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
              :class="moversPage === 1 ? 'text-zinc-400 cursor-not-allowed' : 'text-main hover:bg-overlay-2'"
              :disabled="moversPage === 1"
              @click="prevMoversPage"
            >
              上一页
            </button>
            <div class="flex items-center gap-1">
              <button
                v-for="page in moversTotalPages"
                :key="page"
                type="button"
                class="min-w-[28px] px-2 py-1.5 rounded-lg text-xs font-medium transition-all"
                :class="moversPage === page ? 'bg-blue-600 text-white' : 'text-secondary hover:bg-overlay-2 hover:text-main'"
                @click="goToMoversPage(page)"
              >
                {{ page }}
              </button>
            </div>
            <button
              type="button"
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
              :class="moversPage === moversTotalPages ? 'text-zinc-400 cursor-not-allowed' : 'text-main hover:bg-overlay-2'"
              :disabled="moversPage === moversTotalPages"
              @click="nextMoversPage"
            >
              下一页
            </button>
          </div>
        </template>

        <template v-else>
          <div v-if="!filteredHotActivityItems.length" class="py-12 text-center text-sm text-tertiary">
            当前还没有足够的 Agent 操作热度数据。
          </div>
          <div v-for="(item, index) in paginatedHotActivityItems" :key="`${selectedMarket}-hot-${item.ticker}`" class="flex items-center gap-4 py-3">
            <div class="w-7 text-center text-xs font-bold flex-shrink-0" :class="(activityPage - 1) * ITEMS_PER_PAGE + index < 3 ? 'text-amber-500' : 'text-tertiary'">
              {{ (activityPage - 1) * ITEMS_PER_PAGE + index + 1 }}
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="font-mono text-main font-bold text-sm">{{ item.ticker }}</span>
                <span class="rounded-full bg-overlay-2 px-2 py-0.5 text-[10px] text-tertiary">{{ item.tradeCount }} 笔</span>
              </div>
              <div class="truncate text-[10px] text-tertiary mt-1">{{ item.name }}</div>
              <div class="truncate text-[10px] text-secondary mt-1">
                {{ item.agentSampleLabel }}
              </div>
            </div>
            <div class="text-right flex-shrink-0">
              <div class="text-sm font-bold text-main tabular-nums">{{ formatPrice(item.lastPrice, selectedMarket) }}</div>
              <div class="text-xs text-secondary tabular-nums mt-1">买入 {{ item.buyCount }} / 卖出 {{ item.sellCount }}</div>
              <div class="text-xs font-bold tabular-nums mt-1" :class="cc.textClass(item.changePct)">
                {{ formatPercent(item.changePct) }}
              </div>
            </div>
          </div>

          <!-- Pagination for activity -->
          <div v-if="activityTotalPages > 1 && filteredHotActivityItems.length > 0" class="py-4 flex items-center justify-center gap-2">
            <button
              type="button"
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
              :class="activityPage === 1 ? 'text-zinc-400 cursor-not-allowed' : 'text-main hover:bg-overlay-2'"
              :disabled="activityPage === 1"
              @click="prevActivityPage"
            >
              上一页
            </button>
            <div class="flex items-center gap-1">
              <button
                v-for="page in activityTotalPages"
                :key="page"
                type="button"
                class="min-w-[28px] px-2 py-1.5 rounded-lg text-xs font-medium transition-all"
                :class="activityPage === page ? 'bg-blue-600 text-white' : 'text-secondary hover:bg-overlay-2 hover:text-main'"
                @click="goToActivityPage(page)"
              >
                {{ page }}
              </button>
            </div>
            <button
              type="button"
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
              :class="activityPage === activityTotalPages ? 'text-zinc-400 cursor-not-allowed' : 'text-main hover:bg-overlay-2'"
              :disabled="activityPage === activityTotalPages"
              @click="nextActivityPage"
            >
              下一页
            </button>
          </div>
        </template>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, shallowRef, onMounted, onBeforeUnmount, watch } from 'vue'
import MarketDataTimestamp from '~/components/market/MarketDataTimestamp.vue'
import MarketTrendSparkline from '~/components/market/MarketTrendSparkline.vue'

useHead({ title: '市场总览 - CocoLoop Agent 理财竞赛' })

const cc = useColorConvention()

type MarketKey = 'us' | 'cn' | 'hk'
type PanelMode = 'movers' | 'activity'
type SortDirection = 'desc' | 'asc'

interface MarketBoardItem {
  ticker: string
  name: string
  market: MarketKey
  price: number
  change_pct: number
  volume: number | null
  market_status: string
}

interface MarketSummary {
  market: MarketKey
  name: string
  stock_count: number
  up_count: number
  down_count: number
  flat_count: number
  avg_change_pct: number
  leader?: MarketBoardItem | null
  laggard?: MarketBoardItem | null
}

interface IndexQuote {
  symbol: string
  name: string
  price: number
  change_pct: number
  market: MarketKey
}

interface MarketOverviewResponse {
  indices: IndexQuote[]
  boards: Record<MarketKey, MarketBoardItem[]>
  markets: MarketSummary[]
  updated_at?: string
}

interface MarketTrendPoint {
  ts: number
  close: number
}

interface MarketTrendResponse {
  market: MarketKey
  symbol: string
  name: string
  points: MarketTrendPoint[]
  updated_at?: string
}

interface FeedItem {
  id: number
  agent_id: string
  agent_name: string
  agent_avatar: string
  action: 'buy' | 'sell'
  ticker: string
  amount: number
  created_at: string
}

interface HotActivityItem {
  ticker: string
  name: string
  tradeCount: number
  buyCount: number
  sellCount: number
  amountTotal: number
  lastPrice: number
  changePct: number
  agentSampleLabel: string
}

const REFRESH_INTERVAL_MS = 60000
const FEED_LIMIT = 120

const marketOptions = [
  { label: '美股', value: 'us' },
  { label: 'A 股', value: 'cn' },
  { label: '港股', value: 'hk' },
] as const

const panelOptions = [
  { label: '盘口强弱', value: 'movers' },
  { label: 'Agent 热门操作', value: 'activity' },
] as const

const INDEX_META: Record<string, { shortLabel: string }> = {
  SPX: { shortLabel: '标普 500' },
  NDX: { shortLabel: '纳指' },
  DJI: { shortLabel: '道指' },
  SH: { shortLabel: '上证' },
  SZ: { shortLabel: '深成指' },
  CY: { shortLabel: '创业板' },
  HSI: { shortLabel: '恒生指数' },
  HSCEI: { shortLabel: '恒生国企' },
}

// State
const selectedMarket = shallowRef<MarketKey>('us')
const panelMode = shallowRef<PanelMode>('movers')
const sortDirection = shallowRef<SortDirection>('desc')
const isLoading = ref(false)
const hasLoadedFeed = shallowRef(false)
const isPageVisible = shallowRef(true)

// Pagination state
const ITEMS_PER_PAGE = 15
const moversPage = ref(1)
const activityPage = ref(1)

// Reset page when mode changes
watch(panelMode, () => {
  moversPage.value = 1
  activityPage.value = 1
})

watch(selectedMarket, () => {
  moversPage.value = 1
  activityPage.value = 1
})

// Data
const overviewData = ref<MarketOverviewResponse>({
  indices: [],
  boards: { us: [], cn: [], hk: [] },
  markets: [],
  updated_at: '',
})
const trendSeries = ref<Record<MarketKey, MarketTrendPoint[]>>({
  us: [],
  cn: [],
  hk: [],
})
const feedItems = ref<FeedItem[]>([])

// Client-side data fetching
async function fetchOverview() {
  try {
    const response = await fetch('/api/market/overview')
    if (!response.ok) throw new Error('Failed to fetch overview')
    const data = await response.json()
    overviewData.value = data
  } catch (error) {
    console.error('Error fetching overview:', error)
  }
}

async function fetchTrend(market: MarketKey) {
  try {
    const response = await fetch(`/api/market/trend?market=${market}&points=40`)
    if (!response.ok) throw new Error(`Failed to fetch trend for ${market}`)
    const data = await response.json() as MarketTrendResponse
    trendSeries.value[market] = Array.isArray(data.points) ? data.points : []
  } catch (error) {
    console.error(`Error fetching trend for ${market}:`, error)
  }
}

async function fetchAllTrends() {
  await Promise.all([
    fetchTrend('us'),
    fetchTrend('cn'),
    fetchTrend('hk'),
  ])
}

async function fetchFeed() {
  if (panelMode.value !== 'activity') return
  try {
    const response = await fetch(`/api/feed?limit=${FEED_LIMIT}`)
    if (!response.ok) throw new Error('Failed to fetch feed')
    const data = await response.json()
    feedItems.value = data
    hasLoadedFeed.value = true
  } catch (error) {
    console.error('Error fetching feed:', error)
  }
}

async function fetchAll() {
  isLoading.value = true
  const tasks = [fetchOverview(), fetchAllTrends()]
  if (panelMode.value === 'activity') {
    tasks.push(fetchFeed())
  }
  await Promise.all(tasks)
  isLoading.value = false
}

// Auto refresh
let refreshTimer: number | null = null
let removeVisibilityListener: (() => void) | null = null
onMounted(() => {
  isPageVisible.value = !document.hidden
  const handleVisibilityChange = () => {
    isPageVisible.value = !document.hidden
    if (!isPageVisible.value) return
    void fetchOverview()
    void fetchAllTrends()
    if (panelMode.value === 'activity') {
      void fetchFeed()
    }
  }
  document.addEventListener('visibilitychange', handleVisibilityChange)
  removeVisibilityListener = () => document.removeEventListener('visibilitychange', handleVisibilityChange)

  void fetchOverview()
  void fetchAllTrends()
  if (panelMode.value === 'activity') {
    void fetchFeed()
  }

  refreshTimer = window.setInterval(() => {
    if (!isPageVisible.value) return
    void fetchOverview()
    void fetchAllTrends()
    if (panelMode.value === 'activity') {
      void fetchFeed()
    }
  }, REFRESH_INTERVAL_MS)
})

onBeforeUnmount(() => {
  removeVisibilityListener?.()
  removeVisibilityListener = null
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
})

watch(panelMode, (mode) => {
  if (mode === 'activity' && !hasLoadedFeed.value) {
    void fetchFeed()
  }
})

// Computed data
const usSummary = computed(() => overviewData.value.markets?.find(m => m.market === 'us'))
const cnSummary = computed(() => overviewData.value.markets?.find(m => m.market === 'cn'))
const hkSummary = computed(() => overviewData.value.markets?.find(m => m.market === 'hk'))

const usIndices = computed(() => {
  return (overviewData.value.indices || [])
    .filter(item => item.market === 'us')
    .map(item => ({
      symbol: item.symbol,
      shortLabel: INDEX_META[item.symbol]?.shortLabel || item.name,
      value: formatPrice(item.price, 'us', { minimumFractionDigits: 0, maximumFractionDigits: 2 }),
      changePct: item.change_pct,
    }))
})

const cnIndices = computed(() => {
  return (overviewData.value.indices || [])
    .filter(item => item.market === 'cn')
    .map(item => ({
      symbol: item.symbol,
      shortLabel: INDEX_META[item.symbol]?.shortLabel || item.name,
      value: formatPrice(item.price, 'cn', { minimumFractionDigits: 0, maximumFractionDigits: 2 }),
      changePct: item.change_pct,
    }))
})

const hkIndices = computed(() => {
  return (overviewData.value.indices || [])
    .filter(item => item.market === 'hk')
    .map(item => ({
      symbol: item.symbol,
      shortLabel: INDEX_META[item.symbol]?.shortLabel || item.name,
      value: formatPrice(item.price, 'hk', { minimumFractionDigits: 0, maximumFractionDigits: 2 }),
      changePct: item.change_pct,
    }))
})

// Trend paths for SVG backgrounds
const usTrendId = 'us-bg'
const cnTrendId = 'cn-bg'
const hkTrendId = 'hk-bg'

const usTrendColor = computed(() => {
  const trend = getTrendDirection('us')
  return trend >= 0 ? '#10b981' : '#ef4444'
})

const cnTrendColor = computed(() => {
  const trend = getTrendDirection('cn')
  return trend >= 0 ? '#ef4444' : '#10b981'
})

const hkTrendColor = computed(() => {
  const trend = getTrendDirection('hk')
  return trend >= 0 ? '#10b981' : '#ef4444'
})

function getTrendDirection(market: MarketKey) {
  const points = trendSeries.value[market] || []
  if (points.length >= 2) {
    return (points[points.length - 1]?.close || 0) - (points[0]?.close || 0)
  }
  const summaryMap: Record<MarketKey, typeof usSummary.value> = {
    us: usSummary.value,
    cn: cnSummary.value,
    hk: hkSummary.value,
  }
  return summaryMap[market]?.avg_change_pct || 0
}

function buildTrendPathFromSeries(market: MarketKey) {
  const rawSeries = (trendSeries.value[market] || []).map(point => Number(point.close)).filter(v => Number.isFinite(v))
  if (rawSeries.length < 2) {
    return buildTrendPathFallback(market)
  }

  const width = 400
  const height = 200
  const paddingY = 28
  const minValue = Math.min(...rawSeries)
  const maxValue = Math.max(...rawSeries)
  const range = Math.max(maxValue - minValue, 1e-6)

  const values = rawSeries.map((close) => {
    const normalized = (close - minValue) / range
    return height - (paddingY + normalized * (height - paddingY * 2))
  })

  const step = width / (values.length - 1)
  const linePoints = values.map((y, index) => `${(index * step).toFixed(1)},${y.toFixed(1)}`)
  const line = `M${linePoints.join(' L')}`
  const area = `${line} L${width},${height} L0,${height} Z`
  return { line, area }
}

function buildTrendPathFallback(market: MarketKey) {
  const points = 20
  const width = 400
  const height = 200
  const trend = getTrendDirection(market) >= 0 ? 1 : -1

  const values: number[] = []
  let value = height / 2
  for (let i = 0; i < points; i++) {
    const wave = Math.sin(i * 0.5) * 15
    const drift = trend * (i / points) * 40
    value = Math.max(30, Math.min(height - 30, value + wave * 0.3 + drift * 0.1))
    values.push(value)
  }

  const step = width / (points - 1)
  const linePoints = values.map((y, index) => `${(index * step).toFixed(1)},${(height - y).toFixed(1)}`)
  const line = `M${linePoints.join(' L')}`
  const area = `${line} L${width},${height} L0,${height} Z`
  return { line, area }
}

const usTrendPath = computed(() => buildTrendPathFromSeries('us'))
const cnTrendPath = computed(() => buildTrendPathFromSeries('cn'))
const hkTrendPath = computed(() => buildTrendPathFromSeries('hk'))

// Board items
const boardItems = computed(() => overviewData.value.boards?.[selectedMarket.value] || [])
const boardItemMap = computed(() => new Map(boardItems.value.map(item => [item.ticker, item])))
const boardTickerSet = computed(() => new Set(boardItems.value.map(item => item.ticker)))

const sortedBoardItems = computed(() => {
  const direction = sortDirection.value === 'desc' ? -1 : 1
  return [...boardItems.value].sort((a, b) => {
    if (a.change_pct === b.change_pct) {
      return a.ticker.localeCompare(b.ticker)
    }
    return (a.change_pct - b.change_pct) * direction
  })
})

// Hot activity
const hotActivityItems = computed<HotActivityItem[]>(() => {
  const grouped = new Map<string, HotActivityItem & { agentNames: Set<string> }>()

  for (const item of feedItems.value) {
    if (!boardTickerSet.value.has(item.ticker)) continue

    const boardItem = boardItemMap.value.get(item.ticker)
    const existing = grouped.get(item.ticker) || {
      ticker: item.ticker,
      name: boardItem?.name || item.ticker,
      tradeCount: 0,
      buyCount: 0,
      sellCount: 0,
      amountTotal: 0,
      lastPrice: Number(boardItem?.price || 0),
      changePct: Number(boardItem?.change_pct || 0),
      agentSampleLabel: '',
      agentNames: new Set<string>(),
    }

    existing.tradeCount += 1
    existing.amountTotal += Number(item.amount || 0)
    existing.lastPrice = Number(boardItem?.price || existing.lastPrice || 0)
    existing.changePct = Number(boardItem?.change_pct || existing.changePct || 0)
    existing.agentNames.add(item.agent_name)
    if (item.action === 'buy') existing.buyCount += 1
    else existing.sellCount += 1

    grouped.set(item.ticker, existing)
  }

  return Array.from(grouped.values()).map((item) => {
    const names = Array.from(item.agentNames)
    return {
      ticker: item.ticker,
      name: item.name,
      tradeCount: item.tradeCount,
      buyCount: item.buyCount,
      sellCount: item.sellCount,
      amountTotal: item.amountTotal,
      lastPrice: item.lastPrice,
      changePct: item.changePct,
      agentSampleLabel: names.length > 2 ? `${names.slice(0, 2).join('、')} 等 ${names.length} 位 Agent` : names.join('、'),
    }
  })
})

const filteredHotActivityItems = computed(() => {
  const direction = sortDirection.value === 'desc' ? -1 : 1
  return [...hotActivityItems.value].sort((a, b) => {
    if (a.tradeCount === b.tradeCount) {
      return (a.amountTotal - b.amountTotal) * direction
    }
    return (a.tradeCount - b.tradeCount) * direction
  })
})

// Paginated items
const paginatedBoardItems = computed(() => {
  const start = (moversPage.value - 1) * ITEMS_PER_PAGE
  const end = start + ITEMS_PER_PAGE
  return sortedBoardItems.value.slice(start, end)
})

const paginatedHotActivityItems = computed(() => {
  const start = (activityPage.value - 1) * ITEMS_PER_PAGE
  const end = start + ITEMS_PER_PAGE
  return filteredHotActivityItems.value.slice(start, end)
})

// Pagination metadata
const moversTotalPages = computed(() => Math.ceil(sortedBoardItems.value.length / ITEMS_PER_PAGE))
const activityTotalPages = computed(() => Math.ceil(filteredHotActivityItems.value.length / ITEMS_PER_PAGE))

// Pagination actions
function goToMoversPage(page: number) {
  if (page >= 1 && page <= moversTotalPages.value) {
    moversPage.value = page
  }
}

function goToActivityPage(page: number) {
  if (page >= 1 && page <= activityTotalPages.value) {
    activityPage.value = page
  }
}

function prevMoversPage() {
  if (moversPage.value > 1) {
    moversPage.value--
  }
}

function nextMoversPage() {
  if (moversPage.value < moversTotalPages.value) {
    moversPage.value++
  }
}

function prevActivityPage() {
  if (activityPage.value > 1) {
    activityPage.value--
  }
}

function nextActivityPage() {
  if (activityPage.value < activityTotalPages.value) {
    activityPage.value++
  }
}

// Labels
const updatedAtLabel = computed(() => {
  if (!overviewData.value.updated_at) return '加载中'
  const date = new Date(overviewData.value.updated_at)
  if (Number.isNaN(date.getTime())) return '缓存中'
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
})

const sortButtonLabel = computed(() => {
  if (panelMode.value === 'activity') {
    return sortDirection.value === 'desc' ? '热度优先' : '冷门优先'
  }
  return sortDirection.value === 'desc' ? '涨幅优先' : '跌幅优先'
})

// Actions
async function manualRefresh() {
  await fetchAll()
}

function toggleSort() {
  sortDirection.value = sortDirection.value === 'desc' ? 'asc' : 'desc'
}

function formatPercent(value: number) {
  const numeric = Number(value || 0)
  return `${numeric >= 0 ? '+' : ''}${numeric.toFixed(2)}%`
}

function formatPrice(
  value: number,
  market: MarketKey,
  options: Intl.NumberFormatOptions = { minimumFractionDigits: 2, maximumFractionDigits: 2 },
) {
  const currency = market === 'us' ? '$' : market === 'hk' ? 'HK$' : '¥'
  return `${currency}${Number(value || 0).toLocaleString('en-US', options)}`
}
</script>
