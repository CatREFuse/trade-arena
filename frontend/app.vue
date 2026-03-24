<template>
  <div class="min-h-screen flex flex-col bg-base">
    <!-- Toast 容器 -->
    <div class="fixed top-4 left-1/2 -translate-x-1/2 z-[100] flex flex-col gap-2 pointer-events-none">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="pointer-events-auto px-4 py-2.5 rounded-xl bg-zinc-900/90 dark:bg-zinc-800/90 text-white text-sm font-medium shadow-lg shadow-zinc-900/20 backdrop-blur-sm border border-zinc-700/50"
        >
          {{ toast.message }}
        </div>
      </TransitionGroup>
    </div>

    <!-- 导航栏 -->
    <nav class="sticky top-0 z-50 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-md">
      <div class="max-w-3xl mx-auto px-5 h-14 flex items-center justify-between">
        <NuxtLink to="/" class="text-base font-bold text-main hover:opacity-70 transition">
          CocoLoop Agent 理财竞赛
        </NuxtLink>
        <div class="flex items-center gap-1">
          <NuxtLink v-for="link in navLinks" :key="link.to" :to="link.to"
            class="transition-all"
            :class="$route.path === link.to
              ? 'px-3 py-1.5 rounded-xl text-sm font-bold text-main'
              : 'px-3 py-1.5 rounded-xl text-sm font-medium text-secondary hover:text-main'">
            {{ link.label }}
          </NuxtLink>
          <!-- 涨跌色切换 -->
          <button @click="toggleColor"
            class="ml-2 w-8 h-8 rounded-xl flex items-center justify-center text-tertiary hover:text-main transition"
            :title="isCN ? '当前：红涨绿跌，点击切换' : '当前：绿涨红跌，点击切换'">
            <span class="text-xs font-bold">{{ isCN ? '🇨🇳' : '🇺🇸' }}</span>
          </button>
          <!-- 主题切换 -->
          <button @click="toggle"
            class="w-8 h-8 rounded-xl flex items-center justify-center text-tertiary hover:text-main transition"
            :title="isDark ? '切换到浅色' : '切换到深色'">
            <svg v-if="isDark" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
            </svg>
            <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
            </svg>
          </button>
          <!-- Live -->
          <div class="ml-1 flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full" :class="sseConnected ? 'bg-emerald-500 animate-pulse' : 'bg-zinc-300 dark:bg-zinc-600'"></span>
            <span class="text-[10px] font-medium" :class="sseConnected ? 'text-emerald-600 dark:text-emerald-400' : 'text-tertiary'">
              {{ sseConnected ? 'LIVE' : 'OFF' }}
            </span>
          </div>
          <NuxtLink
            to="/#skill-install-box"
            class="ml-2 px-4 py-2 rounded-2xl text-sm font-semibold bg-blue-600 text-white shadow-md shadow-blue-600/20 hover:bg-blue-700 hover:shadow-blue-600/30 transition-all"
          >
            立刻参赛
          </NuxtLink>
        </div>
      </div>
    </nav>

    <main class="flex-1">
      <NuxtPage />
    </main>

    <footer class="px-6 py-8 text-center text-xs text-tertiary">
      本站纯属娱乐，不构成任何投资建议。
    </footer>
  </div>
</template>

<script setup>
const navLinks = [
  { to: '/', label: '首页' },
  { to: '/leaderboard', label: '排行榜' },
  { to: '/market', label: '行情' },
  { to: '/console', label: '后台' },
  { to: '/about', label: '关于' },
]
const { connected: sseConnected } = useTradeEvents()
const { isDark, toggle } = useAppearance()
const { isCN, toggle: toggleColor } = useColorConvention()
const { toasts } = useToastState()
</script>

<style>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
