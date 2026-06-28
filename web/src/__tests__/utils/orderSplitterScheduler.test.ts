import { describe, it, expect, vi } from 'vitest'
import {
  OrderSplitterScheduler,
  type SplitOrderSlice,
  type SchedulerOrderConfig,
  type PlaceOrderFn,
  type SliceResult,
  type SplitterProgress,
} from '@/utils/orderSplitterScheduler'

// ── Fake timer infrastructure ───────────────────────────────
// We inject setTimeout/clearTimeout so tests are fully synchronous and
// deterministic — no real wall-clock waits.

interface PendingTimer {
  id: number
  fn: () => void
  ms: number
}

class FakeTimerHost {
  private pending: PendingTimer[] = []
  private nextId = 1
  private _nowMs: number

  constructor(startMs: number = Date.now()) {
    this._nowMs = startMs
  }

  setTimeout = (fn: () => void, ms: number) => {
    const id = this.nextId++
    this.pending.push({ id, fn, ms })
    return id as unknown as ReturnType<typeof setTimeout>
  }

  clearTimeout = (id: ReturnType<typeof setTimeout>) => {
    const numId = id as unknown as number
    this.pending = this.pending.filter((p) => p.id !== numId)
  }

  now = () => new Date(this._nowMs)

  advance(ms: number): void {
    this._nowMs += ms
  }

  /** Run all pending timers (in insertion order) and return count fired. */
  flush(): number {
    const due = [...this.pending]
    this.pending = []
    for (const t of due) t.fn()
    return due.length
  }

  pendingCount(): number {
    return this.pending.length
  }
}

function makePlaceOrderSuccess(): PlaceOrderFn & { calls: any[] } {
  const calls: any[] = []
  const fn = vi.fn(async (order: any) => {
    calls.push(order)
    return { id: `ORD-${calls.length}` }
  }) as unknown as PlaceOrderFn & { calls: any[] }
  // Attach calls array for assertions
  ;(fn as any).calls = calls
  return fn
}

function makePlaceOrderFailures(errors: Error[]): PlaceOrderFn {
  let i = 0
  return vi.fn(async () => {
    const err = errors[i++] ?? errors[errors.length - 1]
    throw err
  }) as unknown as PlaceOrderFn
}

const BASE_CONFIG: SchedulerOrderConfig = {
  symbol: 'sh600519',
  side: 'BUY',
  type: 'MARKET',
}

