import client from './client'
import type { DataSourceConfig, CacheStats } from '@/types'

export interface DataHealthEntry {
  provider: string
  name: string
  enabled: boolean
  healthy: boolean
  last_check: string
  error: string
}

export const dataApi = {
  sources: () =>
    client.get('/api/data/sources') as Promise<DataSourceConfig[]>,
  updateSource: (data: DataSourceConfig) =>
    client.post('/api/data/sources', data) as Promise<{ success: boolean }>,
  cacheStats: () =>
    client.get('/api/data/cache') as Promise<CacheStats>,
  clearCache: () =>
    client.delete('/api/data/cache') as Promise<{ success: boolean }>,
  fetchKline: (symbol: string, source: string, start: string, end: string) =>
    client.get(`/api/data/kline?symbol=${symbol}&source=${source}&start=${start}&end=${end}`) as Promise<{
      symbol: string; start: string; end: string; data: any[]; source?: string; cached?: boolean; error?: string;
    }>,
  collect: (data: { symbol: string; source: string; start: string; end: string }) =>
    client.post('/api/data/collect', data) as Promise<{ success: boolean }>,
  health: () =>
    client.get('/api/data/health') as Promise<DataHealthEntry[]>,
}
