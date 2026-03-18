<template>
  <div class="min-h-screen flex flex-col">
    <!-- 导航栏 -->
    <nav class="sticky top-0 z-50 bg-white/80 backdrop-blur-md">
      <div class="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
        <NuxtLink to="/" class="text-lg font-extrabold text-zinc-800 flex items-center gap-2 hover:opacity-80 transition">
          AI 炒股竞技场
        </NuxtLink>
        <div class="flex items-center gap-1">
          <NuxtLink v-for="link in navLinks" :key="link.to" :to="link.to"
            class="px-3 py-1.5 rounded-xl text-sm font-semibold transition-all duration-200"
            :class="$route.path === link.to
              ? 'text-zinc-800'
              : 'text-zinc-400 hover:text-zinc-800'">
            {{ link.label }}
          </NuxtLink>
          <div class="ml-3 flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full" :class="sseConnected ? 'bg-emerald-500 animate-pulse' : 'bg-zinc-300'"></span>
            <span class="text-[10px] font-medium" :class="sseConnected ? 'text-emerald-600' : 'text-zinc-400'">
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

    <!-- 底部 -->
    <footer class="px-6 py-6 text-center text-xs text-zinc-400">
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
