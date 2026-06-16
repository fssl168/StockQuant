import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock axios client — interceptor (r => r.data) is bypassed in mock,
// so client.get/post return whatever we resolve with directly.
vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

import client from '@/api/client'
import { dashboardApi } from '@/api/dashboard'

describe('Dashboard API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ---- metrics ----
  it('dashboardApi.metrics should call GET /dashboard/metrics', async () => {
    const mockData = {
      total_assets: 1234567,
      today_pnl: 12345,
      position_count: 5,
      backtest_count: 10,
      annualized_return: 0.15,
      max_drawdown: 0.08,
      sharpe_ratio: 1.5,
      volatility: 0.2,
    }
    vi.mocked(client.get).mockResolvedValueOnce(mockData)
    const result = await dashboardApi.metrics()
    expect(client.get).toHaveBeenCalledWith('/dashboard/metrics')
    expect(result).toEqual(mockData)
  })

  it('dashboardApi.metrics should propagate network error', async () => {
    vi.mocked(client.get).mockRejectedValueOnce(new Error('Network error'))
    await expect(dashboardApi.metrics()).rejects.toThrow('Network error')
  })

  // ---- signals ----
  it('dashboardApi.signals should call GET /dashboard/signals', async () => {
    const mockSignals = [
      { id: '1', symbol: 'sh600519', type: 'BUY', confidence: 0.9, source: 'ai', reason: 'test', timestamp: '2024-01-01' },
    ]
    vi.mocked(client.get).mockResolvedValueOnce(mockSignals)
    const result = await dashboardApi.signals()
    expect(client.get).toHaveBeenCalledWith('/dashboard/signals')
    expect(result).toEqual(mockSignals)
  })

  it('dashboardApi.signals should return empty array when no signals', async () => {
    vi.mocked(client.get).mockResolvedValueOnce([])
    const result = await dashboardApi.signals()
    expect(result).toEqual([])
  })

  // ---- recentBacktests ----
  it('dashboardApi.recentBacktests should call GET /backtest?limit=20', async () => {
    vi.mocked(client.get).mockResolvedValueOnce([])
    await dashboardApi.recentBacktests()
    expect(client.get).toHaveBeenCalledWith('/backtest?limit=20')
  })

  it('dashboardApi.recentBacktests should return backtest list', async () => {
    const mockList = [{ task_id: 't1', status: 'completed', strategy_name: 'test' }]
    vi.mocked(client.get).mockResolvedValueOnce(mockList)
    const result = await dashboardApi.recentBacktests()
    expect(result).toEqual(mockList)
  })

  it('dashboardApi.recentBacktests should propagate server error', async () => {
    vi.mocked(client.get).mockRejectedValueOnce(new Error('Server error'))
    await expect(dashboardApi.recentBacktests()).rejects.toThrow('Server error')
  })
})
