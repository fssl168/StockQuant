/**
 * Emergency close utility.
 *
 * Rapidly flattens all positions by submitting sequential market orders.
 */

export interface Position {
  symbol: string
  shares: number
  price: number
}

export interface CloseResult {
  symbol: string
  success: boolean
  orderId?: string
  error?: string
}

/**
 * Place a single market sell order and return the result.
 *
 * The caller injects this dependency (typically a backend API call)
 * so the function stays pure in terms of I/O and testable.
 */
type PlaceMarketOrderFn = (order: {
  symbol: string
  side: 'SELL'
  type: 'MARKET'
  price: number
  quantity: number
}) => Promise<{ id: string }>

/**
 * Market-close every position in the list, one by one.
 *
 * Each position is flattened with a single MARKET order for the full
 * share count.  Results are collected and returned regardless of
 * individual failures.
 */
export async function emergencyCloseAll(
  positions: Position[],
  placeMarketOrder: PlaceMarketOrderFn,
): Promise<CloseResult[]> {
  const results: CloseResult[] = []

  for (const pos of positions) {
    try {
      const res = await placeMarketOrder({
        symbol: pos.symbol,
        side: 'SELL',
        type: 'MARKET',
        price: 0,
        quantity: pos.shares,
      })
      results.push({
        symbol: pos.symbol,
        success: true,
        orderId: res.id,
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '未知错误'
      results.push({
        symbol: pos.symbol,
        success: false,
        error: msg,
      })
    }
  }

  return results
}
