<template>
  <svg class="w-[64px] h-[24px]" viewBox="0 0 64 24" preserveAspectRatio="none" aria-hidden="true">
    <defs>
      <filter :id="`spark-glow-${safeId}`" x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur in="SourceGraphic" stdDeviation="1.8" result="blur" />
        <feMerge>
          <feMergeNode in="blur" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </defs>
    <path :d="shape.area" :fill="cc.hex(change)" opacity="0.10" />
    <path
      :d="shape.line"
      fill="none"
      :stroke="cc.hex(change)"
      stroke-width="1.5"
      stroke-linecap="round"
      stroke-linejoin="round"
      opacity="0.55"
      :filter="`url(#spark-glow-${safeId})`"
    />
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  seed: string
  change: number
}>()

const cc = useColorConvention()

function hashSeed(value: string) {
  let hash = 0
  for (let i = 0; i < value.length; i++) {
    hash = ((hash << 5) - hash + value.charCodeAt(i)) | 0
  }
  return Math.abs(hash)
}

function buildShape(seed: string, change: number) {
  const points = 16
  const values: number[] = []
  const seedValue = hashSeed(seed)
  let value = 12 + (seedValue % 5)
  const trend = change >= 0 ? 1 : -1

  for (let i = 0; i < points; i++) {
    const wave = Math.sin(seedValue * 0.011 + i * 0.65) * 1.8
    const drift = trend * (i / Math.max(points - 1, 1)) * Math.min(6, Math.abs(change) * 0.9 + 1.8)
    value = Math.max(2, Math.min(22, value + wave * 0.35 + drift * 0.35))
    values.push(value)
  }

  const step = 64 / Math.max(points - 1, 1)
  const linePoints = values.map((y, index) => `${(index * step).toFixed(1)},${(24 - y).toFixed(1)}`)
  const line = `M${linePoints.join(' L')}`
  const area = `${line} L64,24 L0,24 Z`
  return { line, area }
}

const shape = computed(() => buildShape(props.seed, props.change))
const safeId = computed(() => props.seed.replace(/[^a-zA-Z0-9_-]/g, ''))
</script>
