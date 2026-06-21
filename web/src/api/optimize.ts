import client from './client'
import { OptimizeConfig, OptimizeResult } from '../types'

// ── Real API Functions ─────────────────────────────────────────

/**
 * Submit an optimization task.
 * POST /backtest/optimize → { task_id }
 */
export async function runOptimization(config: OptimizeConfig): Promise<string> {
  const data: any = await client.post('/api/backtest/optimize', config)
  return data.task_id
}

/**
 * Query optimization status and results.
 * GET /backtest/optimize/{task_id}
 */
export async function getOptimizeStatus(taskId: string): Promise<{
  status: string
  progress: number
  results: OptimizeResult[]
  best_result?: any
  error?: string
}> {
  return client.get(`/api/backtest/optimize/${taskId}`) as any
}

/**
 * Stream optimization progress via WebSocket.
 * Falls back to polling when WebSocket is unavailable.
 */
export async function* streamOptimizeProgress(
  taskId: string,
): AsyncGenerator<{ progress: number; currentParams: Record<string, number>; bestResult?: OptimizeResult }> {
  let done = false

  try {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${proto}//${window.location.host}/ws/optimize/${taskId}`
    const ws = new WebSocket(wsUrl)

    // Wait for connection handshake
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve()
      ws.onerror = () => reject(new Error('WebSocket connection failed'))
      setTimeout(() => reject(new Error('WebSocket connection timeout')), 3000)
    })

    // Collect messages; resolves when a message arrives
    const msgQueue: string[] = []
    let msgRes: (() => void) | null = null
    const msgReady = new Promise<void>((resolve) => {
      msgRes = resolve
    })

    ws.onmessage = (event) => {
      if (done) return
      try {
        const msg = JSON.parse(event.data)
        // Skip connection handshake
        if (msg.type === 'connected') return
        msgQueue.push(event.data)
        msgRes?.()
      } catch { /* ignore parse errors */ }
    }

    ws.onclose = () => {
      // Drain remaining
      if (msgQueue.length > 0) msgRes?.()
    }

    // Stream messages until done
    while (!done) {
      if (msgQueue.length === 0) {
        try {
          await Promise.race([
            msgReady,
            new Promise<void>((_, reject) => setTimeout(() => reject(new Error('WS read timeout')), 15000)),
          ])
        } catch {
          // Timeout → fall back to polling
          break
        }
      }

      while (msgQueue.length > 0) {
        const raw = msgQueue.shift()!
        try {
          const msg = JSON.parse(raw)
          // Message format: { type: "progress"|"complete", data: { progress, best_result, ... }, task_id }
          // Also handle direct format: { type: "progress", progress, best_result }
          const inner = msg.data ?? msg
          if (inner.progress !== undefined) {
            yield {
              progress: inner.progress,
              currentParams: inner.current_params ?? {},
              bestResult: inner.best_result ?? undefined,
            }
          }
          if (msg.type === 'complete' || (inner.progress !== undefined && inner.progress >= 100)) {
            done = true
            break
          }
        } catch { /* ignore */ }
      }
    }

    ws.close()
  } catch {
    // WS unavailable → fall back to polling status
    yield* pollOptimizeStatus(taskId)
  }
}

/** Poll getOptimizeStatus every 2s until complete */
async function* pollOptimizeStatus(
  taskId: string,
): AsyncGenerator<{ progress: number; currentParams: Record<string, number>; bestResult?: OptimizeResult }> {
  while (true) {
    const status = await getOptimizeStatus(taskId)
    if (status.status === 'completed' || status.status === 'failed') {
      if (status.results && status.results.length > 0) {
        const sorted = [...status.results].sort((a: OptimizeResult, b: OptimizeResult) =>
          (b.metrics.sharpeRatio ?? 0) - (a.metrics.sharpeRatio ?? 0)
        )
        yield {
          progress: status.progress,
          currentParams: {},
          bestResult: sorted[0],
        }
      }
      return
    }
    const bestResult = status.results && status.results.length > 0
      ? [...status.results].sort((a: OptimizeResult, b: OptimizeResult) =>
          (b.metrics.sharpeRatio ?? 0) - (a.metrics.sharpeRatio ?? 0)
        )[0]
      : undefined
    yield {
      progress: status.progress,
      currentParams: {},
      bestResult,
    }
    if (status.progress >= 100) return
    await new Promise((r) => setTimeout(r, 2000))
  }
}
