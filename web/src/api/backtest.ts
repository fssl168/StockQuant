import client from './client'

export interface BacktestTask {
  taskId: string
  status: string
  strategyName: string
  strategyCode: string
  symbols: string[]
  startDate: string
  endDate: string
  cash: number
  commissionType: string
  slippageType: string
  createdAt: string
  updatedAt: string
  metrics: Record<string, unknown>
  trades: unknown[]
  equityCurve: unknown[]
  error: string | null
}

export const backtestApi = {
  list: () => client.get('/api/backtest') as Promise<BacktestTask[]>,
  get: (id: string) => client.get(`/api/backtest/${id}`) as Promise<BacktestTask>,
  submit: (data: Omit<BacktestTask, 'taskId' | 'status' | 'createdAt' | 'updatedAt' | 'metrics' | 'trades' | 'error'>) =>
    client.post('/api/backtest', data) as Promise<{ taskId: string; status: string }>,
}
