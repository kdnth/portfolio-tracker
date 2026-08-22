<script setup lang="ts">
import { computed, onUnmounted, ref, watch, type ComponentPublicInstance } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import AnalysisModal from '@/components/portfolio/AnalysisModal.vue'
import PerformanceChart from '@/components/portfolio/PerformanceChart.vue'
import RecordTradeModal from '@/components/portfolio/RecordTradeModal.vue'
import AppAlert from '@/components/ui/AppAlert.vue'
import AppButton from '@/components/ui/AppButton.vue'
import {
  usePortfolioStore,
  isFlatPricePoint,
  isHoldingDailyOHLC,
  type Holding,
  type PerformanceRange,
} from '@/stores/portfolio'
import { getApiErrorMessage } from '@/utils/apiError'
import {
  formatCents,
  formatPercent,
  formatSignedCents,
  holdingCostBasisCents,
  holdingMarketValueCents,
  unrealizedGainCents,
  unrealizedGainPercent,
} from '@/utils/money'

const route = useRoute()
const portfolioStore = usePortfolioStore()

const loadError = ref('')
const loading = ref(true)
const tradeOpen = ref(false)
const analysisOpen = ref(false)
const expandedHoldingIds = ref<Set<number>>(new Set())
const portfolioPerformanceError = ref('')
const holdingPerformanceErrors = ref<Record<number, string>>({})

type PerformanceChartInstance = InstanceType<typeof PerformanceChart>
const portfolioChartRef = ref<PerformanceChartInstance | null>(null)
const holdingChartRefs: Record<number, PerformanceChartInstance | null> = {}

function setHoldingChartRef(holdingId: number, el: Element | ComponentPublicInstance | null) {
  holdingChartRefs[holdingId] = el as PerformanceChartInstance | null
}

const portfolioId = computed(() => Number(route.params.portfolioId))

const totalMarketValueCents = computed(() =>
  portfolioStore.currentHoldings.reduce(
    (sum, holding) => sum + holdingMarketValueCents(holding.shares, holding.current_price_cents),
    0,
  ),
)

const totalCostBasisCents = computed(() =>
  portfolioStore.currentHoldings.reduce(
    (sum, holding) => sum + holdingCostBasisCents(holding.shares, holding.avg_cost_basis_cents),
    0,
  ),
)

const totalGainCents = computed(() =>
  unrealizedGainCents(totalMarketValueCents.value, totalCostBasisCents.value),
)

const totalGainPercent = computed(() =>
  unrealizedGainPercent(totalGainCents.value, totalCostBasisCents.value),
)

// null (quota not loaded yet, or unlimited for an admin) never blocks the button --
// only an explicit 0 does.
const analysesRemaining = computed(() => portfolioStore.analysisQuota?.remaining ?? null)
const analysisExhausted = computed(() => analysesRemaining.value === 0)

function holdingGainCents(holding: Holding) {
  return unrealizedGainCents(
    holdingMarketValueCents(holding.shares, holding.current_price_cents),
    holdingCostBasisCents(holding.shares, holding.avg_cost_basis_cents),
  )
}

function holdingGainPercent(holding: Holding) {
  return unrealizedGainPercent(
    holdingGainCents(holding),
    holdingCostBasisCents(holding.shares, holding.avg_cost_basis_cents),
  )
}

const portfolioChartPoints = computed(() =>
  portfolioStore.portfolioPerformance.map((point) => ({
    as_of: point.as_of,
    value_cents: point.total_market_value_cents,
  })),
)

async function loadPortfolioPerformance(range: PerformanceRange = '1M') {
  if (!Number.isFinite(portfolioId.value)) return
  portfolioPerformanceError.value = ''
  try {
    await portfolioStore.fetchPortfolioPerformance(portfolioId.value, range)
  } catch (error) {
    portfolioPerformanceError.value = getApiErrorMessage(error, 'Unable to load performance.')
  }
}

async function loadHoldingPerformance(holdingId: number, range: PerformanceRange = '1M') {
  if (!Number.isFinite(portfolioId.value)) return
  holdingPerformanceErrors.value = { ...holdingPerformanceErrors.value, [holdingId]: '' }
  try {
    await portfolioStore.fetchHoldingPerformance(portfolioId.value, holdingId, range)
  } catch (error) {
    holdingPerformanceErrors.value = {
      ...holdingPerformanceErrors.value,
      [holdingId]: getApiErrorMessage(error, 'Unable to load performance.'),
    }
  }
}

function holdingFlatPoints(holdingId: number) {
  return (portfolioStore.holdingPerformance[holdingId] ?? [])
    .filter(isFlatPricePoint)
    .map((point) => ({ as_of: point.as_of, value_cents: point.price_cents }))
}

