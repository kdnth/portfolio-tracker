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

export const usePortfolioStore = defineStore('portfolio', () => {
  const portfolios = ref<Portfolio[]>([])
  const currentPortfolio = ref<Portfolio | null>(null)
  const currentHoldings = ref<Holding[]>([])
  const portfolioPerformance = ref<PortfolioValuePoint[]>([])
  const portfolioPerformanceLoading = ref(false)
  const holdingPerformance = ref<Record<number, PricePoint[]>>({})
  const holdingPerformanceLoading = ref<Record<number, boolean>>({})

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
      const response = await apiClient.get<PricePoint[]>(
        `/portfolios/${portfolioId}/holdings/${holdingId}/performance`,
        { params: { range } },
      )
      holdingPerformance.value = { ...holdingPerformance.value, [holdingId]: response.data }
    } finally {
      holdingPerformanceLoading.value = { ...holdingPerformanceLoading.value, [holdingId]: false }
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
    fetchPortfolios,
    createPortfolio,
    fetchHoldings,
    fetchPortfolio,
    createTrade,
    fetchPortfolioPerformance,
    fetchHoldingPerformance,
    clearCurrent,
  }
})
