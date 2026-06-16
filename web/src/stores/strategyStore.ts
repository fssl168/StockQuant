import { create } from 'zustand'
import type { Strategy } from '@/types'
import { strategyApi } from '@/api/strategy'

interface StrategyState {
  strategies: Strategy[]
  loading: boolean
  fetchStrategies: () => Promise<void>
  createStrategy: (data: Omit<Strategy, 'id' | 'created_at' | 'updated_at'>) => Promise<void>
  updateStrategy: (id: string, data: { name: string; code: string }) => Promise<void>
  deleteStrategy: (id: string) => Promise<void>
  currentStrategy: Strategy | null
  setCurrentStrategy: (s: Strategy | null) => void
}

export const useStrategyStore = create<StrategyState>((set) => ({
  strategies: [],
  loading: false,
  currentStrategy: null,
  setCurrentStrategy: (s) => set({ currentStrategy: s }),
  fetchStrategies: async () => {
    set({ loading: true })
    try {
      const strategies = await strategyApi.list()
      set({ strategies, loading: false })
    } catch {
      set({ strategies: [], loading: false })
    }
  },
  createStrategy: async (data) => {
    try {
      const created = await strategyApi.create(data)
      set((st) => ({ strategies: [...st.strategies, created] }))
    } catch { /* ignore */ }
  },
  updateStrategy: async (id, data) => {
    await strategyApi.update(id, data)
    set((state) => ({
      strategies: state.strategies.map((s) => s.id === id ? { ...s, ...data } : s)
    }))
  },
  deleteStrategy: async (id) => {
    try {
      await strategyApi.delete(id)
      set((st) => ({
        strategies: st.strategies.filter((s) => s.id !== id),
        currentStrategy: st.currentStrategy?.id === id ? null : st.currentStrategy,
      }))
    } catch { /* ignore */ }
  },
}))