function holdingOhlcPoints(holdingId: number) {
  return (portfolioStore.holdingPerformance[holdingId] ?? []).filter(isHoldingDailyOHLC)
}

function onTradeRecorded() {
  // Trades can change portfolio value immediately, and can trigger a server-side
  // historical backfill for a brand-new ticker -- neither is reflected in chart
  // data already sitting in the store, so both charts need an explicit refresh.
  // .refresh() re-fetches at whichever range each chart already has selected.
  portfolioChartRef.value?.refresh()
  for (const holdingId of expandedHoldingIds.value) {
    holdingChartRefs[holdingId]?.refresh()
  }
}

function toggleHoldingExpanded(holdingId: number) {
  const next = new Set(expandedHoldingIds.value)
  if (next.has(holdingId)) {
    next.delete(holdingId)
  } else {
    next.add(holdingId)
    if (!portfolioStore.holdingPerformance[holdingId]) {
      loadHoldingPerformance(holdingId)
    }
  }
  expandedHoldingIds.value = next
}

async function load() {
  if (!Number.isFinite(portfolioId.value)) {
    loadError.value = 'Invalid portfolio id.'
    loading.value = false
    return
  }

  loading.value = true
  loadError.value = ''
  expandedHoldingIds.value = new Set()
  portfolioPerformanceError.value = ''
  holdingPerformanceErrors.value = {}
  // Fire-and-forget: if this fails, the Analyze button just falls back to its default
  // enabled state rather than blocking the whole page on a non-critical fetch.
  portfolioStore.fetchAnalysisQuota().catch(() => {})

  try {
    await Promise.all([
      portfolioStore.fetchPortfolio(portfolioId.value),
      portfolioStore.fetchHoldings(portfolioId.value),
    ])
    loadPortfolioPerformance()
  } catch (error) {
    loadError.value = getApiErrorMessage(error, 'Unable to load portfolio.')
    portfolioStore.clearCurrent()
  } finally {
    loading.value = false
  }
}

watch(portfolioId, load, { immediate: true })

onUnmounted(() => {
  portfolioStore.clearCurrent()
})
</script>

