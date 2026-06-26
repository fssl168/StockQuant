import { create } from 'zustand'
import { backtestApi, type BacktestTask } from '@/api/backtest'

interface BacktestSubmitResult {
  taskId: string
  status: string
  createdAt?: string
}

interface BacktestState {
  tasks: BacktestTask[]
  loading: boolean
  fetchTasks: () => Promise<void>
  submitTask: (data: Partial<BacktestTask>) => Promise<BacktestSubmitResult>
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
      const result = await backtestApi.submit(data as any) as BacktestSubmitResult
      await get().fetchTasks()
      return result
    } catch (e) {
      set({ loading: false })
      throw e
    }
  },
}))
