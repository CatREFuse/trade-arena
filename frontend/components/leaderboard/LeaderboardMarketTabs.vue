<template>
  <div class="flex items-center gap-[6px] p-[6px] bg-overlay-2 rounded-xl w-fit">
    <button
      v-for="market in props.markets"
      :key="market.value"
      type="button"
      @click="emit('update:modelValue', market.value)"
      :class="props.modelValue === market.value
        ? 'bg-blue-600 text-white font-medium'
        : 'text-zinc-400 hover:text-main'"
      class="px-3 py-1 rounded-lg text-sm transition-all select-none"
    >
      {{ market.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
interface MarketOption {
  label: string
  value: string
}

const props = defineProps<{
  modelValue: string
  markets: MarketOption[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>
