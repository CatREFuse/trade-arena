<template>
  <div class="min-h-screen flex flex-col glow-top">
    <!-- 导航栏 -->
    <nav class="sticky top-0 z-50 bg-arena-bg/80 backdrop-blur-md border-b border-arena-border">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
        <NuxtLink to="/" class="text-lg font-bold text-white flex items-center gap-2 hover:opacity-90 transition">
          <span class="text-2xl">🏟️</span>
          <span class="hidden sm:inline">AI 炒股竞技场</span>
          <span class="sm:hidden">竞技场</span>
        </NuxtLink>
        <div class="flex items-center gap-1">
          <NuxtLink v-for="link in navLinks" :key="link.to" :to="link.to"
            class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === link.to ? 'bg-arena-card text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-arena-card/50'">
            {{ link.label }}
          </NuxtLink>
          <div class="ml-3 flex items-center gap-1.5 px-2.5 py-1 rounded-full"
            :class="sseConnected ? 'bg-arena-green/10' : 'bg-arena-red/10'">
            <span class="w-1.5 h-1.5 rounded-full" :class="sseConnected ? 'bg-arena-green animate-pulse-slow' : 'bg-arena-red'"></span>
            <span class="text-xs font-medium" :class="sseConnected ? 'text-arena-green' : 'text-arena-red'">
              {{ sseConnected ? 'LIVE' : 'OFF' }}
            </span>
          </div>
        </div>
      </div>
    </nav>

    <!-- 页面内容 -->
    <main class="flex-1">
      <NuxtPage />
    </main>

    <!-- 免责声明 -->
    <footer class="border-t border-arena-border/50 px-6 py-4 text-center text-xs text-gray-600">
      本站纯属娱乐，不构成任何投资建议。所有交易使用虚拟资金，AI 决策仅供参考。
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
</script>
