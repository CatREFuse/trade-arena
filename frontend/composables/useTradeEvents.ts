interface TradeEvent {
  type: string
  agent_id?: string
  action?: string
  ticker?: string
  shares?: string
  price?: string
  amount?: string
  reasoning?: string
  timestamp?: string
  [key: string]: any
}

export function useTradeEvents() {
  const events = ref<TradeEvent[]>([])
  const connected = ref(false)

  let source: EventSource | null = null

  function connect() {
    if (typeof window === 'undefined') return
    source = new EventSource('/api/sse/events')
    source.onopen = () => { connected.value = true }
    source.addEventListener('trade', (e: MessageEvent) => {
      const trade = JSON.parse(e.data)
      events.value.unshift(trade)
      if (events.value.length > 100) events.value.pop()
    })
    source.addEventListener('ranking', (e: MessageEvent) => {
      // ranking updates handled by polling
    })
    source.onerror = () => {
      connected.value = false
      source?.close()
      setTimeout(connect, 3000)
    }
  }

  onMounted(connect)
  onUnmounted(() => { source?.close() })

  return { events, connected }
}
