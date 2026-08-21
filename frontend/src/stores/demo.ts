import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '@/api/axios'
import type { Holding, HoldingPerformancePoint, PerformanceRange, Portfolio, PortfolioValuePoint } from '@/stores/portfolio'

/** Mirrors the shape/behavior of usePortfolioStore, but against the public, unauthenticated
 * /demo/* endpoints -- see the product spec's "Public landing page" section. Kept as a
 * separate store rather than reusing usePortfolioStore's state so an anonymous visitor's
 * demo browsing never shares state with (or leaks into) an authenticated user's own
 * portfolio data. */
export const useDemoStore = defineStore('demo', () => {
  const portfolio = ref<Portfolio | null>(null)
  const holdings = ref<Holding[]>([])
  const portfolioPerformance = ref<PortfolioValuePoint[]>([])
  const portfolioPerformanceLoading = ref(false)
  const holdingPerformance = ref<Record<number, HoldingPerformancePoint[]>>({})
  const holdingPerformanceLoading = ref<Record<number, boolean>>({})
  /** Null until the first analyze response comes back (success or 429). */
  const analysesRemaining = ref<number | null>(null)

  async function fetchDemoPortfolio() {
    const response = await apiClient.get<Portfolio>('/demo/portfolio')
    portfolio.value = response.data
  }

  async function fetchDemoHoldings() {
    const response = await apiClient.get<Holding[]>('/demo/holdings')
    holdings.value = response.data
  }

  async function fetchDemoPortfolioPerformance(range: PerformanceRange = '1M') {
    portfolioPerformanceLoading.value = true
    try {
      const response = await apiClient.get<PortfolioValuePoint[]>('/demo/performance', { params: { range } })
      portfolioPerformance.value = response.data
    } finally {
      portfolioPerformanceLoading.value = false
    }
  }

  async function fetchDemoHoldingPerformance(holdingId: number, range: PerformanceRange = '1M') {
    holdingPerformanceLoading.value = { ...holdingPerformanceLoading.value, [holdingId]: true }
    try {
      const response = await apiClient.get<HoldingPerformancePoint[]>(
        `/demo/holdings/${holdingId}/performance`,
        { params: { range } },
      )
      holdingPerformance.value = { ...holdingPerformance.value, [holdingId]: response.data }
    } finally {
      holdingPerformanceLoading.value = { ...holdingPerformanceLoading.value, [holdingId]: false }
    }
  }

  async function analyzeDemoPortfolio(): Promise<string> {
    const response = await apiClient.post<{ report: string; demo_analyses_remaining_today: number }>(
      '/demo/analyze',
    )
    analysesRemaining.value = response.data.demo_analyses_remaining_today
    return response.data.report
  }

  /** Syncs local quota state immediately after a 429, without waiting on a separate
   * round-trip, so the Analyze button reflects reality right away. */
  function markQuotaExhausted() {
    analysesRemaining.value = 0
  }

  return {
    portfolio,
    holdings,
    portfolioPerformance,
    portfolioPerformanceLoading,
    holdingPerformance,
    holdingPerformanceLoading,
    analysesRemaining,
    fetchDemoPortfolio,
    fetchDemoHoldings,
    fetchDemoPortfolioPerformance,
    fetchDemoHoldingPerformance,
    analyzeDemoPortfolio,
    markQuotaExhausted,
  }
})
