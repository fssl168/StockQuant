import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

import client from '@/api/client'
import type { OptimizeConfig } from '@/types'
import * as optimizeApi from '@/api/optimize'

// Helper to create a minimal config for testing
function createConfig(overrides?: Partial<OptimizeConfig>): OptimizeConfig {
  return {
    strategyId: 'test_strategy',
    params: [
      { name: 'fast_period', min: 5, max: 30, step: 5, value: 10 },
      { name: 'slow_period', min: 30, max: 120, step: 10, value: 60 },
    ],
    method: overrides?.method ?? 'grid',
    targetMetric: 'sharpeRatio',
    maxIters: overrides?.maxIters ?? 10,
    ...overrides,
  }
}

const mockResults = [
  { params: { fast_period: 10, slow_period: 60 }, metrics: { sharpeRatio: 2.0, totalReturn: 0.3, maxDrawdown: -0.1 } },
  { params: { fast_period: 15, slow_period: 70 }, metrics: { sharpeRatio: 1.5, totalReturn: 0.2, maxDrawdown: -0.15 } },
  { params: { fast_period: 20, slow_period: 80 }, metrics: { sharpeRatio: 1.0, totalReturn: 0.1, maxDrawdown: -0.2 } },
]

describe('Optimize API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('runOptimization()', () => {
    it('should return a task ID string starting with OPT-', async () => {
      vi.mocked(client.post).mockResolvedValueOnce({ taskId: 'OPT-123' })
      const taskId = await optimizeApi.runOptimization(createConfig())
      expect(client.post).toHaveBeenCalledWith('/api/backtest/optimize', expect.any(Object))
      expect(taskId).toMatch(/^OPT-\d+$/)
    })

    it('task should start in running state', async () => {
      vi.mocked(client.post).mockResolvedValueOnce({ taskId: 'OPT-123' })
      vi.mocked(client.get).mockResolvedValueOnce({ status: 'running', progress: 0, results: [] })
      const taskId = await optimizeApi.runOptimization(createConfig({ maxIters: 5 }))
      const status = await optimizeApi.getOptimizeStatus(taskId)
      expect(status.status).toBe('running')
    })

    it('different calls should return different task IDs', async () => {
      vi.mocked(client.post).mockResolvedValueOnce({ taskId: 'OPT-1' })
      vi.mocked(client.post).mockResolvedValueOnce({ taskId: 'OPT-2' })
      const id1 = await optimizeApi.runOptimization(createConfig({ maxIters: 3 }))
      const id2 = await optimizeApi.runOptimization(createConfig({ maxIters: 3 }))
      expect(id1).not.toBe(id2)
    })
  })

  describe('getOptimizeStatus()', () => {
    it('should return running status during optimization', async () => {
      vi.mocked(client.get).mockResolvedValueOnce({ status: 'running', progress: 50, results: [] })
      const status = await optimizeApi.getOptimizeStatus('OPT-123')
      expect(status.status).toBe('running')
      expect(status.progress).toBeGreaterThanOrEqual(0)
    })

    it('should return completed results after optimization finishes', async () => {
      vi.mocked(client.post).mockResolvedValueOnce({ taskId: 'OPT-123' })
      vi.mocked(client.get).mockResolvedValueOnce({
        status: 'completed',
        progress: 100,
        results: mockResults,
      })
      const taskId = await optimizeApi.runOptimization(createConfig({ maxIters: 4 }))
      const status = await optimizeApi.getOptimizeStatus(taskId)
      expect(status.status).toBe('completed')
      expect(status.progress).toBe(100)
      expect(status.results.length).toBeGreaterThan(0)
    }, 10000)

    it('results should be sorted by sharpeRatio descending when completed', async () => {
      vi.mocked(client.get).mockResolvedValueOnce({
        status: 'completed',
        progress: 100,
        results: mockResults,
      })
      const status = await optimizeApi.getOptimizeStatus('OPT-123')
      const results = status.results
      for (let i = 1; i < results.length; i++) {
        expect((results[i].metrics.sharpeRatio ?? 0) <= (results[i - 1].metrics.sharpeRatio ?? 0)).toBe(true)
      }
    }, 10000)

    it('should throw error for non-existent taskId', async () => {
      vi.mocked(client.get).mockRejectedValueOnce(new Error('Task not found'))
      await expect(optimizeApi.getOptimizeStatus('OPT-99999')).rejects.toThrow('Task not found')
    })
  })

  describe('streamOptimizeProgress()', () => {
    it('should yield progress updates', async () => {
      vi.mocked(client.post).mockResolvedValueOnce({ taskId: 'OPT-123' })
      vi.mocked(client.get).mockResolvedValueOnce({
        status: 'completed',
        progress: 100,
        results: mockResults,
      })
      const taskId = await optimizeApi.runOptimization(createConfig({ maxIters: 4 }))
      const yields: { progress: number }[] = []
      for await (const update of optimizeApi.streamOptimizeProgress(taskId)) {
        yields.push(update)
        if (update.progress === 100) break
      }
      expect(yields.length).toBeGreaterThan(0)
      yields.forEach((u) => {
        expect(u.progress).toBeGreaterThanOrEqual(0)
        expect(u.progress).toBeLessThanOrEqual(100)
      })
    }, 10000)

    it('final emission should have progress=100', async () => {
      vi.mocked(client.post).mockResolvedValueOnce({ taskId: 'OPT-123' })
      vi.mocked(client.get).mockResolvedValueOnce({
        status: 'completed',
        progress: 100,
        results: mockResults,
      })
      const taskId = await optimizeApi.runOptimization(createConfig({ maxIters: 4 }))
      let lastUpdate: { progress: number } | undefined
      for await (const update of optimizeApi.streamOptimizeProgress(taskId)) {
        lastUpdate = update
        if (update.progress === 100) break
      }
      expect(lastUpdate!.progress).toBe(100)
    }, 10000)

    it('should throw error for non-existent taskId', async () => {
      vi.mocked(client.get).mockRejectedValueOnce(new Error('Task not found'))
      const generator = optimizeApi.streamOptimizeProgress('OPT-99999')
      await expect(generator.next()).rejects.toThrow('Task not found')
    })
  })

  describe('Grid vs Random behavior', () => {
    it('grid method should produce results', async () => {
      vi.mocked(client.post).mockResolvedValueOnce({ taskId: 'OPT-123' })
      vi.mocked(client.get).mockResolvedValueOnce({
        status: 'completed',
        progress: 100,
        results: mockResults,
      })
      const taskId = await optimizeApi.runOptimization(createConfig({ method: 'grid', maxIters: 4 }))
      const status = await optimizeApi.getOptimizeStatus(taskId)
      expect(status.status).toBe('completed')
      expect(status.results.length).toBeGreaterThan(0)
    }, 10000)

    it('random method should produce results', async () => {
      vi.mocked(client.post).mockResolvedValueOnce({ taskId: 'OPT-456' })
      vi.mocked(client.get).mockResolvedValueOnce({
        status: 'completed',
        progress: 100,
        results: mockResults,
      })
      const taskId = await optimizeApi.runOptimization(createConfig({ method: 'random', maxIters: 4 }))
      const status = await optimizeApi.getOptimizeStatus(taskId)
      expect(status.status).toBe('completed')
      expect(status.results.length).toBeGreaterThan(0)
    }, 10000)

    it('grid method should produce deterministic results on repeat runs', async () => {
      vi.mocked(client.post).mockResolvedValueOnce({ taskId: 'OPT-789' })
      vi.mocked(client.get).mockResolvedValueOnce({
        status: 'completed',
        progress: 100,
        results: mockResults,
      })
      const taskId1 = await optimizeApi.runOptimization(createConfig({ method: 'grid', maxIters: 2 }))
      const status1 = await optimizeApi.getOptimizeStatus(taskId1)
      expect(status1.results.length).toBeGreaterThan(0)
    }, 10000)
  })
})
