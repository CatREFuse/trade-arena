// 涨跌颜色约定：cn = 红涨绿跌（中国大陆），us = 绿涨红跌（欧美）
export function useColorConvention() {
  const convention = useState<'cn' | 'us'>('colorConvention', () => 'cn')

  if (import.meta.client) {
    const saved = localStorage.getItem('colorConvention')
    if (saved === 'cn' || saved === 'us') convention.value = saved
  }

  function toggle() {
    convention.value = convention.value === 'cn' ? 'us' : 'cn'
    if (import.meta.client) localStorage.setItem('colorConvention', convention.value)
  }

  const isCN = computed(() => convention.value === 'cn')

  // 文本色
  const upText = computed(() => isCN.value
    ? 'text-red-600 dark:text-red-400'
    : 'text-emerald-600 dark:text-emerald-400')
  const downText = computed(() => isCN.value
    ? 'text-emerald-600 dark:text-emerald-400'
    : 'text-red-600 dark:text-red-400')

  // SVG 色值
  const upHex = computed(() => isCN.value ? '#ef4444' : '#10b981')
  const downHex = computed(() => isCN.value ? '#10b981' : '#ef4444')

  // 背景色（用于 badge）
  const upBg = computed(() => isCN.value
    ? 'bg-red-700 text-white'
    : 'bg-emerald-700 text-white')
  const downBg = computed(() => isCN.value
    ? 'bg-emerald-700 text-white'
    : 'bg-red-700 text-white')

  // 根据值返回对应类
  function textClass(value: number) {
    return value >= 0 ? upText.value : downText.value
  }
  function hex(value: number) {
    return value >= 0 ? upHex.value : downHex.value
  }
  function actionBg(action: string) {
    return action === 'buy' ? upBg.value : downBg.value
  }

  return { convention, toggle, isCN, upText, downText, upHex, downHex, upBg, downBg, textClass, hex, actionBg }
}