<template>
  <div>
    <RouterLink
      :to="{ name: 'portfolios' }"
      class="text-sm font-medium text-accent hover:text-accent-hover"
    >
      ← Back to portfolios
    </RouterLink>

    <AppAlert v-if="loadError" class="mt-6">{{ loadError }}</AppAlert>

    <template v-else-if="loading">
      <p class="mt-10 text-sm text-ink-muted">Loading portfolio…</p>
    </template>

    <template v-else-if="portfolioStore.currentPortfolio">
      <div class="mt-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 class="text-3xl font-bold tracking-tight text-ink">
            {{ portfolioStore.currentPortfolio.name }}
          </h1>
          <p class="mt-1 text-sm text-ink-muted">
            Market value
            <span class="font-semibold text-ink">{{ formatCents(totalMarketValueCents) }}</span>
            <span
              v-if="totalCostBasisCents > 0"
              class="ml-2 font-medium"
              :class="totalGainCents >= 0 ? 'text-accent' : 'text-danger'"
            >
              {{ formatSignedCents(totalGainCents) }} ({{ formatPercent(totalGainPercent) }})
            </span>
          </p>
        </div>

        <div class="flex flex-col items-end gap-1">
          <div class="flex gap-2">
            <AppButton
              variant="secondary"
              :disabled="analysisExhausted"
              @click="analysisOpen = true"
            >
              Analyze portfolio
              <svg
                  class="size-6 shrink-0"
                  viewBox="0 0 194 231"
                  fill="none"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    d="M6 79.5C44 60 46.4872 40.309 51.5 -0.5C56.6293 40.0239 63.5 59.5 96.5 79.5C67.1412 88.5941 56.716 103.835 51.5 153.5C47.0666 102.795 35.7376 88.8311 6 79.5Z"
                    stroke-width="9"
                  />
                  <path
                    d="M91 143C129 123.5 131.487 103.809 136.5 63C141.629 103.524 148.5 123 181.5 143C152.141 152.094 141.716 167.335 136.5 217C132.067 166.295 120.738 152.331 91 143Z"
                    stroke-width="10"
                  />
                </svg>
            </AppButton>
            <AppButton @click="tradeOpen = true">Record trade</AppButton>
          </div>
          <p v-if="analysisExhausted" class="text-xs text-ink-muted">
            Daily analysis limit reached. Resets at midnight UTC.
          </p>
          <p v-else-if="analysesRemaining !== null" class="text-xs text-ink-muted">
            {{ analysesRemaining }} analys{{ analysesRemaining === 1 ? 'is' : 'es' }} left today
          </p>
        </div>
      </div>

      <div class="mt-6 rounded-2xl border border-border bg-surface p-5">
        <h2 class="text-sm font-semibold text-ink-muted">Performance</h2>
        <PerformanceChart
          ref="portfolioChartRef"
          class="mt-2"
          :points="portfolioChartPoints"
          :loading="portfolioStore.portfolioPerformanceLoading"
          :error="portfolioPerformanceError || null"
          label="Portfolio value"
          @range-change="loadPortfolioPerformance"
        />
      </div>

      <div
        v-if="portfolioStore.currentHoldings.length === 0"
        class="mt-10 rounded-2xl border border-dashed border-border bg-surface px-6 py-12 text-center"
      >
        <h2 class="text-lg font-semibold text-ink">No holdings yet</h2>
        <p class="mt-2 text-sm text-ink-muted">
          Record a buy to open your first position in this portfolio.
        </p>
        <div class="mt-6 flex justify-center">
          <AppButton @click="tradeOpen = true">Record trade</AppButton>
        </div>
      </div>

      <div
        v-else
        class="mt-8 overflow-x-auto rounded-2xl border border-border bg-surface"
      >
        <table class="min-w-full text-left text-sm">
          <thead class="border-b border-border bg-canvas/60 text-ink-muted">
            <tr>
              <th class="px-5 py-3 font-medium">Ticker</th>
              <th class="px-5 py-3 font-medium">Shares</th>
              <th class="px-5 py-3 font-medium">Avg cost</th>
              <th class="px-5 py-3 font-medium">Price</th>
              <th class="px-5 py-3 font-medium">Market value</th>
              <th class="px-5 py-3 font-medium">Unrealized P&amp;L</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <template v-for="holding in portfolioStore.currentHoldings" :key="holding.id">
              <tr class="text-ink">
                <td class="px-5 py-3.5 font-semibold">
                  <button
                    type="button"
                    class="inline-flex items-center gap-1.5 hover:text-accent"
                    :aria-expanded="expandedHoldingIds.has(holding.id)"
                    :aria-controls="`holding-performance-${holding.id}`"
                    @click="toggleHoldingExpanded(holding.id)"
                  >
                    <svg
                      class="size-3.5 shrink-0 text-ink-muted transition-transform"
                      :class="{ 'rotate-90': expandedHoldingIds.has(holding.id) }"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      aria-hidden="true"
                    >
                      <path
                        fill-rule="evenodd"
                        d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                        clip-rule="evenodd"
                      />
                    </svg>
                    {{ holding.ticker }}
                  </button>
                </td>
                <td class="px-5 py-3.5 tabular-nums">{{ holding.shares }}</td>
                <td class="px-5 py-3.5 tabular-nums">
                  {{ formatCents(holding.avg_cost_basis_cents) }}
                </td>
                <td class="px-5 py-3.5 tabular-nums">
                  {{ formatCents(holding.current_price_cents) }}
                </td>
                <td class="px-5 py-3.5 tabular-nums font-medium">
                  {{
                    formatCents(
                      holdingMarketValueCents(holding.shares, holding.current_price_cents),
                    )
                  }}
                </td>
                <td
                  class="px-5 py-3.5 tabular-nums font-medium"
                  :class="holdingGainCents(holding) >= 0 ? 'text-accent' : 'text-danger'"
                >
                  {{ formatSignedCents(holdingGainCents(holding)) }}
                  <span class="text-xs font-normal opacity-80">
                    ({{ formatPercent(holdingGainPercent(holding)) }})
                  </span>
                </td>
              </tr>
              <tr v-if="expandedHoldingIds.has(holding.id)" :id="`holding-performance-${holding.id}`">
                <td colspan="6" class="bg-canvas/40 px-5 py-4">
                  <PerformanceChart
                    :ref="(el) => setHoldingChartRef(holding.id, el)"
                    :points="holdingFlatPoints(holding.id)"
                    :ohlc-points="holdingOhlcPoints(holding.id)"
                    :supports-ohlc="true"
                    :loading="!!portfolioStore.holdingPerformanceLoading[holding.id]"
                    :error="holdingPerformanceErrors[holding.id] || null"
                    :label="`${holding.ticker} price`"
                    @range-change="(range) => loadHoldingPerformance(holding.id, range)"
                  />
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <RecordTradeModal
        :open="tradeOpen"
        :portfolio-id="portfolioId"
        @close="tradeOpen = false"
        @saved="onTradeRecorded"
      />

      <AnalysisModal
        :open="analysisOpen"
        :portfolio-id="portfolioId"
        @close="analysisOpen = false"
      />
    </template>
  </div>
</template>
