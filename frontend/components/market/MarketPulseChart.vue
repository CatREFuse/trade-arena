<template>
  <div ref="chartEl" class="h-[96px] w-full"></div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { AreaData, IChartApi, ISeriesApi, UTCTimestamp } from 'lightweight-charts'

const props = defineProps<{
  values: number[]
}>()

const chartEl = ref<HTMLElement | null>(null)
let chart: IChartApi | null = null
let series: ISeriesApi<'Area'> | null = null
let resizeObserver: ResizeObserver | null = null

const seriesData = computed<AreaData[]>(() => {
  const source = props.values.length >= 2 ? props.values : [0, 0]
  const min = Math.min(...source)
  const max = Math.max(...source)
  const range = Math.max(max - min, 0.0001)
  const baseTs = Math.floor(Date.now() / 1000) - source.length * 300

  return source.map((value, index) => ({
    time: (baseTs + index * 300) as UTCTimestamp,
    value: Number(((value - min) / range).toFixed(6)),
  }))
})

function applyData() {
  if (!series) return
  series.setData(seriesData.value)
}

async function initChart() {
  if (!chartEl.value || chart) return
  const lightweight = await import('lightweight-charts')
  const initialWidth = Math.max(1, Math.floor(chartEl.value.getBoundingClientRect().width || chartEl.value.clientWidth || 320))
  chart = lightweight.createChart(chartEl.value, {
    width: initialWidth,
    height: 96,
    layout: {
      textColor: '#9CA3AF',
      background: { type: lightweight.ColorType.Solid, color: 'transparent' },
    },
    grid: {
      vertLines: { visible: false },
      horzLines: { color: '#F1F5F9' },
    },
    rightPriceScale: {
      visible: false,
      borderVisible: false,
    },
    leftPriceScale: {
      visible: false,
      borderVisible: false,
    },
    timeScale: {
      visible: false,
      borderVisible: false,
      fixLeftEdge: true,
      fixRightEdge: true,
    },
    crosshair: { mode: lightweight.CrosshairMode.Hidden },
    handleScroll: false,
    handleScale: false,
  })

  series = chart.addAreaSeries({
    lineColor: '#2563EB',
    topColor: 'rgba(37, 99, 235, 0.28)',
    bottomColor: 'rgba(37, 99, 235, 0.02)',
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  })
  applyData()
  chart.timeScale().fitContent()

  resizeObserver = new ResizeObserver((entries) => {
    const width = entries[0]?.contentRect.width
    if (chart && width) {
      chart.applyOptions({ width })
      chart.timeScale().fitContent()
    }
  })
  resizeObserver.observe(chartEl.value)
}

watch(seriesData, () => {
  applyData()
  chart?.timeScale().fitContent()
})

onMounted(() => {
  void initChart()
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  chart?.remove()
  chart = null
  series = null
})
</script>
