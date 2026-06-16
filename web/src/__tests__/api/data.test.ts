import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

import client from '@/api/client'
import { dataApi } from '@/api/data'

describe('Data API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ---- sources ----
  it('dataApi.sources should call GET /data/sources', async () => {
    const mockSources = [{ provider: 'tushare', enabled: true }]
    vi.mocked(client.get).mockResolvedValueOnce(mockSources)
    const result = await dataApi.sources()
    expect(client.get).toHaveBeenCalledWith('/data/sources')
    expect(result).toEqual(mockSources)
  })

  it('dataApi.sources should return empty array when no sources', async () => {
    vi.mocked(client.get).mockResolvedValueOnce([])
    const result = await dataApi.sources()
    expect(result).toEqual([])
  })

  // ---- updateSource ----
  it('dataApi.updateSource should call POST /data/sources with config', async () => {
    const mockConfig = { provider: 'tushare', enabled: true, tushare_token: 'xxx' }
    vi.mocked(client.post).mockResolvedValueOnce({ success: true })
    const result = await dataApi.updateSource(mockConfig)
    expect(client.post).toHaveBeenCalledWith('/data/sources', mockConfig)
    expect(result).toEqual({ success: true })
  })

  // ---- cacheStats ----
  it('dataApi.cacheStats should call GET /data/cache', async () => {
    const mockStats = { total_size_mb: 128.5, hit_rate: 0.85, last_update: '2024-01-01', symbol_count: 50 }
    vi.mocked(client.get).mockResolvedValueOnce(mockStats)
    const result = await dataApi.cacheStats()
    expect(client.get).toHaveBeenCalledWith('/data/cache')
    expect(result).toEqual(mockStats)
  })

  // ---- clearCache ----
  it('dataApi.clearCache should call DELETE /data/cache', async () => {
    vi.mocked(client.delete).mockResolvedValueOnce({ success: true })
    const result = await dataApi.clearCache()
    expect(client.delete).toHaveBeenCalledWith('/data/cache')
    expect(result).toEqual({ success: true })
  })

  it('dataApi.clearCache should propagate error', async () => {
    vi.mocked(client.delete).mockRejectedValueOnce(new Error('Clear failed'))
    await expect(dataApi.clearCache()).rejects.toThrow('Clear failed')
  })

  // ---- fetchKline ----
  it('dataApi.fetchKline should call GET /data/kline with query params', async () => {
    const mockKline = [{ date: '2024-01-01', open: 100, close: 105 }]
    vi.mocked(client.get).mockResolvedValueOnce(mockKline)
    const result = await dataApi.fetchKline('sh600519', 'tushare', '2024-01-01', '2024-12-31')
    expect(client.get).toHaveBeenCalledWith('/data/kline?symbol=sh600519&source=tushare&start=2024-01-01&end=2024-12-31')
    expect(result).toEqual(mockKline)
  })

  it('dataApi.fetchKline should propagate server error', async () => {
    vi.mocked(client.get).mockRejectedValueOnce(new Error('Bad request'))
    await expect(dataApi.fetchKline('invalid', 'src', '', '')).rejects.toThrow('Bad request')
  })
})
