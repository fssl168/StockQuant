/**
 * Iceberg order splitting algorithm.
 *
 * Breaks a large order into visible + hidden slices so that the market
 * only sees a small portion of the total quantity at any given time.
 *
 * Pattern: [VISIBLE showQty] → [HIDDEN hiddenQty] → [VISIBLE showQty] → ...
 */

export interface IcebergConfig {
  showQty: number      // Quantity shown in the order book per visible slice
  hiddenQty: number    // Quantity hidden (not shown) per hidden cycle
  minShowQty: number   // Minimum allowed showQty (prevents zero/negative)
}

export interface IcebergSlice {
  qty: number
  isVisible: boolean
  sequence: number
}

/**
 * Split a total quantity into alternating visible + hidden slices.
 *
 * Example: totalQty=5000, showQty=500, hiddenQty=1000
 *  Slice 1: qty=500,   visible=true   (cumulative: 500)
 *  Slice 2: qty=1000,  visible=false  (cumulative: 1500)
 *  Slice 3: qty=500,   visible=true   (cumulative: 2000)
 *  Slice 4: qty=1000,  visible=false  (cumulative: 3000)
 *  Slice 5: qty=500,   visible=true   (cumulative: 3500)
 *  Slice 6: qty=1000,  visible=false  (cumulative: 4500)
 *  Slice 7: qty=500,   visible=true   (cumulative: 5000)
 */
export function splitIceberg(
  totalQty: number,
  config: IcebergConfig,
): IcebergSlice[] {
  const showQty = Math.max(config.showQty, config.minShowQty)
  const hiddenQty = Math.max(config.hiddenQty, 0)

  if (totalQty <= 0 || showQty <= 0) {
    return []
  }

  const slices: IcebergSlice[] = []
  let sequence = 0
  let remaining = totalQty

  while (remaining > 0) {
    // Visible slice
    const visQty = Math.min(showQty, remaining)
    slices.push({ qty: visQty, isVisible: true, sequence: ++sequence })
    remaining -= visQty

    if (remaining <= 0) break

    // Hidden slice
    const hidQty = Math.min(hiddenQty, remaining)
    if (hidQty > 0) {
      slices.push({ qty: hidQty, isVisible: false, sequence: ++sequence })
      remaining -= hidQty
    }
  }

  return slices
}

/**
 * Given the full slice list and the cumulative filled quantity,
 * return the next slice to be submitted.
 *
 * Walks the slice list and returns the first slice whose cumulative
 * qty (inclusive) exceeds filledQty.
 */
export function getNextSlice(
  slices: IcebergSlice[],
  filledQty: number,
): IcebergSlice | null {
  let cumulative = 0

  for (const slice of slices) {
    cumulative += slice.qty
    if (cumulative > filledQty) {
      return slice
    }
  }

  return null
}
