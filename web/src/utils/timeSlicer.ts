/**
 * Time-based order slicing algorithm.
 *
 * Distributes a total quantity across N evenly-spaced time slots,
 * optionally with random jitter to obscure intent.
 */

export interface TimeSliceConfig {
  totalQty: number
  sliceCount: number
  intervalSec: number
  randomize: boolean
  randomizeRangeSec: number
}

export interface TimeSlice {
  qty: number
  execAt: Date
}

/**
 * Split a total quantity into N equal slices at regular intervals.
 *
 * The first slice is scheduled at `now`, subsequent slices at
 * `now + i * intervalSec`.  If `randomize` is true, each execAt is offset
 * by a random value in `[-randomizeRangeSec, +randomizeRangeSec]`.
 *
 * If sliceCount is 1, returns a single slice for the full quantity.
 */
export function splitByTime(config: TimeSliceConfig): TimeSlice[] {
  const { totalQty, sliceCount, intervalSec, randomize, randomizeRangeSec } = config

  if (totalQty <= 0 || sliceCount <= 0 || intervalSec <= 0) {
    return []
  }

  const now = new Date()
  const qtyPerSlice = Math.floor(totalQty / sliceCount)
  const remainder = totalQty - qtyPerSlice * sliceCount

  const slices: TimeSlice[] = []

  for (let i = 0; i < sliceCount; i++) {
    const execAt = new Date(now.getTime() + i * intervalSec * 1000)

    if (randomize && randomizeRangeSec > 0) {
      const jitterMs =
        (Math.random() * 2 - 1) * randomizeRangeSec * 1000
      execAt.setTime(execAt.getTime() + jitterMs)
    }

    // Last slice absorbs the remainder
    const qty = i === sliceCount - 1 ? qtyPerSlice + remainder : qtyPerSlice

    slices.push({ qty, execAt })
  }

  return slices
}
