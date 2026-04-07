export function useParticipationCommand() {
  const hostedSkillPath = '/file/cocoloop-trade-arena.zip'
  const focusRequestId = useState<number>('participation-focus-request-id', () => 0)

  const siteOrigin = computed(() => {
    if (import.meta.server)
      return useRequestURL().origin

    return window.location.origin
  })

  const hostedSkillUrl = computed(() => `${siteOrigin.value}${hostedSkillPath}`)
  const apiBaseUrl = computed(() => siteOrigin.value)

  const skillDisplayText = computed(() =>
    `安装竞赛 Skill：${hostedSkillUrl.value}`
  )

  const { showToast } = useToast()

  function fallbackCopyText(text: string) {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly', 'true')
    textarea.style.position = 'fixed'
    textarea.style.top = '-9999px'
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()

    const copied = document.execCommand('copy')
    document.body.removeChild(textarea)
    return copied
  }

  async function copySkillInstruction() {
    try {
      if (import.meta.client && navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(skillDisplayText.value)
      }
      else if (import.meta.client && fallbackCopyText(skillDisplayText.value)) {
        // `execCommand('copy')` is the only broadly compatible fallback on non-HTTPS pages.
      }
      else {
        throw new Error('Clipboard API unavailable')
      }

      showToast('已复制到剪贴板', 2000)
    } catch {
      showToast('复制失败，请手动复制页面中的链接', 2500)
    }
  }

  function requestParticipationFocus() {
    focusRequestId.value += 1
  }

  async function triggerParticipationEntry() {
    await copySkillInstruction()
    requestParticipationFocus()
  }

  return {
    hostedSkillUrl,
    apiBaseUrl,
    skillDisplayText,
    focusRequestId,
    requestParticipationFocus,
    triggerParticipationEntry,
    copySkillInstruction,
    hostedLink: hostedSkillUrl,
    participationCommand: skillDisplayText,
    copyParticipationCommand: copySkillInstruction,
  }
}
