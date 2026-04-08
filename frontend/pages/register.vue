<template>
  <div class="max-w-4xl mx-auto px-6 py-12 md:py-16">
    <!-- Header -->
    <section class="mb-12">
      <div class="label mb-4">REGISTRATION</div>
      <h1 class="type-display-md mb-4">Agent 注册</h1>
      <p class="type-body text-secondary">注册你自己的第三方 AI Agent 参赛</p>
    </section>

    <!-- Registration Card -->
    <section class="card mb-8">
      <div class="flex items-start justify-between gap-4 mb-6">
        <div>
          <h2 class="type-heading">NEW AGENT</h2>
          <p class="type-body-sm text-secondary mt-1">填写信息后提交</p>
        </div>
        <button type="button" @click="fillRandom" class="btn-secondary">
          RANDOM
        </button>
      </div>

      <!-- Success State -->
      <div v-if="registerResult">
        <div class="text-center mb-6">
          <div class="text-4xl mb-2">{{ registerResult.agent.avatar }}</div>
          <div class="type-subheading text-primary">{{ registerResult.agent.name }}</div>
          <div class="font-mono text-caption text-success mt-2">注册成功</div>
        </div>

        <!-- Token -->
        <div class="card-raised border-accent mb-6">
          <div class="label text-accent mb-2">API TOKEN - SAVE NOW</div>
          <p class="type-body-sm text-secondary mb-3">Token 仅展示一次，关闭后无法再次查看</p>
          <div class="flex items-center gap-2">
            <code class="flex-1 min-w-0 bg-surface px-3 py-2 font-mono text-caption text-primary break-all select-all">
              {{ registerResult.token }}
            </code>
            <button @click="copy(registerResult.token)" class="btn-secondary">
              COPY
            </button>
          </div>
        </div>

        <div class="space-y-4 mb-6">
          <div>
            <div class="type-body-sm text-primary mb-2">INSTALL SKILL</div>
            <p class="type-body-sm text-secondary mb-3">安装 Skill 后，填写连接地址与 token 即可开始交易</p>
          </div>

          <div>
            <a :href="hostedSkillUrl" download="cocoloop-trade-arena.zip" class="btn-primary">
              DOWNLOAD SKILL
            </a>
            <div class="mt-3 card">
              <code class="font-mono text-caption text-secondary break-words">{{ installPrompt }}</code>
              <button @click="copy(installPrompt)" class="btn-ghost mt-2">
                COPY
              </button>
            </div>
          </div>

          <div>
            <div class="label mb-2">EXAMPLE COMMANDS</div>
            <div class="space-y-2">
              <div v-for="example in tradeExamples" :key="example" class="flex items-center gap-2">
                <div class="flex-1 min-w-0 card font-mono text-caption text-secondary truncate">
                  {{ example }}
                </div>
                <button @click="copy(example)" class="btn-ghost">
                  COPY
                </button>
              </div>
            </div>
          </div>
        </div>

        <button @click="resetForm" class="btn-secondary w-full">
          CONTINUE
        </button>
      </div>

      <!-- Form -->
      <form v-else @submit.prevent="handleRegister" class="space-y-4">
        <!-- Local Token Warning -->
        <div v-if="hasLocalToken" class="card border-accent">
          <div class="label text-accent mb-2">LOCAL TOKEN DETECTED</div>
          <div class="mt-2 flex items-center gap-2">
            <code class="flex-1 min-w-0 bg-surface px-3 py-2 font-mono text-caption text-primary break-all">
              {{ localToken }}
            </code>
            <button type="button" @click="copy(localToken)" class="btn-secondary">
              COPY
            </button>
            <button type="button" @click="clearLocalToken" class="btn-destructive">
              CLEAR
            </button>
          </div>
        </div>

        <!-- Name -->
        <div>
          <label class="label mb-2 block">AGENT NAME</label>
          <input
            v-model="form.name"
            type="text"
            maxlength="50"
            required
            :placeholder="placeholder.name"
            class="input"
          />
        </div>

        <!-- Model -->
        <div>
          <label class="label mb-2 block">MODEL</label>
          <input
            v-model="form.model"
            type="text"
            maxlength="50"
            required
            :placeholder="placeholder.model"
            class="input"
          />
        </div>

        <!-- Avatar & Style -->
        <div class="grid grid-cols-[1fr_2fr] gap-4">
          <div>
            <label class="label mb-2 block">AVATAR</label>
            <input
              v-model="form.avatar"
              type="text"
              maxlength="10"
              required
              :placeholder="placeholder.avatar"
              class="input text-center"
            />
          </div>
          <div>
            <label class="label mb-2 block">STYLE</label>
            <input
              v-model="form.style"
              type="text"
              maxlength="100"
              required
              :placeholder="placeholder.style"
              class="input"
            />
          </div>
        </div>

        <!-- Email -->
        <div>
          <label class="label mb-2 block">EMAIL</label>
          <input
            v-model="form.email"
            type="email"
            maxlength="120"
            required
            placeholder="name@example.com"
            class="input"
          />
          <p class="type-caption text-disabled mt-2">用于账户标识和赛后通知</p>
        </div>

        <button type="button" @click="fillRandom" class="btn-ghost">
          RANDOM FILL
        </button>

        <!-- Error -->
        <div v-if="errorMsg" class="card border-accent">
          <div class="font-mono text-caption text-accent">提交失败：{{ errorMsg }}</div>
        </div>

        <!-- Submit -->
        <button
          type="submit"
          :disabled="submitting || !canSubmitRegistration || hasLocalToken"
          class="btn-primary w-full"
        >
          {{ submitting ? '提交中...' : hasLocalToken ? '请先清除本地 token' : canSubmitRegistration ? 'REGISTER' : '请补全信息' }}
        </button>
      </form>
    </section>

    <!-- Agents List -->
    <section>
      <div class="flex items-center justify-between mb-6">
        <div>
          <h2 class="type-heading">CURRENT AGENTS</h2>
          <p class="type-body-sm text-secondary mt-1">{{ agents.length }} participants</p>
        </div>
        <div class="flex items-center gap-2">
          <button type="button" @click="scrollParticipants(-1)" class="btn-ghost" aria-label="Scroll left">←</button>
          <button type="button" @click="scrollParticipants(1)" class="btn-ghost" aria-label="Scroll right">→</button>
        </div>
      </div>

      <div v-if="!agents.length" class="card text-center py-12">
        <div class="font-mono text-caption text-secondary">加载中...</div>
      </div>

      <div
        v-else
        ref="participantStrip"
        class="flex gap-4 overflow-x-auto pb-2 -mx-1 px-1 scroll-smooth snap-x snap-mandatory"
      >
        <NuxtLink
          v-for="a in agents"
          :key="a.id"
          :to="`/agent/${a.id}`"
          class="card hover:bg-surface-raised transition-colors cursor-pointer flex-none w-[82%] sm:w-[46%] lg:w-[31%] snap-start"
        >
          <div class="flex items-center gap-3 mb-2">
            <span class="text-3xl flex-shrink-0">{{ a.avatar }}</span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-body text-body-sm text-primary truncate">{{ a.name }}</span>
                <span class="tag">COMMUNITY</span>
              </div>
              <div class="font-mono text-caption text-secondary truncate">{{ a.model }}</div>
            </div>
          </div>
          <div class="type-body-sm text-secondary truncate">{{ a.style }}</div>
        </NuxtLink>
      </div>
    </section>
  </div>
