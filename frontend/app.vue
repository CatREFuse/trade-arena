<template>
  <div class="min-h-screen flex flex-col bg-base">
    <!-- Toast - Inline Status Style (No popups) -->
    <div class="fixed top-4 left-1/2 -translate-x-1/2 z-[100] flex flex-col gap-2 pointer-events-none">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="pointer-events-auto px-4 py-2 bg-surface border border-border-visible"
        >
          <span class="font-mono text-caption text-primary">[{{ toast.message }}]</span>
        </div>
      </TransitionGroup>
    </div>

    <!-- Navigation - Nothing Design Style -->
    <nav class="sticky top-0 z-50 bg-base border-b border-border">
      <div class="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <!-- Logo / Brand -->
        <NuxtLink to="/" class="flex items-center gap-3 group">
          <span class="font-display text-2xl tracking-tight text-display">CocoLoop</span>
          <span class="hidden sm:block label">TRADE ARENA</span>
        </NuxtLink>

        <!-- Nav Links - Fixed Width, Bracket Style -->
        <div class="flex items-center">
          <NuxtLink
            v-for="link in navLinks"
            :key="link.to"
            :to="link.to"
            class="font-mono text-sm tracking-wider uppercase py-2 transition-colors text-center min-w-[72px]"
            :class="$route.path === link.to ? 'text-display' : 'text-disabled hover:text-secondary'"
          >
            <span class="text-secondary opacity-0" :class="{ 'opacity-100': $route.path === link.to }">[</span>
            {{ link.label }}
            <span class="text-secondary opacity-0" :class="{ 'opacity-100': $route.path === link.to }">]</span>
          </NuxtLink>

          <!-- Theme Toggle -->
          <button
            @click="toggle"
            class="ml-4 w-10 h-10 flex items-center justify-center text-disabled hover:text-secondary transition-colors"
            :title="isDark ? 'Switch to Light' : 'Switch to Dark'"
          >
            <svg v-if="isDark" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
              <circle cx="12" cy="12" r="4"/>
              <path d="M12 2v2m0 16v2m9-9h-2M5 12H3m14.071-7.071l-1.414 1.414M6.343 17.657l-1.414 1.414m14.142 0l-1.414-1.414M6.343 6.343L4.929 4.929"/>
            </svg>
            <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
              <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
            </svg>
          </button>

          <!-- Color Convention Toggle -->
          <button
            @click="toggleColor"
            class="w-10 h-10 flex items-center justify-center text-disabled hover:text-secondary transition-colors"
            :title="isCN ? 'Red Up Green Down (CN)' : 'Green Up Red Down (US)'"
          >
            <span class="font-mono text-xs">{{ isCN ? 'CN' : 'US' }}</span>
          </button>

          <!-- Live Indicator -->
          <div class="ml-4 flex items-center gap-2">
            <span class="w-1.5 h-1.5 rounded-full" :class="sseConnected ? 'bg-success' : 'text-disabled bg-current'">
              <span v-if="sseConnected" class="animate-pulse"></span>
            </span>
            <span class="font-mono text-caption" :class="sseConnected ? 'text-success' : 'text-disabled'">
              {{ sseConnected ? 'LIVE' : 'OFF' }}
            </span>
          </div>

          <!-- CTA Button -->
          <button
            type="button"
            @click="handleJoinNow"
            class="btn-primary ml-6"
          >
            JOIN NOW
          </button>
        </div>
      </div>
    </nav>

    <main class="flex-1">
      <NuxtPage />
    </main>

    <!-- Footer - Minimal -->
    <footer class="px-6 py-8 border-t border-border">
      <div class="max-w-6xl mx-auto flex items-center justify-between">
        <span class="font-mono text-caption text-disabled">
          本站纯属娱乐，不构成任何投资建议
        </span>
        <span class="font-mono text-caption text-disabled">
          COCOLOOP 2024
        </span>
      </div>
    </footer>
  </div>
</template>

<script setup>
const navLinks = [
  { to: '/', label: 'HOME' },
  { to: '/leaderboard', label: 'RANK' },
  { to: '/market', label: 'MARKET' },
  { to: '/about', label: 'ABOUT' },
]

const route = useRoute()
const { connected: sseConnected } = useTradeEvents()
const { isDark, toggle } = useAppearance()
const { isCN, toggle: toggleColor } = useColorConvention()
const { toasts } = useToastState()

async function handleJoinNow() {
  if (route.path !== '/') {
    await navigateTo('/')
  }
}
</script>

<style>
.toast-enter-active,
.toast-leave-active {
  transition: opacity 200ms ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
}
</style>
