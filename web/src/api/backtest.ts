import client from './client'

export interface BacktestTask {
  task_id: string
  status: string
  strategy_name: string
  strategy_code: string
  symbols: string[]
  start_date: string
  end_date: string
  cash: number
  commission_type: string
  slippage_type: string
  created_at: string
  updated_at: string
  metrics: Record<string, unknown>
  trades: unknown[]
  equity_curve: unknown[]
  error: string | null
}

export const backtestApi = {
  list: () => client.get('/api/backtest') as Promise<BacktestTask[]>,
  get: (id: string) => client.get(`/api/backtest/${id}`) as Promise<BacktestTask>,
  submit: (data: Omit<BacktestTask, 'task_id' | 'status' | 'created_at' | 'updated_at' | 'metrics' | 'trades' | 'error'>) =>
    client.post('/api/backtest', data) as Promise<{ task_id: string; status: string }>,
}
