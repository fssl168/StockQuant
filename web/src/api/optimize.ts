import client from './client'
import { OptimizeConfig, OptimizeResult } from '../types'

const USE_MOCK = !import.meta.env.VITE_API_URL

// ── Mock Optimizer Engine ────────────────────────────────────

interface OptimizeTask {
  id: string
  config: OptimizeConfig
  status: 'running' | 'completed' | 'error'
  progress: number
  results: OptimizeResult[]
  startedAt: number
}

let taskIdCounter = 0
let globalGridCounter = 0
const activeTasks = new Map<string, OptimizeTask>()

function generateResult(rank: number, params: Record<string, number>): OptimizeResult {
  const sharpe = Number((0.8 + Math.random() * 1.4).toFixed(2))
  const ret = Number((10 + Math.random() * 55).toFixed(1))
  const dd = Number((-(5 + Math.random() * 22)).toFixed(1))
  const wr = Number((45 + Math.random() * 35).toFixed(1))
  const nTrades = Math.floor(20 + Math.random() * 250)

  return {
    rank,
    params,
    metrics: {
      sharpeRatio: sharpe,
      totalReturn: ret,
      maxDrawdown: dd,
      winRate: wr,
      totalTrades: nTrades,
    },
  }
}

function sampleParams(config: OptimizeConfig): Record<string, number> {
  const result: Record<string, number> = {}
  for (const p of config.params) {
    const step = p.step ?? 1
    const range = p.max - p.min
    const steps = Math.floor(range / step)
    if (config.method === 'grid') {
      const pickIndex = globalGridCounter % (steps + 1)
      result[p.name] = p.min + pickIndex * step
      globalGridCounter = Math.floor(globalGridCounter / (steps + 1))
    } else {
      // Random sampling
      result[p.name] = p.min + Math.floor(Math.random() * (steps + 1)) * step
    }
  }
  return result
}

// ── Mock Implementations ──────────────────────────────────────

async function mockRunOptimization(config: OptimizeConfig): Promise<string> {
  const taskId = `OPT-${++taskIdCounter}`
  const totalIters = config.maxIters ?? 20

  const task: OptimizeTask = {
    id: taskId,
    config,
    status: 'running',
    progress: 0,
    results: [],
    startedAt: Date.now(),
  }
  activeTasks.set(taskId, task)

  // Simulate async optimization with incremental results
  let completed = 0
  const interval = setInterval(() => {
    if (completed >= totalIters) {
      clearInterval(interval)
      task.status = 'completed'
      task.progress = 100
      // Sort by sharpe descending and assign ranks
      task.results.sort((a, b) => (b.metrics.sharpeRatio ?? 0) - (a.metrics.sharpeRatio ?? 0))
      task.results.forEach((r, i) => { r.rank = i + 1 })
      return
    }

    const batchSize = config.method === 'grid' ? 2 : 1
    for (let i = 0; i < batchSize && completed < totalIters; i++) {
      completed++
      task.results.push(generateResult(completed, sampleParams(config)))
    }
    task.progress = Math.round((completed / totalIters) * 100)
  }, 400)

  return taskId
}

async function mockGetOptimizeStatus(taskId: string): Promise<{
  status: string
  progress: number
  results: OptimizeResult[]
}> {
  const task = activeTasks.get(taskId)
  if (!task) throw new Error('Task not found')
  return {
    status: task.status,
    progress: task.progress,
    results: [...task.results],
  }
}

async function* mockStreamOptimizeProgress(
  taskId: string,
): AsyncGenerator<{ progress: number; currentParams: Record<string, number>; bestResult?: OptimizeResult }> {
  const task = activeTasks.get(taskId)
  if (!task) throw new Error('Task not found')

  while (task.status === 'running') {
    await new Promise((resolve) => setTimeout(resolve, 450))

    const latest = task.results[task.results.length - 1]
    const sorted = [...task.results].sort((a, b) => (b.metrics.sharpeRatio ?? 0) - (a.metrics.sharpeRatio ?? 0))
    yield {
      progress: task.progress,
      currentParams: latest?.params ?? {},
      bestResult: sorted[0],
    }
  }

  // Final emission
  const sorted = [...task.results].sort((a, b) => (b.metrics.sharpeRatio ?? 0) - (a.metrics.sharpeRatio ?? 0))
  yield {
    progress: 100,
    currentParams: {},
    bestResult: sorted[0],
  }
}

// ── API Functions ────────────────────────────────────────────

/**
 * Run optimization — returns task ID for polling/streaming.
 */
export async function runOptimization(config: OptimizeConfig): Promise<string> {
  if (USE_MOCK) return mockRunOptimization(config)
  const data: any = await client.post('/backtest/optimize', config)
  return data.task_id
}

export async function getOptimizeStatus(taskId: string): Promise<{
  status: string
  progress: number
  results: OptimizeResult[]
}> {
  if (USE_MOCK) return mockGetOptimizeStatus(taskId)
  return client.get(`/backtest/optimize/${taskId}`) as any
}

/**
 * Stream optimization progress via async generator.
 * Yields a result object every ~400ms until completion.
 * SSE streaming requires backend support — mock only for now.
 */
export async function* streamOptimizeProgress(
  taskId: string,
): AsyncGenerator<{ progress: number; currentParams: Record<string, number>; bestResult?: OptimizeResult }> {
  if (USE_MOCK) {
    yield* mockStreamOptimizeProgress(taskId)
    return
  }
  // TODO: Replace with real SSE streaming when backend supports it
  yield* mockStreamOptimizeProgress(taskId)
}
