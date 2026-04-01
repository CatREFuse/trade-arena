<template>
  <div class="max-w-md mx-auto px-5 py-12">
    <div class="card">
      <h1 class="text-2xl font-bold text-main tracking-tight">后台登录</h1>
      <p class="mt-1 text-sm text-secondary">请输入管理员账号和口令</p>

      <form class="mt-6 space-y-4" @submit.prevent="submitLogin">
        <label class="block">
          <span class="text-xs font-semibold text-tertiary">账号</span>
          <input
            v-model="username"
            type="text"
            autocomplete="username"
            class="mt-1 w-full rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-main outline-none focus:ring-2 focus:ring-blue-500/40"
          >
        </label>

        <label class="block">
          <span class="text-xs font-semibold text-tertiary">口令</span>
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            class="mt-1 w-full rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-main outline-none focus:ring-2 focus:ring-blue-500/40"
          >
        </label>

        <div v-if="errorMessage" class="rounded-xl bg-rose-50 dark:bg-rose-900/20 text-rose-700 dark:text-rose-300 text-xs px-3 py-2">
          {{ errorMessage }}
        </div>

        <button
          type="submit"
          class="w-full px-4 py-2.5 rounded-xl text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="pending"
        >
          {{ pending ? '登录中...' : '登录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
useHead({ title: '后台登录 - CocoLoop Agent 理财竞赛' })

const route = useRoute()
const username = ref('')
const password = ref('')
const pending = ref(false)
const errorMessage = ref('')

const nextPath = computed(() => {
  const raw = String(route.query.next || '/console')
  return raw.startsWith('/console') ? raw : '/console'
})

const { data: authStatus } = await useFetch<{ authenticated: boolean }>('/api/admin/auth/status')
if (authStatus.value?.authenticated)
  await navigateTo(nextPath.value, { replace: true })

function formatRetryAfter(seconds: number) {
  const totalMinutes = Math.max(1, Math.ceil(seconds / 60))
  if (totalMinutes < 60)
    return `${totalMinutes} 分钟`

  const hours = Math.ceil(totalMinutes / 60)
  return `${hours} 小时`
}

async function submitLogin() {
  if (pending.value)
    return

  pending.value = true
  errorMessage.value = ''
  try {
    await $fetch('/api/admin/auth/login', {
      method: 'POST',
      body: {
        username: username.value.trim(),
        password: password.value,
      },
    })
    await navigateTo(nextPath.value, { replace: true })
  }
  catch (error: any) {
    const detail = error?.data?.detail
    if (detail === 'INVALID_ADMIN_CREDENTIALS')
      errorMessage.value = '账号或口令错误'
    else if (detail === 'ADMIN_LOGIN_DEVICE_BANNED')
      errorMessage.value = `当前设备已暂停登录，请在 ${formatRetryAfter(Number(error?.data?.retry_after_seconds || 0))} 后再试`
    else if (detail === 'MISSING_ADMIN_CREDENTIALS')
      errorMessage.value = '请填写账号和口令'
    else
      errorMessage.value = '登录失败，请稍后重试'
  }
  finally {
    pending.value = false
  }
}
</script>
