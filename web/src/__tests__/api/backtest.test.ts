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
  it('backtestApi.list should call GET /backtest', async () => {
    const mockList = [{ task_id: 't1', status: 'completed' }]
    vi.mocked(client.get).mockResolvedValueOnce(mockList)
    const result = await backtestApi.list()
    expect(client.get).toHaveBeenCalledWith('/backtest')
    expect(result).toEqual(mockList)
  })

  it('backtestApi.list should return empty array when no backtests', async () => {
    vi.mocked(client.get).mockResolvedValueOnce([])
    const result = await backtestApi.list()
    expect(result).toEqual([])
  })

  // ---- get ----
  it('backtestApi.get should call GET /backtest/:id', async () => {
    const mockTask = { task_id: 'test-1', status: 'completed', strategy_name: 'Dual MA' }
    vi.mocked(client.get).mockResolvedValueOnce(mockTask)
    const result = await backtestApi.get('test-1')
    expect(client.get).toHaveBeenCalledWith('/backtest/test-1')
    expect(result).toEqual(mockTask)
  })

  it('backtestApi.get should propagate error for invalid id', async () => {
    vi.mocked(client.get).mockRejectedValueOnce(new Error('Not found'))
    await expect(backtestApi.get('invalid')).rejects.toThrow('Not found')
  })

  // ---- submit ----
  it('backtestApi.submit should call POST /backtest with payload', async () => {
    const mockResponse = { task_id: 'task-1', status: 'pending' }
    vi.mocked(client.post).mockResolvedValueOnce(mockResponse)
    const payload = {
      strategy_name: 'test',
      symbols: ['sh600519'],
      start_date: '2024-01-01',
      end_date: '2024-12-31',
      cash: 1000000,
      strategy_code: 'code',
      commission_type: 'ashare',
      slippage_type: 'none',
      equity_curve: [] as unknown[],
    }
    const result = await backtestApi.submit(payload)
    expect(client.post).toHaveBeenCalledWith('/backtest', payload)
    expect(result).toEqual(mockResponse)
  })

  it('backtestApi.submit should propagate server validation error', async () => {
    vi.mocked(client.post).mockRejectedValueOnce(new Error('Invalid strategy'))
    await expect(
      backtestApi.submit({
        strategy_name: '',
        symbols: [],
        start_date: '',
        end_date: '',
        cash: 0,
        strategy_code: '',
        commission_type: '',
        slippage_type: '',
        equity_curve: [],
      })
    ).rejects.toThrow('Invalid strategy')
  })
})