describe('OrderSplitterScheduler', () => {
  describe('empty slices', () => {
    it('emits a final complete event with zero slices when slices list is empty', () => {
      const onProgress = vi.fn()
      const onComplete = vi.fn()
      const placeOrder = makePlaceOrderSuccess()
      const scheduler = new OrderSplitterScheduler(
        BASE_CONFIG,
        [],
        placeOrder,
        { onProgress, onComplete },
      )

      scheduler.start()

      expect(placeOrder).not.toHaveBeenCalled()
      expect(onComplete).toHaveBeenCalledTimes(1)
      const progress = onComplete.mock.calls[0][0] as SplitterProgress
      expect(progress.totalSlices).toBe(0)
      expect(progress.completedSlices).toBe(0)
      expect(progress.filledQty).toBe(0)
      expect(progress.isRunning).toBe(false)
    })
  })

  describe('single slice, immediate execution', () => {
    it('submits a single MARKET order with price=0 and the slice quantity', async () => {
      const placeOrder = makePlaceOrderSuccess()
      const slices: SplitOrderSlice[] = [{ qty: 500 }]
      const scheduler = new OrderSplitterScheduler(BASE_CONFIG, slices, placeOrder)

      scheduler.start()
      // Let the in-flight promise resolve
      await flushMicrotasks()

      expect(placeOrder).toHaveBeenCalledTimes(1)
      expect((placeOrder as any).calls[0]).toEqual({
        symbol: 'sh600519',
        side: 'BUY',
        type: 'MARKET',
        price: 0,
        quantity: 500,
      })
    })

    it('records a successful result and updates filledQty', async () => {
      const placeOrder = makePlaceOrderSuccess()
      const scheduler = new OrderSplitterScheduler(
        BASE_CONFIG,
        [{ qty: 250 }],
        placeOrder,
      )

      scheduler.start()
      await flushMicrotasks()

      const progress = scheduler.getProgress()
      expect(progress.completedSlices).toBe(1)
      expect(progress.failedSlices).toBe(0)
      expect(progress.filledQty).toBe(250)
      expect(progress.totalQty).toBe(250)
      expect(progress.isRunning).toBe(false)
      expect(progress.results[0].success).toBe(true)
      expect(progress.results[0].orderId).toBe('ORD-1')
    })
  })

  describe('LIMIT orders', () => {
    it('submits a LIMIT order with the configured price', async () => {
      const placeOrder = makePlaceOrderSuccess()
      const config: SchedulerOrderConfig = {
        symbol: 'sh600519',
        side: 'SELL',
        type: 'LIMIT',
        price: 1700,
      }
      const scheduler = new OrderSplitterScheduler(
        config,
        [{ qty: 100 }],
        placeOrder,
      )

      scheduler.start()
      await flushMicrotasks()

      expect((placeOrder as any).calls[0]).toEqual({
        symbol: 'sh600519',
        side: 'SELL',
        type: 'LIMIT',
        price: 1700,
        quantity: 100,
      })
    })

    it('uses price=0 when LIMIT price is omitted', async () => {
      const placeOrder = makePlaceOrderSuccess()
      const scheduler = new OrderSplitterScheduler(
        { symbol: 'X', side: 'BUY', type: 'LIMIT' },
        [{ qty: 1 }],
        placeOrder,
      )
      scheduler.start()
      await flushMicrotasks()
      expect((placeOrder as any).calls[0].price).toBe(0)
    })
  })

  describe('multiple slices, immediate execution', () => {
    it('submits all slices sequentially in order', async () => {
      const placeOrder = makePlaceOrderSuccess()
      const slices: SplitOrderSlice[] = [
        { qty: 100 },
        { qty: 200 },
        { qty: 300 },
      ]
      const scheduler = new OrderSplitterScheduler(BASE_CONFIG, slices, placeOrder)

      scheduler.start()
      await flushMicrotasks()

      expect(placeOrder).toHaveBeenCalledTimes(3)
      expect((placeOrder as any).calls.map((c: any) => c.quantity)).toEqual([
        100, 200, 300,
      ])
      const progress = scheduler.getProgress()
      expect(progress.completedSlices).toBe(3)
      expect(progress.filledQty).toBe(600)
      expect(progress.results.map((r) => r.sequence)).toEqual([1, 2, 3])
    })

    it('executes strictly sequentially (next slice waits for previous to resolve)', async () => {
      const order: string[] = []
      const placeOrder = vi.fn(async (req: any) => {
        order.push(`start-${req.quantity}`)
        // Use microtasks (not setTimeout) so flushMicrotasks can advance them
        await Promise.resolve()
        await Promise.resolve()
        order.push(`end-${req.quantity}`)
        return { id: `ORD-${req.quantity}` }
      }) as unknown as PlaceOrderFn
      const scheduler = new OrderSplitterScheduler(
        BASE_CONFIG,
        [{ qty: 1 }, { qty: 2 }, { qty: 3 }],
        placeOrder,
      )

      scheduler.start()
      await flushMicrotasks()

      expect(order).toEqual([
        'start-1', 'end-1',
        'start-2', 'end-2',
        'start-3', 'end-3',
      ])
    })
  })

  describe('slice failure handling', () => {
    it('continues with next slice when one fails', async () => {
      // First call throws; subsequent calls should succeed (partial failure).
      let call = 0
      const mixed = vi.fn(async () => {
        call++
        if (call === 1) throw new Error('order rejected')
        return { id: `ORD-${call}` }
      }) as unknown as PlaceOrderFn
      const scheduler = new OrderSplitterScheduler(
        BASE_CONFIG,
        [{ qty: 100 }, { qty: 200 }, { qty: 300 }],
        mixed,
      )

      scheduler.start()
      await flushMicrotasks()

      expect(mixed).toHaveBeenCalledTimes(3)
      const progress = scheduler.getProgress()
      expect(progress.completedSlices).toBe(3)
      expect(progress.failedSlices).toBe(1)
      expect(progress.filledQty).toBe(500) // 200 + 300, the 100 failure doesn't count
      expect(progress.results[0].success).toBe(false)
      expect(progress.results[0].error).toBe('order rejected')
      expect(progress.results[1].success).toBe(true)
      expect(progress.results[2].success).toBe(true)
    })

    it('invokes onError with the failing slice and error', async () => {
      const onError = vi.fn()
      const placeOrder = makePlaceOrderFailures([new Error('network down')])
      const scheduler = new OrderSplitterScheduler(
        BASE_CONFIG,
        [{ qty: 100 }],
        placeOrder,
        { onError },
      )

      scheduler.start()
      await flushMicrotasks()

      expect(onError).toHaveBeenCalledTimes(1)
      const [err, slice] = onError.mock.calls[0] as [Error, SliceResult]
      expect(err.message).toBe('network down')
      expect(slice.success).toBe(false)
      expect(slice.qty).toBe(100)
    })

    it('falls back to generic message for non-Error throws', async () => {
      const placeOrder = vi.fn(async () => {
        throw 'string error'
      }) as unknown as PlaceOrderFn
      const scheduler = new OrderSplitterScheduler(
        BASE_CONFIG,
        [{ qty: 1 }],
        placeOrder,
      )

      scheduler.start()
      await flushMicrotasks()

      expect(scheduler.getProgress().results[0].error).toBe('未知错误')
    })
  })

  describe('scheduled execution (execAt)', () => {
    it('schedules a timer when execAt is in the future', () => {
      const host = new FakeTimerHost(10_000)
      const placeOrder = makePlaceOrderSuccess()
      const slices: SplitOrderSlice[] = [
        { qty: 100, execAt: new Date(10_000 + 5_000) }, // +5s
      ]
      const scheduler = new OrderSplitterScheduler(BASE_CONFIG, slices, placeOrder, {
        setTimeoutFn: host.setTimeout,
        clearTimeoutFn: host.clearTimeout,
        nowFn: host.now,
      })

      scheduler.start()
      // Place order should NOT have been called yet — timer pending
      expect(placeOrder).not.toHaveBeenCalled()
      expect(host.pendingCount()).toBe(1)

      // Advance time + flush timer
      host.advance(5_000)
      host.flush()
      // The order is async — let it resolve
      return flushMicrotasks().then(() => {
        expect(placeOrder).toHaveBeenCalledTimes(1)
      })
    })

    it('submits immediately when execAt is in the past', () => {
      const host = new FakeTimerHost(20_000)
      const placeOrder = makePlaceOrderSuccess()
      const slices: SplitOrderSlice[] = [
        { qty: 100, execAt: new Date(10_000) }, // 10s ago
      ]
      const scheduler = new OrderSplitterScheduler(BASE_CONFIG, slices, placeOrder, {
        setTimeoutFn: host.setTimeout,
        clearTimeoutFn: host.clearTimeout,
        nowFn: host.now,
      })

      scheduler.start()
      // No timer should have been scheduled
      expect(host.pendingCount()).toBe(0)
    })

    it('submits immediately when execAt is omitted', () => {
      const host = new FakeTimerHost(0)
      const placeOrder = makePlaceOrderSuccess()
      const scheduler = new OrderSplitterScheduler(
        BASE_CONFIG,
        [{ qty: 100 }],
        placeOrder,
        {
          setTimeoutFn: host.setTimeout,
          clearTimeoutFn: host.clearTimeout,
          nowFn: host.now,
        },
      )
      scheduler.start()
      expect(host.pendingCount()).toBe(0)
    })
  })

  describe('cancel()', () => {
    it('clears the pending timer and stops further submission', async () => {
      const host = new FakeTimerHost(10_000)
      const placeOrder = makePlaceOrderSuccess()
      const slices: SplitOrderSlice[] = [
        { qty: 100, execAt: new Date(20_000) }, // +10s
        { qty: 200, execAt: new Date(30_000) },
      ]
      const scheduler = new OrderSplitterScheduler(BASE_CONFIG, slices, placeOrder, {
        setTimeoutFn: host.setTimeout,
        clearTimeoutFn: host.clearTimeout,
        nowFn: host.now,
      })

      scheduler.start()
      expect(host.pendingCount()).toBe(1)
      expect(scheduler.isRunning()).toBe(true)

      scheduler.cancel()

      expect(scheduler.isRunning()).toBe(false)
      expect(scheduler.isCancelled()).toBe(true)
      expect(host.pendingCount()).toBe(0)

      // Flushing would have been a no-op anyway (timer cleared)
      host.flush()
      await flushMicrotasks()
      expect(placeOrder).not.toHaveBeenCalled()
    })

    it('emits complete event with isCancelled=true on cancel', () => {
      const onComplete = vi.fn()
      const host = new FakeTimerHost(0)
      const scheduler = new OrderSplitterScheduler(
        BASE_CONFIG,
        [{ qty: 100, execAt: new Date(100_000) }],
        makePlaceOrderSuccess(),
        {
          onComplete,
          setTimeoutFn: host.setTimeout,
          clearTimeoutFn: host.clearTimeout,
          nowFn: host.now,
        },
      )
      scheduler.start()
      scheduler.cancel()

      const progress = onComplete.mock.calls[0][0] as SplitterProgress
      expect(progress.isCancelled).toBe(true)
      expect(progress.isRunning).toBe(false)
    })

    it('cancel is a no-op when not running', () => {
      const scheduler = new OrderSplitterScheduler(
        BASE_CONFIG,
        [{ qty: 1 }],
        makePlaceOrderSuccess(),
      )
      expect(() => scheduler.cancel()).not.toThrow()
      expect(scheduler.isCancelled()).toBe(false) // never started
    })
  })

  describe('start() idempotency', () => {
    it('second call to start() is a no-op', async () => {
      const placeOrder = makePlaceOrderSuccess()
      const scheduler = new OrderSplitterScheduler(
        BASE_CONFIG,
        [{ qty: 100 }],
        placeOrder,
      )
      scheduler.start()
      scheduler.start() // should not double-dispatch
      await flushMicrotasks()
      expect(placeOrder).toHaveBeenCalledTimes(1)
    })
  })

  describe('progress callbacks', () => {
    it('onProgress fires after each slice completes', async () => {
      const onProgress = vi.fn()
      const placeOrder = makePlaceOrderSuccess()
      const scheduler = new OrderSplitterScheduler(
        BASE_CONFIG,
        [{ qty: 100 }, { qty: 200 }],
        placeOrder,
        { onProgress },
      )
      scheduler.start()
      await flushMicrotasks()

      // At least 2 progress emissions (one per slice); possibly an extra
      // final emission. We only assert >= 2 and that the last call shows
      // completedSlices = 2.
      expect(onProgress.mock.calls.length).toBeGreaterThanOrEqual(2)
      const last = onProgress.mock.calls[onProgress.mock.calls.length - 1][0] as SplitterProgress
      expect(last.completedSlices).toBe(2)
    })

    it('onComplete fires exactly once at the end', async () => {
      const onComplete = vi.fn()
      const scheduler = new OrderSplitterScheduler(
        BASE_CONFIG,
        [{ qty: 100 }, { qty: 200 }],
        makePlaceOrderSuccess(),
        { onComplete },
      )
      scheduler.start()
      await flushMicrotasks()
      expect(onComplete).toHaveBeenCalledTimes(1)
    })
  })

  describe('defensive copy', () => {
    it('mutating the input slices array after construction does not affect execution', async () => {
      const placeOrder = makePlaceOrderSuccess()
      const slices: SplitOrderSlice[] = [{ qty: 100 }, { qty: 200 }]
      const scheduler = new OrderSplitterScheduler(BASE_CONFIG, slices, placeOrder)

      slices.push({ qty: 999 }) // post-construction mutation

      scheduler.start()
      await flushMicrotasks()
      expect(placeOrder).toHaveBeenCalledTimes(2)
      expect(scheduler.getProgress().totalQty).toBe(300)
    })
  })
})

// Helper: flush the microtask queue several times to await async work
async function flushMicrotasks(): Promise<void> {
  for (let i = 0; i < 10; i++) {
    await Promise.resolve()
  }
}
