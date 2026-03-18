type Appearance = 'light' | 'dark' | 'auto'

export function useAppearance() {
  const preference = useState<Appearance>('appearance', () => 'auto')
  const isDark = useState<boolean>('isDark', () => false)

  function applyTheme() {
    if (typeof document === 'undefined') return
    const shouldBeDark =
      preference.value === 'dark' ||
      (preference.value === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches)
    isDark.value = shouldBeDark
    document.documentElement.classList.toggle('dark', shouldBeDark)
  }

  function toggle() {
    // auto -> light -> dark -> auto
    if (preference.value === 'auto') {
      preference.value = isDark.value ? 'light' : 'dark'
    } else if (preference.value === 'light') {
      preference.value = 'dark'
    } else {
      preference.value = 'light'
    }
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('appearance', preference.value)
    }
    applyTheme()
  }

  onMounted(() => {
    const saved = localStorage.getItem('appearance') as Appearance | null
    if (saved) preference.value = saved
    applyTheme()
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyTheme)
  })

  return { preference, isDark, toggle }
}
