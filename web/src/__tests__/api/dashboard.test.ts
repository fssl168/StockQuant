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
  it('dashboardApi.metrics should call GET /api/dashboard/metrics', async () => {
    const mockData = {
      totalAssets: 1234567,
      todayPnl: 12345,
      positionCount: 5,
      backtestCount: 10,
      annualizedReturn: 0.15,
      maxDrawdown: 0.08,
      sharpeRatio: 1.5,
      volatility: 0.2,
    }
    vi.mocked(client.get).mockResolvedValueOnce(mockData)
    const result = await dashboardApi.metrics()
    expect(client.get).toHaveBeenCalledWith('/api/dashboard/metrics')
    expect(result).toEqual(mockData)
  })

  it('dashboardApi.metrics should propagate network error', async () => {
    vi.mocked(client.get).mockRejectedValueOnce(new Error('Network error'))
    await expect(dashboardApi.metrics()).rejects.toThrow('Network error')
  })

  // ---- signals ----
  it('dashboardApi.signals should call GET /api/dashboard/signals', async () => {
    const mockSignals = [
      { id: '1', symbol: 'sh600519', type: 'BUY', confidence: 0.9, source: 'ai', reason: 'test', timestamp: '2024-01-01' },
    ]
    vi.mocked(client.get).mockResolvedValueOnce(mockSignals)
    const result = await dashboardApi.signals()
    expect(client.get).toHaveBeenCalledWith('/api/dashboard/signals')
    expect(result).toEqual(mockSignals)
  })

  it('dashboardApi.signals should return empty array when no signals', async () => {
    vi.mocked(client.get).mockResolvedValueOnce([])
    const result = await dashboardApi.signals()
    expect(result).toEqual([])
  })

  // ---- recentBacktests ----
  it('dashboardApi.recentBacktests should call GET /api/backtest', async () => {
    vi.mocked(client.get).mockResolvedValueOnce([])
    await dashboardApi.recentBacktests()
    expect(client.get).toHaveBeenCalledWith('/api/backtest')
  })

  it('dashboardApi.recentBacktests should return backtest list', async () => {
    const mockList = [{ taskId: 't1', status: 'completed', strategyName: 'test' }]
    vi.mocked(client.get).mockResolvedValueOnce(mockList)
    const result = await dashboardApi.recentBacktests()
    expect(result).toEqual(mockList)
  })

  it('dashboardApi.recentBacktests should propagate server error', async () => {
    vi.mocked(client.get).mockRejectedValueOnce(new Error('Server error'))
    await expect(dashboardApi.recentBacktests()).rejects.toThrow('Server error')
  })
})
