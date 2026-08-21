import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '@/api/axios'

export interface Portfolio {
  id: number
  user_id: number
  name: string
  created_at: string
  updated_at: string
}

export interface Holding {
  id: number
  portfolio_id: number
  ticker: string
  shares: number
  avg_cost_basis_cents: number
  current_price_cents: number
  last_priced_at: string
}

export type PerformanceRange = '1D' | '1W' | '1M'

export interface PortfolioValuePoint {
  as_of: string
  total_market_value_cents: number
}

export interface PricePoint {
  as_of: string
  price_cents: number
}

export interface HoldingDailyOHLC {
  date: string
  open_cents: number
  /** Null specifically for the current day while the market is still open -- there is no
   * real close yet. See the product spec's "Chart range behavior" section. */
  close_cents: number | null
  high_cents: number
  low_cents: number
}

/** The holding performance endpoint's response shape depends on range: flat PricePoints
 * for 1D, one HoldingDailyOHLC per day for 1W/1M. See the product spec's "Chart range
 * behavior" section. */
export type HoldingPerformancePoint = PricePoint | HoldingDailyOHLC

export function isHoldingDailyOHLC(point: HoldingPerformancePoint): point is HoldingDailyOHLC {
  return 'open_cents' in point
}

export function isFlatPricePoint(point: HoldingPerformancePoint): point is PricePoint {
  return 'price_cents' in point
}

export interface AnalysisQuota {
  limit: number
  used_today: number
  /** Null means unlimited -- the current user is an admin, exempt from the daily quota. */
  remaining: number | null
}

export const usePortfolioStore = defineStore('portfolio', () => {
  const portfolios = ref<Portfolio[]>([])
  const currentPortfolio = ref<Portfolio | null>(null)
  const currentHoldings = ref<Holding[]>([])
  const portfolioPerformance = ref<PortfolioValuePoint[]>([])
  const portfolioPerformanceLoading = ref(false)
  const holdingPerformance = ref<Record<number, HoldingPerformancePoint[]>>({})
  const holdingPerformanceLoading = ref<Record<number, boolean>>({})
  const analysisQuota = ref<AnalysisQuota | null>(null)

  async function fetchPortfolios() {
    const response = await apiClient.get<Portfolio[]>('/portfolios/')
    portfolios.value = response.data
  }

  async function createPortfolio(name: string) {
    const response = await apiClient.post<Portfolio>('/portfolios/', { name })
    portfolios.value.push(response.data)
    return response.data
  }

  async function fetchPortfolio(portfolioId: number) {
    const response = await apiClient.get<Portfolio>(`/portfolios/${portfolioId}`)
    currentPortfolio.value = response.data
  }

  async function fetchHoldings(portfolioId: number) {
    const response = await apiClient.get<Holding[]>(`/portfolios/${portfolioId}/holdings/`)
    currentHoldings.value = response.data
  }

  async function createTrade(
    portfolioId: number,
    trade: {
      ticker: string
      trade_type: 'buy' | 'sell'
      shares: number
      price_per_share_cents: number
      executed_at: string
    },
  ) {
    await apiClient.post(`/portfolios/${portfolioId}/trades/`, trade)
    await fetchHoldings(portfolioId)
  }

  async function fetchPortfolioPerformance(portfolioId: number, range: PerformanceRange = '1M') {
    portfolioPerformanceLoading.value = true
    try {
      const response = await apiClient.get<PortfolioValuePoint[]>(
        `/portfolios/${portfolioId}/performance`,
        { params: { range } },
      )
      portfolioPerformance.value = response.data
    } finally {
      portfolioPerformanceLoading.value = false
    }
  }

  async function fetchHoldingPerformance(
    portfolioId: number,
    holdingId: number,
    range: PerformanceRange = '1M',
  ) {
    holdingPerformanceLoading.value = { ...holdingPerformanceLoading.value, [holdingId]: true }
    try {
      const response = await apiClient.get<HoldingPerformancePoint[]>(
        `/portfolios/${portfolioId}/holdings/${holdingId}/performance`,
        { params: { range } },
      )
      holdingPerformance.value = { ...holdingPerformance.value, [holdingId]: response.data }
    } finally {
      holdingPerformanceLoading.value = { ...holdingPerformanceLoading.value, [holdingId]: false }
    }
  }

  async function fetchAnalysisQuota() {
    const response = await apiClient.get<AnalysisQuota>('/users/me/analysis-quota')
    analysisQuota.value = response.data
  }

  async function analyzePortfolio(portfolioId: number): Promise<string> {
    const response = await apiClient.post<{ report: string; analyses_remaining_today: number | null }>(
      `/portfolios/${portfolioId}/analyze`,
    )
    analysisQuota.value = analysisQuota.value
      ? { ...analysisQuota.value, remaining: response.data.analyses_remaining_today }
      : null
    return response.data.report
  }

  /** Syncs local quota state immediately after a 429, without waiting on a separate
   * fetchAnalysisQuota() round-trip, so the Analyze button reflects reality right away. */
  function markQuotaExhausted() {
    if (analysisQuota.value) {
      analysisQuota.value = { ...analysisQuota.value, remaining: 0 }
    }
  }

  function clearCurrent() {
    currentPortfolio.value = null
    currentHoldings.value = []
    portfolioPerformance.value = []
    holdingPerformance.value = {}
  }

  return {
    portfolios,
    currentPortfolio,
    currentHoldings,
    portfolioPerformance,
    portfolioPerformanceLoading,
    holdingPerformance,
    holdingPerformanceLoading,
    analysisQuota,
    fetchPortfolios,
    createPortfolio,
    fetchHoldings,
    fetchPortfolio,
    createTrade,
    fetchPortfolioPerformance,
    fetchHoldingPerformance,
    fetchAnalysisQuota,
    analyzePortfolio,
    markQuotaExhausted,
    clearCurrent,
  }
})
