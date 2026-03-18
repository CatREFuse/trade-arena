<template>
  <div class="min-h-screen flex flex-col bg-base">
    <!-- 导航栏 -->
    <nav class="sticky top-0 z-50 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-md">
      <div class="max-w-3xl mx-auto px-5 h-14 flex items-center justify-between">
        <NuxtLink to="/" class="text-base font-bold text-main hover:opacity-70 transition">
          AI 炒股竞技场
        </NuxtLink>
        <div class="flex items-center gap-1">
          <NuxtLink v-for="link in navLinks" :key="link.to" :to="link.to"
            class="px-3 py-1.5 rounded-xl text-sm font-medium transition-all"
            :class="$route.path === link.to
              ? 'text-main font-bold'
              : 'text-secondary hover:text-main'">
            {{ link.label }}
          </NuxtLink>
          <!-- 主题切换 -->
          <button @click="toggle"
            class="ml-2 w-8 h-8 rounded-xl flex items-center justify-center text-tertiary hover:text-main transition"
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
  { to: '/', label: '排行榜' },
  { to: '/market', label: '行情' },
  { to: '/about', label: '关于' },
]
const { connected: sseConnected } = useTradeEvents()
const { isDark, toggle } = useAppearance()
</script>
