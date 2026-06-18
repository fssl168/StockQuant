import { create } from 'zustand'
import type { CacheStats, DataSourceConfig } from '@/types'
import { dataApi } from '@/api/data'

interface DataState {
  sources: DataSourceConfig[]
  cacheStats: CacheStats | null
  loading: boolean
  fetchSources: () => Promise<void>
  fetchCacheStats: () => Promise<void>
}

export const useDataStore = create<DataState>((set) => ({
  sources: [],
  cacheStats: null,
  loading: false,
  fetchSources: async () => {
    try {
      const res: any = await dataApi.sources()
      const sources = Array.isArray(res) ? res : (res?.sources ?? res?.data ?? [])
      set({ sources })
    } catch {
      set({ sources: [] })
    }
  },
  fetchCacheStats: async () => {
    try {
      const res: any = await dataApi.cacheStats()
      // client 响应拦截器返回 axios response（数据在 .data）；兼容测试中直接返回裸数据
      const stats = res && typeof res === 'object' && 'data' in res ? res.data : res
      set({ cacheStats: stats })
    } catch {
      set({ cacheStats: null })
    }
  },
}))
