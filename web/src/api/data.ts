import client from './client'
import type { DataSourceConfig, CacheStats } from '@/types'

export const dataApi = {
  sources: () =>
    client.get('/data/sources') as Promise<DataSourceConfig[]>,
  updateSource: (data: DataSourceConfig) =>
    client.post('/data/sources', data) as Promise<{ success: boolean }>,
  cacheStats: () =>
    client.get('/data/cache') as Promise<CacheStats>,
  clearCache: () =>
    client.delete('/data/cache') as Promise<{ success: boolean }>,
  fetchKline: (symbol: string, source: string, start: string, end: string) =>
    client.get(`/data/kline?symbol=${symbol}&source=${source}&start=${start}&end=${end}`) as Promise<any[]>,
}
