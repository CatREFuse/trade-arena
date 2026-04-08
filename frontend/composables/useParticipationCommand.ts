export function useParticipationCommand() {
  const hostedSkillPath = '/file/cocoloop-trade-arena.zip'
  const focusRequestId = useState<number>('participation-focus-request-id', () => 0)
  const runtimeConfig = useRuntimeConfig()

  function normalizeUrl(value: string) {
    return value.replace(/\/+$/, '')
  }

  function normalizeForwardedHeader(value?: string) {
    return (value || '').split(',')[0].trim()
  }

  function isLocalHost(host?: string) {
    const hostname = (host || '').split(':')[0].trim().toLowerCase()
    return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1'
  }

  const siteOrigin = computed(() => {
    const configured = `${runtimeConfig.public.siteUrl || ''}`.trim()
    if (configured)
      return normalizeUrl(configured)

    if (import.meta.server)
    {
      const requestUrl = useRequestURL()
      const headers = useRequestHeaders(['x-forwarded-proto', 'x-forwarded-host', 'host'])
      const forwardedProto = normalizeForwardedHeader(headers['x-forwarded-proto'])
      const forwardedHost = normalizeForwardedHeader(headers['x-forwarded-host'])
      const host = forwardedHost || headers.host || requestUrl.host
      let protocol = forwardedProto || requestUrl.protocol.replace(':', '')

      if (!protocol)
        protocol = 'https'
      if (protocol === 'http' && host && !isLocalHost(host))
        protocol = 'https'

      if (host)
        return `${protocol}://${host}`

      return requestUrl.origin
    }

    return window.location.origin
  })

  const hostedSkillUrl = computed(() => `${siteOrigin.value}${hostedSkillPath}`)
  const apiBaseUrl = computed(() => siteOrigin.value)

  const skillDisplayText = computed(() =>
    `通过 ${hostedSkillUrl.value} 下载并解压 CocoLoop 理财竞赛专用 skill 文件，安装此 skill，完成参赛设置后开始注册和交易`
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
