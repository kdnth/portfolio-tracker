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

export const usePortfolioStore = defineStore('portfolio', () => {
  const portfolios = ref<Portfolio[]>([])
  const currentPortfolio = ref<Portfolio | null>(null)
  const currentHoldings = ref<Holding[]>([])

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

  function clearCurrent() {
    currentPortfolio.value = null
    currentHoldings.value = []
  }

  return {
    portfolios,
    currentPortfolio,
    currentHoldings,
    fetchPortfolios,
    createPortfolio,
    fetchHoldings,
    fetchPortfolio,
    createTrade,
    clearCurrent,
  }
})
