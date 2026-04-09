// 涨跌颜色约定：全站固定为红涨绿跌
export function useColorConvention() {
  const convention = computed(() => 'fixed-red-up-green-down')
  const isCN = computed(() => true)

  // 文本色
  const upText = computed(() => 'text-accent')
  const downText = computed(() => 'text-success')

  // SVG 色值
  const upHex = computed(() => '#ef4444')
  const downHex = computed(() => '#10b981')

  // 背景色（用于 badge）
  const upBg = computed(() => 'bg-red-700 text-white')
  const downBg = computed(() => 'bg-emerald-700 text-white')

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

  return { convention, isCN, upText, downText, upHex, downHex, upBg, downBg, textClass, hex, actionBg }
}
