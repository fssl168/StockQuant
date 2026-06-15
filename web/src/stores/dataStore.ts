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
      const sources = await dataApi.sources()
      set({ sources })
    } catch {
      set({ sources: [] })
    }
  },
  fetchCacheStats: async () => {
    try {
      const stats = await dataApi.cacheStats()
      set({ cacheStats: stats })
    } catch {
      set({ cacheStats: null })
    }
  },
}))
