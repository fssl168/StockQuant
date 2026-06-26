import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

import client from '@/api/client'
import { backtestApi } from '@/api/backtest'

describe('Backtest API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ---- list ----
  it('backtestApi.list should call GET /api/backtest', async () => {
    const mockList = [{ taskId: 't1', status: 'completed' }]
    vi.mocked(client.get).mockResolvedValueOnce(mockList)
    const result = await backtestApi.list()
    expect(client.get).toHaveBeenCalledWith('/api/backtest')
    expect(result).toEqual(mockList)
  })

  it('backtestApi.list should return empty array when no backtests', async () => {
    vi.mocked(client.get).mockResolvedValueOnce([])
    const result = await backtestApi.list()
    expect(result).toEqual([])
  })

  // ---- get ----
  it('backtestApi.get should call GET /api/backtest/:id', async () => {
    const mockTask = { taskId: 'test-1', status: 'completed', strategyName: 'Dual MA' }
    vi.mocked(client.get).mockResolvedValueOnce(mockTask)
    const result = await backtestApi.get('test-1')
    expect(client.get).toHaveBeenCalledWith('/api/backtest/test-1')
    expect(result).toEqual(mockTask)
  })

  it('backtestApi.get should propagate error for invalid id', async () => {
    vi.mocked(client.get).mockRejectedValueOnce(new Error('Not found'))
    await expect(backtestApi.get('invalid')).rejects.toThrow('Not found')
  })

  // ---- submit ----
  it('backtestApi.submit should call POST /api/backtest with payload', async () => {
    const mockResponse = { taskId: 'task-1', status: 'pending' }
    vi.mocked(client.post).mockResolvedValueOnce(mockResponse)
    const payload = {
      strategyName: 'test',
      symbols: ['sh600519'],
      startDate: '2024-01-01',
      endDate: '2024-12-31',
      cash: 1000000,
      strategyCode: 'code',
      commissionType: 'ashare',
      slippageType: 'none',
      equityCurve: [] as unknown[],
    }
    const result = await backtestApi.submit(payload)
    expect(client.post).toHaveBeenCalledWith('/api/backtest', payload)
    expect(result).toEqual(mockResponse)
  })

  it('backtestApi.submit should propagate server validation error', async () => {
    vi.mocked(client.post).mockRejectedValueOnce(new Error('Invalid strategy'))
    await expect(
      backtestApi.submit({
        strategyName: '',
        symbols: [],
        startDate: '',
        endDate: '',
        cash: 0,
        strategyCode: '',
        commissionType: '',
        slippageType: '',
        equityCurve: [],
      })
    ).rejects.toThrow('Invalid strategy')
  })
})
