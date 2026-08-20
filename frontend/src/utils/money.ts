/** Convert a dollar amount string/number to integer cents. */
export function dollarsToCents(dollars: string | number): number {
  const value = typeof dollars === 'string' ? Number(dollars) : dollars
  if (!Number.isFinite(value)) {
    return NaN
  }
  return Math.round(value * 100)
}

/** Format integer cents as a locale currency string (USD). */
export function formatCents(cents: number): string {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'USD',
  }).format(cents / 100)
}

/** Market value in cents for a holding position. */
export function holdingMarketValueCents(shares: number, priceCents: number): number {
  return Math.round(shares * priceCents)
}

/** Total cost basis in cents for a holding position (avg cost per share * shares). */
export function holdingCostBasisCents(shares: number, avgCostBasisCents: number): number {
  return Math.round(shares * avgCostBasisCents)
}

/** Unrealized gain/loss in cents: market value minus cost basis. */
export function unrealizedGainCents(marketValueCents: number, costBasisCents: number): number {
  return marketValueCents - costBasisCents
}

/** Unrealized gain/loss as a percentage of cost basis. Returns 0 when cost basis is 0 (no position to measure against). */
export function unrealizedGainPercent(gainCents: number, costBasisCents: number): number {
  if (costBasisCents === 0) return 0
  return (gainCents / costBasisCents) * 100
}

/** Format integer cents as a signed locale currency string, e.g. "+$120.50" or "-$45.00". */
export function formatSignedCents(cents: number): string {
  return `${cents > 0 ? '+' : ''}${formatCents(cents)}`
}

/** Format a percentage with a sign and two decimal places, e.g. "+4.32%" or "-1.05%". */
export function formatPercent(percent: number): string {
  return `${percent > 0 ? '+' : ''}${percent.toFixed(2)}%`
}
