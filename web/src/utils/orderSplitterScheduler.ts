/**
 * Order splitter scheduler — execution engine for sliced orders.
 *
 * Consumes a slice plan (produced by `splitByTime` / `splitIceberg` /
 * custom input) and submits each slice via the injected `placeOrder`
 * function at the slice's scheduled time.
 *
 * Design:
 * - Pure logic, no React dependency (testable in isolation).
 * - Sequential execution: each slice is awaited before scheduling the next.
 * - Per-slice failure does NOT abort the remaining slices — the scheduler
 *   records the failure and proceeds.
 * - `cancel()` clears any pending timeout and stops further submission;
 *   an in-flight HTTP request is allowed to complete (its result is still
 *   recorded, but no further slices are dispatched).
 *
 * NOT included (avoiding over-engineering):
 * - pause/resume (re-call `start()` with remaining slices instead).
 * - retry/backoff (the caller can re-inject a retrying placeOrder fn).
 */

export interface SplitOrderSlice {
  /** Quantity for this slice. Must be > 0. */
  qty: number
  /**
   * Scheduled submission time. If omitted or in the past, the slice
   * is submitted immediately after the previous slice completes.
   */
  execAt?: Date
}

export interface SchedulerOrderConfig {
  symbol: string
  side: 'BUY' | 'SELL'
  type: 'MARKET' | 'LIMIT'
  /** Required for LIMIT orders; ignored for MARKET orders (use 0). */
  price?: number
}

export interface SliceResult {
  sequence: number
  qty: number
  success: boolean
  orderId?: string
  error?: string
  submittedAt: Date
}

export interface SplitterProgress {
  totalSlices: number
  completedSlices: number
  failedSlices: number
  filledQty: number
  totalQty: number
  isRunning: boolean
  isCancelled: boolean
  results: SliceResult[]
}

export type PlaceOrderFn = (order: {
  symbol: string
  side: 'BUY' | 'SELL'
  type: 'MARKET' | 'LIMIT'
  price: number
  quantity: number
}) => Promise<{ id: string }>

export interface SchedulerOptions {
  onProgress?: (progress: SplitterProgress) => void
  onComplete?: (progress: SplitterProgress) => void
  onError?: (error: Error, slice: SliceResult) => void
  /** Timer factory (defaults to setTimeout); injected for testing. */
  setTimeoutFn?: (fn: () => void, ms: number) => ReturnType<typeof setTimeout>
  /** Clear timer (defaults to clearTimeout); injected for testing. */
  clearTimeoutFn?: (id: ReturnType<typeof setTimeout>) => void
  /** now() factory, injectable for deterministic tests. */
  nowFn?: () => Date
}

const DEFAULT_NOW = () => new Date()
const DEFAULT_SET_TIMEOUT = (fn: () => void, ms: number) => setTimeout(fn, ms)
const DEFAULT_CLEAR_TIMEOUT = (id: ReturnType<typeof setTimeout>) => clearTimeout(id)

export class OrderSplitterScheduler {
  private readonly config: SchedulerOrderConfig
  private readonly slices: readonly SplitOrderSlice[]
  private readonly placeOrder: PlaceOrderFn
  private readonly options: Required<Omit<SchedulerOptions, 'onProgress' | 'onComplete' | 'onError'>>
  private readonly onProgress?: (progress: SplitterProgress) => void
  private readonly onComplete?: (progress: SplitterProgress) => void
  private readonly onError?: (error: Error, slice: SliceResult) => void

  private results: SliceResult[] = []
  private filledQty = 0
  private running = false
  private cancelled = false
  private pendingTimer: ReturnType<typeof setTimeout> | null = null

