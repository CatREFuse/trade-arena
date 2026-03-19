export function useParticipationCommand() {
  const siteOrigin = computed(() => {
    if (import.meta.server)
      return useRequestURL().origin

    return window.location.origin
  })

  const apiOrigin = computed(() => {
    const origin = siteOrigin.value
    if (origin.includes('localhost') || origin.includes('127.0.0.1') || origin.includes('::1')) {
      return origin
    }
    try {
      const url = new URL(origin)
      const hostname = url.hostname
      if (hostname.startsWith('api.')) {
        return origin
      }
      const parts = hostname.split('.')
      const rootDomain = parts.length >= 2
        ? parts.slice(-2).join('.')
        : hostname
      return `${url.protocol}//api.${rootDomain}${url.port ? `:${url.port}` : ''}`
    } catch {
      return origin
    }
  })

  const hostedSkillUrl = computed(() => `${apiOrigin.value}/api/agents/skill/hosted`)

  const skillDisplayText = computed(() =>
    `通过 ${hostedSkillUrl.value} 下载 CocoLoop 理财竞赛专用 skill，并通过 skill 进行注册和交易`
  )

  const { showToast } = useToast()

  async function copySkillInstruction() {
    try {
      await navigator.clipboard.writeText(skillDisplayText.value)
      showToast('已复制到剪贴板', 2000)
    } catch {
      showToast('复制失败', 2000)
    }
  }

  return {
    hostedSkillUrl,
    skillDisplayText,
    copySkillInstruction,
    hostedLink: hostedSkillUrl,
    participationCommand: skillDisplayText,
    copyParticipationCommand: copySkillInstruction,
  }
}
