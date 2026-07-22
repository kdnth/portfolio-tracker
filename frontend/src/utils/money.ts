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