  constructor(
    config: SchedulerOrderConfig,
    slices: readonly SplitOrderSlice[],
    placeOrder: PlaceOrderFn,
    options: SchedulerOptions = {},
  ) {
    this.config = config
    // Defensive copy to prevent caller mutation mid-run
    this.slices = slices.map((s) => ({ ...s }))
    this.placeOrder = placeOrder
    this.onProgress = options.onProgress
    this.onComplete = options.onComplete
    this.onError = options.onError
    this.options = {
      setTimeoutFn: options.setTimeoutFn ?? DEFAULT_SET_TIMEOUT,
      clearTimeoutFn: options.clearTimeoutFn ?? DEFAULT_CLEAR_TIMEOUT,
      nowFn: options.nowFn ?? DEFAULT_NOW,
    }
  }

  /** Begin sequential submission of slices. Safe to call once. */
  start(): void {
    if (this.running) return
    if (this.slices.length === 0) {
      // Nothing to do — emit a final progress + complete event.
      this.emitProgress()
      this.emitComplete()
      return
    }
    this.running = true
    void this.dispatchNext(0)
  }

  /**
   * Cancel pending submissions. An in-flight request is allowed to finish.
   *
   * No-op if the scheduler has not started or has already been cancelled.
   * Calling `cancel()` before `start()` does NOT mark the scheduler as
   * cancelled — the caller can still `start()` it later.
   */
  cancel(): void {
    if (this.cancelled) return
    if (!this.running) return
    this.cancelled = true
    if (this.pendingTimer !== null) {
      this.options.clearTimeoutFn(this.pendingTimer)
      this.pendingTimer = null
    }
    this.running = false
    this.emitProgress()
    this.emitComplete()
  }

  isRunning(): boolean {
    return this.running
  }

  isCancelled(): boolean {
    return this.cancelled
  }

  getProgress(): SplitterProgress {
    return {
      totalSlices: this.slices.length,
      completedSlices: this.results.length,
      failedSlices: this.results.filter((r) => !r.success).length,
      filledQty: this.filledQty,
      totalQty: this.slices.reduce((s, sl) => s + sl.qty, 0),
      isRunning: this.running,
      isCancelled: this.cancelled,
      results: [...this.results],
    }
  }

  // ---------- internals ----------

  private async dispatchNext(index: number): Promise<void> {
    if (this.cancelled) return
    if (index >= this.slices.length) {
      this.running = false
      this.emitProgress()
      this.emitComplete()
      return
    }

    const slice = this.slices[index]
    const now = this.options.nowFn()

    // Compute delay until execAt (negative/past = immediate)
    let delayMs = 0
    if (slice.execAt) {
      delayMs = slice.execAt.getTime() - now.getTime()
      if (delayMs < 0) delayMs = 0
    }

    if (delayMs > 0) {
      this.pendingTimer = this.options.setTimeoutFn(() => {
        this.pendingTimer = null
        void this.executeSlice(index, slice)
      }, delayMs)
    } else {
      void this.executeSlice(index, slice)
    }
  }

  private async executeSlice(index: number, slice: SplitOrderSlice): Promise<void> {
    if (this.cancelled) return

    const sequence = index + 1
    const submittedAt = this.options.nowFn()
    const price = this.config.type === 'LIMIT' ? (this.config.price ?? 0) : 0

    try {
      const res = await this.placeOrder({
        symbol: this.config.symbol,
        side: this.config.side,
        type: this.config.type,
        price,
        quantity: slice.qty,
      })
      if (this.cancelled) return
      this.results.push({
        sequence,
        qty: slice.qty,
        success: true,
        orderId: res.id,
        submittedAt,
      })
      this.filledQty += slice.qty
    } catch (err: unknown) {
      if (this.cancelled) return
      const msg = err instanceof Error ? err.message : '未知错误'
      const result: SliceResult = {
        sequence,
        qty: slice.qty,
        success: false,
        error: msg,
        submittedAt,
      }
      this.results.push(result)
      this.onError?.(err instanceof Error ? err : new Error(String(err)), result)
    }

    this.emitProgress()
    void this.dispatchNext(index + 1)
  }

  private emitProgress(): void {
    this.onProgress?.(this.getProgress())
  }

  private emitComplete(): void {
    this.onComplete?.(this.getProgress())
  }
}