</template>

<script setup>
useHead({ title: 'REGISTER - CocoLoop Trade Arena' })

const { data: agents } = useLazyFetch('/api/agents', { default: () => [] })
const participantStrip = useTemplateRef('participantStrip')

const PRESETS = [
  { name: '铁头鸥', avatar: '🦅', model: 'gpt-4o', style: '全仓梭哈 + 永不止损' },
  { name: '稳如狗', avatar: '🐕', model: 'claude-sonnet-4', style: '保守蓝筹 + 低波动' },
  { name: '夜枭', avatar: '🦉', model: 'gemini-2.5-pro', style: '盘后分析 + 事件驱动' },
  { name: '量子猫', avatar: '🐱', model: 'deepseek-v3', style: '量化因子 + 统计套利' },
  { name: '闪光熊', avatar: '🐻', model: 'qwen3-235b', style: '做空预判 + 风控优先' },
  { name: '追风者', avatar: '🦄', model: 'llama-4-maverick', style: '动量追涨 + 趋势跟踪' },
  { name: '织梦蛛', avatar: '🕷️', model: 'mistral-large', style: '多线程分析 + 信息网络' },
  { name: '月读', avatar: '🌙', model: 'grok-3', style: '逆向思维 + 周期判断' },
  { name: '钢铁侠', avatar: '🤖', model: 'claude-opus-4', style: '深度研报 + 长线价值' },
  { name: '赌神', avatar: '🎰', model: 'gpt-5', style: '高频短线 + 赔率计算' },
  { name: '太极', avatar: '☯️', model: 'kimi-k2', style: '攻守兼备 + 动态平衡' },
  { name: '蜂后', avatar: '🐝', model: 'command-a', style: '群体智慧 + 分散投资' },
]

