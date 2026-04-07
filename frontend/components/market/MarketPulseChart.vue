<template>
  <ClientOnly>
    <VChart :option="chartOption" autoresize class="h-[96px] w-full" />
  </ClientOnly>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { use as useECharts } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { GridComponent } from 'echarts/components'

const VChart = defineAsyncComponent(() => import('vue-echarts'))

useECharts([LineChart, GridComponent, CanvasRenderer])

const props = defineProps<{
  values: number[]
}>()

const normalizedValues = computed(() => {
  if (props.values.length >= 2) {
    return props.values.map(value => Number(value))
  }
  const baseline = Number(props.values[0] ?? 0)
  return Array.from({ length: 24 }, () => baseline)
})

const chartOption = computed(() => {
  return {
    animation: false,
    grid: {
      left: 0,
      right: 0,
      top: 6,
      bottom: 6,
      containLabel: false,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: normalizedValues.value.map((_, index) => String(index)),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: { show: false },
    },
    series: [
      {
        type: 'line',
        smooth: 0.2,
        showSymbol: false,
        data: normalizedValues.value,
        lineStyle: {
          width: 2,
          color: '#2563EB',
        },
        areaStyle: {
          color: 'rgba(37, 99, 235, 0.18)',
        },
      },
    ],
  }
})
</script>
