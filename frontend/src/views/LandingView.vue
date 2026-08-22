<script setup lang="ts">
import { computed, onMounted, ref, type ComponentPublicInstance } from 'vue'
import { RouterLink } from 'vue-router'

import logoUrl from '@/assets/logo.png'
import DemoAnalysisModal from '@/components/portfolio/DemoAnalysisModal.vue'
import PerformanceChart from '@/components/portfolio/PerformanceChart.vue'
import AppAlert from '@/components/ui/AppAlert.vue'
import AppButton from '@/components/ui/AppButton.vue'
import { useDemoStore } from '@/stores/demo'
import { isFlatPricePoint, isHoldingDailyOHLC, type Holding, type PerformanceRange } from '@/stores/portfolio'
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

const demoStore = useDemoStore()

const loading = ref(true)
const loadError = ref('')
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

// null (quota not fetched yet -- nothing has happened this session) never blocks the
// button; only an explicit 0 does.
const analysesRemaining = computed(() => demoStore.analysesRemaining)
const analysisExhausted = computed(() => analysesRemaining.value === 0)

const totalMarketValueCents = computed(() =>
  demoStore.holdings.reduce(
    (sum, holding) => sum + holdingMarketValueCents(holding.shares, holding.current_price_cents),
    0,
  ),
)
const totalCostBasisCents = computed(() =>
  demoStore.holdings.reduce(
    (sum, holding) => sum + holdingCostBasisCents(holding.shares, holding.avg_cost_basis_cents),
    0,
  ),
)
const totalGainCents = computed(() => unrealizedGainCents(totalMarketValueCents.value, totalCostBasisCents.value))
const totalGainPercent = computed(() => unrealizedGainPercent(totalGainCents.value, totalCostBasisCents.value))

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
  demoStore.portfolioPerformance.map((point) => ({
    as_of: point.as_of,
    value_cents: point.total_market_value_cents,
  })),
)

async function loadPortfolioPerformance(range: PerformanceRange = '1M') {
  portfolioPerformanceError.value = ''
  try {
    await demoStore.fetchDemoPortfolioPerformance(range)
  } catch (error) {
    portfolioPerformanceError.value = getApiErrorMessage(error, 'Unable to load performance.')
  }
}

async function loadHoldingPerformance(holdingId: number, range: PerformanceRange = '1M') {
  holdingPerformanceErrors.value = { ...holdingPerformanceErrors.value, [holdingId]: '' }
  try {
    await demoStore.fetchDemoHoldingPerformance(holdingId, range)
  } catch (error) {
    holdingPerformanceErrors.value = {
      ...holdingPerformanceErrors.value,
      [holdingId]: getApiErrorMessage(error, 'Unable to load performance.'),
    }
  }
}

function holdingFlatPoints(holdingId: number) {
  return (demoStore.holdingPerformance[holdingId] ?? [])
    .filter(isFlatPricePoint)
    .map((point) => ({ as_of: point.as_of, value_cents: point.price_cents }))
}

function holdingOhlcPoints(holdingId: number) {
  return (demoStore.holdingPerformance[holdingId] ?? []).filter(isHoldingDailyOHLC)
}

function toggleHoldingExpanded(holdingId: number) {
  const next = new Set(expandedHoldingIds.value)
  if (next.has(holdingId)) {
    next.delete(holdingId)
  } else {
    next.add(holdingId)
    if (!demoStore.holdingPerformance[holdingId]) {
      loadHoldingPerformance(holdingId)
    }
  }
  expandedHoldingIds.value = next
}

