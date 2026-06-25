import { create } from "zustand"
import type { CacheStats, DataSourceConfig } from "@/types"
import { dataApi } from "@/api/data"

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
      // Backend returns a plain array of DataSourceConfig[]
      const sources = Array.isArray(res) ? res : (res?.sources ?? res?.data ?? [])
      set({ sources })
    } catch {
      set({ sources: [] })
    }
  },
  fetchCacheStats: async () => {
    try {
      const res: any = await dataApi.cacheStats()
      // Backend returns { size_mb, hit_rate, symbol_count, last_update } directly
      // client interceptor returns snakeToCamel-transformed data already
      // Handle both direct object and nested response formats
      let stats: any = null
      if (res && typeof res === "object") {
        // If response has a "data" field, unwrap it
        if ("data" in res && typeof res.data === "object") {
          stats = res.data
        } else {
          stats = res
        }
      }
      // Normalize camelCase keys to match CacheStats type (sizeMb, hitRate, symbolCount)
      // snakeToCamel converts size_mb -> sizeMb, hit_rate -> hitRate, etc.
      set({ cacheStats: stats })
    } catch {
      set({ cacheStats: null })
    }
  },
}))
