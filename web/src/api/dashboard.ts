import client from './client'
import type { BacktestMetrics, Trade } from '@/types'

export interface DashboardMetrics {
  total_assets: number
  today_pnl: number
  position_count: number
  backtest_count: number
  annualized_return: number
  max_drawdown: number
  sharpe_ratio: number
  volatility: number
}

export interface SignalItem {
  id: string
  symbol: string
  type: string
  confidence: number
  source: string
  reason: string
  timestamp: string
}

export const dashboardApi = {
  metrics: () =>
    client.get('/dashboard/metrics') as Promise<DashboardMetrics>,
  signals: () =>
    client.get('/dashboard/signals') as Promise<SignalItem[]>,
  recentBacktests: () =>
    client.get('/backtest?limit=20') as Promise<any[]>,
  equityCurve: () =>
    client.get('/portfolio/equity-curve') as Promise<{ dates: string[]; values: number[] }>,
}

export const backtestApi = {
  list: (limit = 20) =>
    client.get(`/backtest?limit=${limit}`) as Promise<any[]>,
  get: (id: string) =>
    client.get(`/backtest/${id}`) as Promise<{
      task_id: string
      status: string
      strategy_name: string
      metrics: BacktestMetrics
      trades: Trade[]
      equity_curve: number[]
      error: string | null
    }>,
  submit: (data: {
    strategy_name: string
    symbols: string[]
    start_date: string
    end_date: string
    cash: number
    strategy_code: string
    commission_type: string
    slippage_type: string
  }) =>
    client.post('/backtest', data) as Promise<{ task_id: string; status: string }>,
  delete: (id: string) =>
    client.delete(`/backtest/${id}`) as Promise<void>,
}
