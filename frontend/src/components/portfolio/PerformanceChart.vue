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
import type { HoldingDailyOHLC, PerformanceRange } from '@/stores/portfolio'

ChartJS.register(TimeScale, LinearScale, LineElement, PointElement, Tooltip, Filler)

const RANGES: PerformanceRange[] = ['1D', '1W', '1M']

const props = withDefaults(
  defineProps<{
    points: { as_of: string; value_cents: number }[]
    ohlcPoints?: HoldingDailyOHLC[]
    /** Whether 1W/1M should render the four-line open/close/top/bottom view. Portfolio
     * charts never set this because there's no per-portfolio backfill to derive it from. */
    supportsOhlc?: boolean
    loading?: boolean
    error?: string | null
    label?: string
  }>(),
  {
    ohlcPoints: () => [],
    supportsOhlc: false,
    loading: false,
    error: null,
    label: 'Value',
  },
)

const emit = defineEmits<{ 'range-change': [range: PerformanceRange] }>()

const selectedRange = ref<PerformanceRange>('1M')

const isOhlcView = computed(() => props.supportsOhlc && selectedRange.value !== '1D')
const hasData = computed(() =>
  isOhlcView.value ? props.ohlcPoints.length > 0 : props.points.length > 0,
)

// "Not enough data yet" threshold: ceil(range / 4) days of actual data span -- 1W needs >=2
// days, 1M needs >=7 (anchored to 28, the shortest calendar month, not our 30-day fetch
// window). 1D is exempt. See the product spec's "Chart range behavior" section. Applies to
// both chart types: a newly-tracked portfolio (no backfill exists for portfolio history) and
// a holding whose backfill failed with too little live history accumulated since.
const RANGE_DAYS: Record<PerformanceRange, number> = { '1D': 1, '1W': 7, '1M': 28 }

const actualDataSpanDays = computed(() => {
  if (isOhlcView.value) {
    // Each ohlcPoints entry is already one distinct calendar day of aggregated data.
    return props.ohlcPoints.length
  }
  const distinctDates = new Set(props.points.map((point) => new Date(point.as_of).toISOString().slice(0, 10)))
  return distinctDates.size
})

const hasEnoughData = computed(() => {
  if (selectedRange.value === '1D') return true
  return actualDataSpanDays.value >= Math.ceil(RANGE_DAYS[selectedRange.value] / 4)
})

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

// Date-only strings (from the daily-OHLC endpoint) parse as UTC midnight in JS, which can
// display as the previous day once localized to a viewer west of UTC. Anchoring to local
// noon keeps the displayed calendar date correct regardless of viewer timezone.
function dailyPointToMillis(dateString: string): number {
  return new Date(`${dateString}T12:00:00`).getTime()
}

const singleLineData = computed(() => ({
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

const ohlcLineData = computed(() => {
  function series(field: 'open_cents' | 'close_cents' | 'high_cents' | 'low_cents') {
    return props.ohlcPoints.map((point) => {
      const value = point[field]
      return {
        x: dailyPointToMillis(point.date),
        y: value === null ? null : value / 100,
      }
    })
  }

  return {
    datasets: [
      {
        label: 'Close',
        data: series('close_cents'),
        borderColor: '#0f766e',
        backgroundColor: 'rgba(15, 118, 110, 0.15)',
        fill: false,
        tension: 0.2,
        pointRadius: 0,
        borderWidth: 2,
        // Today has no close_cents until the market closes -- render that as a visible
        // gap rather than bridging it to yesterday's close.
        spanGaps: false,
      },
      {
        label: 'Open',
        data: series('open_cents'),
        borderColor: '#5a6e69',
        backgroundColor: 'transparent',
        fill: false,
        tension: 0.2,
        pointRadius: 0,
        borderWidth: 1.5,
      },
      {
        label: 'Top',
        data: series('high_cents'),
        borderColor: '#5eead4',
        backgroundColor: 'transparent',
        borderDash: [4, 3],
        fill: false,
        tension: 0.2,
        pointRadius: 0,
        borderWidth: 1.5,
      },
      {
        label: 'Bottom',
        data: series('low_cents'),
        borderColor: '#134e4a',
        backgroundColor: 'transparent',
        borderDash: [4, 3],
        fill: false,
        tension: 0.2,
        pointRadius: 0,
        borderWidth: 1.5,
      },
    ],
  }
})

const chartData = computed(() => (isOhlcView.value ? ohlcLineData.value : singleLineData.value))

// Tooltip format follows the selected range: exact time when viewing a single
// day, calendar date once points span multiple days.
const chartOptions = computed<ChartOptions<'line'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { intersect: false, mode: 'index' },
  plugins: {
    legend: { display: isOhlcView.value },
    tooltip: {
      callbacks: {
        label: (context) => {
          const formatted = new Intl.NumberFormat(undefined, {
            style: 'currency',
            currency: 'USD',
          }).format(typeof context.parsed.y === 'number' ? context.parsed.y : 0)
          return `${context.dataset.label}: ${formatted}`
        },
      },
    },
  },
  scales: {
    x: {
      type: 'time',
      time: {
        tooltipFormat: selectedRange.value === '1D' ? 'h:mm a' : 'MMM d, yyyy',
        // 1W/1M must never render hourly ticks, regardless of how sparse the underlying
        // data is -- a chart covering only a few real hours would otherwise auto-pick an
        // hourly axis and look like a broken 1D chart. Forced to 'day' on both chart types.
        unit: selectedRange.value === '1D' ? undefined : 'day',
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
        v-else-if="!hasData"
        class="flex h-full items-center justify-center text-sm text-ink-muted"
      >
        No price history yet for this range.
      </p>
      <p
        v-else-if="!hasEnoughData"
        class="flex h-full items-center justify-center text-sm text-ink-muted"
      >
        Not enough price history yet for this range.
      </p>
      <Line v-else :data="chartData" :options="chartOptions" />
    </div>
    <p v-if="isOhlcView && !loading && !error" class="mt-2 text-xs text-accent/70 italic">
      Values derived from available price samples for each day. Top/bottom/close/open are not exact records*
    </p>
  </div>
</template>
