<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import RecordTradeModal from '@/components/portfolio/RecordTradeModal.vue'
import AppAlert from '@/components/ui/AppAlert.vue'
import AppButton from '@/components/ui/AppButton.vue'
import { usePortfolioStore } from '@/stores/portfolio'
import { getApiErrorMessage } from '@/utils/apiError'
import { formatCents, holdingMarketValueCents } from '@/utils/money'

const route = useRoute()
const portfolioStore = usePortfolioStore()

const loadError = ref('')
const loading = ref(true)
const tradeOpen = ref(false)

const portfolioId = computed(() => Number(route.params.portfolioId))

const totalMarketValueCents = computed(() =>
  portfolioStore.currentHoldings.reduce(
    (sum, holding) => sum + holdingMarketValueCents(holding.shares, holding.current_price_cents),
    0,
  ),
)

async function load() {
  if (!Number.isFinite(portfolioId.value)) {
    loadError.value = 'Invalid portfolio id.'
    loading.value = false
    return
  }

  loading.value = true
  loadError.value = ''
  try {
    await Promise.all([
      portfolioStore.fetchPortfolio(portfolioId.value),
      portfolioStore.fetchHoldings(portfolioId.value),
    ])
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
          </p>
        </div>

        <AppButton @click="tradeOpen = true">Record trade</AppButton>
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
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr
              v-for="holding in portfolioStore.currentHoldings"
              :key="holding.id"
              class="text-ink"
            >
              <td class="px-5 py-3.5 font-semibold">{{ holding.ticker }}</td>
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
            </tr>
          </tbody>
        </table>
      </div>

      <RecordTradeModal
        :open="tradeOpen"
        :portfolio-id="portfolioId"
        @close="tradeOpen = false"
      />
    </template>
  </div>
</template>
