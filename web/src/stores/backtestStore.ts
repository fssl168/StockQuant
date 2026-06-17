import { create } from 'zustand'
import { backtestApi, type BacktestTask } from '@/api/backtest'

interface BacktestState {
  tasks: BacktestTask[]
  loading: boolean
  fetchTasks: () => Promise<void>
  submitTask: (data: Partial<BacktestTask>) => Promise<void>
}

export const useBacktestStore = create<BacktestState>((set, get) => ({
  tasks: [],
  loading: false,
  fetchTasks: async () => {
    set({ loading: true })
    try {
      const res: any = await backtestApi.list()
      const tasks = Array.isArray(res) ? res : (res?.tasks ?? res?.data ?? [])
      set({ tasks, loading: false })
    } catch {
      set({ tasks: [], loading: false })
    }
  },
  submitTask: async (data) => {
    set({ loading: true })
    try {
      await backtestApi.submit(data as any)
      await get().fetchTasks()
    } catch {
      set({ loading: false })
    }
  },
}))
