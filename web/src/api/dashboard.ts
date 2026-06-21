import client from './client'

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
    client.get('/api/dashboard/metrics') as Promise<DashboardMetrics>,
  signals: () =>
    client.get('/api/dashboard/signals') as Promise<SignalItem[]>,
  recentBacktests: () =>
    client.get('/api/backtest') as Promise<any[]>,
  equityCurve: () =>
    client.get('/api/portfolio/equity-curve') as Promise<{ dates: string[]; values: number[] }>,
}

// Re-export backtestApi from backtest.ts to avoid duplicate definition
export { backtestApi } from './backtest'
