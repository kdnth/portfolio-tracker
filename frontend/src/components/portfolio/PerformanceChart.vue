<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  Chart as ChartJS,
  Filler,
  LinearScale,
  LineElement,
  PointElement,
  TimeScale,
  Tooltip,
  type ChartOptions,
} from 'chart.js'
import 'chartjs-adapter-date-fns'
import { Line } from 'vue-chartjs'

import AppAlert from '@/components/ui/AppAlert.vue'
import type { PerformanceRange } from '@/stores/portfolio'

ChartJS.register(TimeScale, LinearScale, LineElement, PointElement, Tooltip, Filler)

const RANGES: PerformanceRange[] = ['1D', '1W', '1M']

const props = withDefaults(
  defineProps<{
    points: { as_of: string; value_cents: number }[]
    loading?: boolean
    error?: string | null
    label?: string
  }>(),
  {
    loading: false,
    error: null,
    label: 'Value',
  },
)

const emit = defineEmits<{ 'range-change': [range: PerformanceRange] }>()

const selectedRange = ref<PerformanceRange>('1M')

function selectRange(range: PerformanceRange) {
  // Re-emits even for the already-selected range so a range button doubles as
  // a retry action when the last fetch for it failed.
  selectedRange.value = range
  emit('range-change', range)
}

/** Re-fetches at whichever range is currently selected, without changing it --
 * for a parent to call after something outside this component (e.g. a new trade)
 * changes the underlying data. Refetching at a hardcoded default instead would
 * desync the highlighted range button from what's actually displayed. */
function refresh() {
  emit('range-change', selectedRange.value)
}

defineExpose({ refresh })

const chartData = computed(() => ({
  datasets: [
    {
      label: props.label,
      data: props.points.map((point) => ({
        x: new Date(point.as_of).getTime(),
        y: point.value_cents / 100,
      })),
      borderColor: '#0f766e',
      backgroundColor: 'rgba(15, 118, 110, 0.15)',
      fill: true,
      tension: 0.3,
      pointRadius: 0,
      borderWidth: 2,
    },
  ],
}))

// Tooltip format follows the selected range: exact time when viewing a single
// day, calendar date once points span multiple days.
const chartOptions = computed<ChartOptions<'line'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { intersect: false, mode: 'index' },
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (context) =>
          new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD' }).format(
            typeof context.parsed.y === 'number' ? context.parsed.y : 0,
          ),
      },
    },
  },
  scales: {
    x: {
      type: 'time',
      time: {
        tooltipFormat: selectedRange.value === '1D' ? 'h:mm a' : 'MMM d, yyyy',
      },
      // No vertical gridlines across the plot area (keeps it uncluttered), but keep the
      // small tick marks at each label so the axis reads as a real scale, not just text.
      grid: { drawOnChartArea: false, drawTicks: true },
    },
    y: {
      grid: { drawTicks: true },
      ticks: { callback: (value) => `$${value}` },
    },
  },
}))
</script>

<template>
  <div>
    <div class="flex items-center justify-end gap-1">
      <button
        v-for="range in RANGES"
        :key="range"
        type="button"
        class="rounded-md px-2.5 py-1 text-xs font-semibold transition"
        :class="
          range === selectedRange
            ? 'bg-accent text-white'
            : 'text-ink-muted hover:bg-canvas hover:text-ink'
        "
        @click="selectRange(range)"
      >
        {{ range }}
      </button>
    </div>

    <div class="mt-3 h-56">
      <p v-if="loading" class="flex h-full items-center justify-center text-sm text-ink-muted">
        Loading…
      </p>
      <div v-else-if="error" class="flex h-full items-center">
        <AppAlert class="w-full">{{ error }}</AppAlert>
      </div>
      <p
        v-else-if="points.length === 0"
        class="flex h-full items-center justify-center text-sm text-ink-muted"
      >
        No price history yet for this range.
      </p>
      <Line v-else :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>