onMounted(async () => {
  try {
    await Promise.all([demoStore.fetchDemoPortfolio(), demoStore.fetchDemoHoldings()])
    loadPortfolioPerformance()
  } catch (error) {
    loadError.value = getApiErrorMessage(error, 'The live demo is temporarily unavailable.')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="min-h-dvh bg-canvas">
    <header class="border-b border-border bg-surface">
      <div class="mx-auto flex h-14 max-w-5xl items-center justify-between gap-4 px-4">
        <div class="inline-flex items-center gap-2.5 text-sm font-semibold tracking-[0.14em] text-accent uppercase">
          <img :src="logoUrl" alt="" width="28" height="28" class="size-7 rounded-md" />
          Portfolio Tracker
        </div>
        <div class="flex items-center gap-3">
          <RouterLink :to="{ name: 'login' }">
            <AppButton variant="ghost">Log in</AppButton>
          </RouterLink>
          <RouterLink :to="{ name: 'register' }">
            <AppButton variant="secondary">Create an account</AppButton>
          </RouterLink>
        </div>
      </div>
    </header>

    <section class="py-24 bg-accent text-start">
      <div class="mx-auto max-w-5xl px-4">
    <section class="py-24 px-4 text-start bg-accent">
        <h1 class="text-4xl font-bold tracking-tight text-canvas">Track your investments with real time and historic data.</h1>
        <p class="mt-6 max-w-2xl text-base text-canvas">
          Portfolio Tracker pulls real market prices for your holdings, charts real
          performance history, and can run free AI analysis of your portfolio's patterns, grounded in your holdings and trade history.
        </p>
        <div class="mt-8 flex justify-center gap-3">
          <RouterLink :to="{ name: 'register' }">
            <AppButton variant="secondary">Get started</AppButton>
          </RouterLink>
          <RouterLink :to="{ name: 'login' }">
            <AppButton variant="secondary">Log in</AppButton>
          </RouterLink>
        </div>
      </div>
    </section>
      </section>

    <main class="mx-auto max-w-5xl px-4 py-12">
      <section class="mt-8">
        <div class="text-start">
          <h2 class="text-2xl font-bold tracking-tight text-ink">Try it live</h2>
          <p class="mt-2 text-sm text-ink-muted">
            Get a live AI analysis of a demo portfolio containing synthetic data.
          </p>
        </div>

        <AppAlert v-if="loadError" class="mt-8">{{ loadError }}</AppAlert>

        <p v-else-if="loading" class="mt-10 text-center text-sm text-ink-muted">Loading demo portfolio…</p>

        <template v-else>
          <AppAlert variant="info" class="mt-8 italic">
            Contoso, Fabrikam, Northwind, and AdventureWorks are fictional placeholder companies, not real, tradeable
            securities. The analysis is a live response from the same agent real accounts use.
          </AppAlert>

          <div class="mt-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h3 class="text-xl font-bold tracking-tight text-ink">
                {{ demoStore.portfolio?.name ?? 'Demo Portfolio' }}
              </h3>
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
              <AppButton variant="secondary" :disabled="analysisExhausted" @click="analysisOpen = true">
                Run demo analysis
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
              <p v-if="analysisExhausted" class="text-xs text-ink-muted">
                Demo limit reached for today. Resets at midnight UTC.
              </p>
              <p v-else-if="analysesRemaining !== null" class="text-xs text-ink-muted">
                {{ analysesRemaining }} demo run{{ analysesRemaining === 1 ? '' : 's' }} left today
              </p>
            </div>
          </div>

          <div class="mt-6 rounded-2xl border border-border bg-surface p-5">
            <h4 class="text-sm font-semibold text-ink-muted">Performance</h4>
            <PerformanceChart
              ref="portfolioChartRef"
              class="mt-2"
              :points="portfolioChartPoints"
              :loading="demoStore.portfolioPerformanceLoading"
              :error="portfolioPerformanceError || null"
              label="Portfolio value"
              @range-change="loadPortfolioPerformance"
            />
          </div>

          <div class="mt-8 overflow-x-auto rounded-2xl border border-border bg-surface">
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
                <template v-for="holding in demoStore.holdings" :key="holding.id">
                  <tr class="text-ink">
                    <td class="px-5 py-3.5 font-semibold">
                      <button
                        type="button"
                        class="inline-flex items-center gap-1.5 hover:text-accent"
                        :aria-expanded="expandedHoldingIds.has(holding.id)"
                        :aria-controls="`demo-holding-performance-${holding.id}`"
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
                    <td class="px-5 py-3.5 tabular-nums">{{ formatCents(holding.avg_cost_basis_cents) }}</td>
                    <td class="px-5 py-3.5 tabular-nums">{{ formatCents(holding.current_price_cents) }}</td>
                    <td class="px-5 py-3.5 tabular-nums font-medium">
                      {{ formatCents(holdingMarketValueCents(holding.shares, holding.current_price_cents)) }}
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
                  <tr v-if="expandedHoldingIds.has(holding.id)" :id="`demo-holding-performance-${holding.id}`">
                    <td colspan="6" class="bg-canvas/40 px-5 py-4">
                      <PerformanceChart
                        :ref="(el) => setHoldingChartRef(holding.id, el)"
                        :points="holdingFlatPoints(holding.id)"
                        :ohlc-points="holdingOhlcPoints(holding.id)"
                        :supports-ohlc="true"
                        :loading="!!demoStore.holdingPerformanceLoading[holding.id]"
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

          <p class="mt-3 text-center text-xs text-ink-muted">
            Synthetic demo data. Not your data, and not real companies. Create an account
            to track your own portfolio.
          </p>
        </template>
      </section>
    </main>

    <DemoAnalysisModal :open="analysisOpen" @close="analysisOpen = false" />
  </div>
</template>
