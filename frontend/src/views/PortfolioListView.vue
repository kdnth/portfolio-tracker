<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import CreatePortfolioModal from '@/components/portfolio/CreatePortfolioModal.vue'
import AppAlert from '@/components/ui/AppAlert.vue'
import AppButton from '@/components/ui/AppButton.vue'
import { usePortfolioStore } from '@/stores/portfolio'
import { getApiErrorMessage } from '@/utils/apiError'

const portfolioStore = usePortfolioStore()

const loadError = ref('')
const loading = ref(true)
const createOpen = ref(false)

onMounted(async () => {
  loading.value = true
  loadError.value = ''
  try {
    await portfolioStore.fetchPortfolios()
  } catch (error) {
    loadError.value = getApiErrorMessage(error, 'Unable to load portfolios.')
  } finally {
    loading.value = false
  }
})

function formatUpdatedAt(value: string) {
  return new Date(value).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}
</script>

<template>
  <div>
    <div class="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 class="text-3xl font-bold tracking-tight text-ink">Portfolios</h1>
        <p class="mt-1 text-sm text-ink-muted">Open a book to review holdings and record trades.</p>
      </div>

      <AppButton @click="createOpen = true">New portfolio</AppButton>
    </div>

    <AppAlert v-if="loadError" class="mt-6">{{ loadError }}</AppAlert>

    <p v-else-if="loading" class="mt-10 text-sm text-ink-muted">Loading portfolios…</p>

    <div
      v-else-if="portfolioStore.portfolios.length === 0"
      class="mt-10 rounded-2xl border border-dashed border-border bg-surface px-6 py-12 text-center"
    >
      <h2 class="text-lg font-semibold text-ink">No portfolios yet</h2>
      <p class="mt-2 text-sm text-ink-muted">Create one to start tracking holdings and trades.</p>
      <div class="mt-6 flex justify-center">
        <AppButton @click="createOpen = true">Create portfolio</AppButton>
      </div>
    </div>

    <ul v-else class="mt-8 divide-y divide-border overflow-hidden rounded-2xl border border-border bg-surface">
      <li v-for="portfolio in portfolioStore.portfolios" :key="portfolio.id">
        <RouterLink
          :to="{ name: 'portfolio-detail', params: { portfolioId: portfolio.id } }"
          class="flex items-center justify-between gap-4 px-5 py-4 transition hover:bg-canvas"
        >
          <div>
            <p class="font-semibold text-ink">{{ portfolio.name }}</p>
            <p class="mt-0.5 text-sm text-ink-muted">
              Updated {{ formatUpdatedAt(portfolio.updated_at) }}
            </p>
          </div>
          <span class="text-sm font-medium text-accent">Open</span>
        </RouterLink>
      </li>
    </ul>

    <CreatePortfolioModal :open="createOpen" @close="createOpen = false" />
  </div>
</template>
