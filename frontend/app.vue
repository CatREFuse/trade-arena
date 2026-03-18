<template>
  <div class="min-h-screen flex flex-col">
    <!-- 导航栏 -->
    <nav class="bg-arena-card border-b border-arena-border px-6 py-3 flex items-center justify-between">
      <NuxtLink to="/" class="text-xl font-bold text-white flex items-center gap-2">
        <span>🏟️</span> AI 炒股竞技场
      </NuxtLink>
      <div class="flex items-center gap-6">
        <NuxtLink to="/" class="text-gray-300 hover:text-white transition">排行榜</NuxtLink>
        <NuxtLink to="/market" class="text-gray-300 hover:text-white transition">行情</NuxtLink>
        <NuxtLink to="/about" class="text-gray-300 hover:text-white transition">关于</NuxtLink>
        <div class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full" :class="sseConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'"></span>
          <span class="text-xs text-gray-400">{{ sseConnected ? 'Live' : 'Offline' }}</span>
        </div>
      </div>
    </nav>

    <!-- 页面内容 -->
    <main class="flex-1">
      <NuxtPage />
    </main>

    <!-- 免责声明 -->
    <footer class="bg-arena-card border-t border-arena-border px-6 py-3 text-center text-xs text-gray-500">
      免责声明：本站纯属娱乐，不构成任何投资建议。所有交易使用虚拟资金，AI 决策仅供参考。
    </footer>
  </div>
</template>

<script setup>
const { connected: sseConnected } = useTradeEvents()
</script>