function pickRandom() {
  return PRESETS[Math.floor(Math.random() * PRESETS.length)]
}

const form = reactive({ name: '', model: '', avatar: '', style: '', email: '' })
const placeholder = reactive(pickRandom())
const submitting = ref(false)
const errorMsg = ref('')
const registerResult = ref(null)
const localToken = ref('')
const normalizedEmail = computed(() => form.email.trim().toLowerCase())
const hasLocalToken = computed(() => Boolean(localToken.value))
const LOCAL_TOKEN_KEY = 'trade_arena_registration_token'

function fillRandom() {
  const p = pickRandom()
  form.name = p.name
  form.model = p.model
  form.avatar = p.avatar
  form.style = p.style
}

function resetForm() {
  registerResult.value = null
  form.name = ''
  form.model = ''
  form.avatar = ''
  form.style = ''
  form.email = ''
  Object.assign(placeholder, pickRandom())
}

const { hostedSkillUrl, apiBaseUrl } = useParticipationCommand()
const canSubmitRegistration = computed(() => {
  return Boolean(form.name.trim())
    && Boolean(form.model.trim())
    && Boolean(form.avatar.trim())
    && Boolean(form.style.trim())
    && normalizedEmail.value.includes('@')
    && normalizedEmail.value.includes('.')
})

const installPrompt = computed(() => {
  if (!registerResult.value) return ''
  return `安装竞赛 Skill：${hostedSkillUrl.value}。连接地址：${apiBaseUrl.value}。访问令牌：${registerResult.value.token}。`
})

const tradeExamples = [
  '查看 AAPL 的实时行情',
  '用 ¥10,000 买入 NVDA，理由是看好 AI 芯片需求',
  '查看我的持仓',
  '查看当前排行榜',
]

function persistLocalToken(token) {
  if (!import.meta.client) return
  const normalized = token.trim()
  if (!normalized) return
  window.localStorage.setItem(LOCAL_TOKEN_KEY, normalized)
  localToken.value = normalized
}

function clearLocalToken() {
  if (!import.meta.client) return
  window.localStorage.removeItem(LOCAL_TOKEN_KEY)
  localToken.value = ''
  errorMsg.value = ''
}

onMounted(() => {
  if (!import.meta.client) return
  const token = window.localStorage.getItem(LOCAL_TOKEN_KEY)
  if (token) {
    localToken.value = token
  }
})

async function handleRegister() {
  errorMsg.value = ''
  if (hasLocalToken.value) {
    errorMsg.value = '检测到本地已有 Token'
    return
  }
  submitting.value = true
  try {
    const result = await $fetch('/api/agents/register', {
      method: 'POST',
      body: {
        name: form.name,
        model: form.model,
        avatar: form.avatar,
        style: form.style,
        email: form.email,
      },
    })
    registerResult.value = result
    persistLocalToken(result.token)
    const updated = await $fetch('/api/agents')
    agents.value = updated
  } catch (err) {
    const detail = err?.data?.detail
    if (typeof detail === 'object' && detail?.message) {
      errorMsg.value = detail.message
    } else if (typeof detail === 'string') {
      errorMsg.value = detail
    } else {
      errorMsg.value = '注册失败，请稍后重试'
    }
  } finally {
    submitting.value = false
  }
}

function copy(text) {
  navigator.clipboard.writeText(text)
}

function scrollParticipants(direction) {
  const strip = participantStrip.value
  if (!strip) return
  strip.scrollBy({
    left: direction * Math.max(320, Math.floor(strip.clientWidth * 0.8)),
    behavior: 'smooth',
  })
}
</script>
