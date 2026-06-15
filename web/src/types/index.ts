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

export interface BacktestMetrics {
  'Annualized Return'?: number
  'Max Drawdown'?: number
  'Sharpe Ratio'?: number
  'Sortino Ratio'?: number
  'Calmar Ratio'?: number
  'Win Rate'?: number
  'Total Trades'?: number
  'SQN (System Quality Number)'?: number
  'Omega Ratio'?: number
  'Information Ratio'?: number
  'Treynor Ratio'?: number
  'VaR (95%)'?: number
  'CVaR (95%)'?: number
  'Volatility (Annual)'?: number
  'Beta'?: number
  'Alpha'?: number
  'Max Drawdown Duration'?: number
  'Avg Drawdown'?: number
  'Avg Drawdown Recovery'?: number
  'Longest Win Streak'?: number
  'Longest Loss Streak'?: number
  'Profit Factor'?: number
  'Avg Win'?: number
  'Avg Loss'?: number
  'Avg Trade Return'?: number
  'Total Commission'?: number
  'Total Slippage'?: number
  'Monthly Returns'?: Record<string, number>
  [key: string]: unknown
}

export interface Trade {
  time: string
  symbol: string
  direction: string
  size: number
  price: number
  pnl?: number
}

export interface Signal {
  id: string
  symbol: string
  type: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  source: string
  reason: string
  timestamp: string
}

export interface Position {
  symbol: string
  name: string
  shares: number
  cost: number
  price: number
  pnl: number
  pnlPct: number
}

export interface Strategy {
  id: string
  name: string
  code: string
  description: string
  parameters: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export interface NotificationItem {
  id: string
  type: 'signal' | 'alert' | 'info'
  title: string
  message: string
  time: string
}

export interface MarketQuote {
  symbol: string
  price: number
  change: number
  changePct: number
  volume: number
  timestamp: string
}

export interface WSMessage {
  type: 'progress' | 'metrics' | 'trade' | 'alert' | 'quote'
  task_id?: string
  data: unknown
  timestamp: string
}

export interface SettingItem {
  key: string
  value: unknown
  overridden: boolean
  value_type: 'string' | 'number' | 'float' | 'boolean' | 'password' | 'select' | 'time' | 'lines'
  label: string
  description: string
  secret: boolean
  group_key: string
  group_label: string
  group_icon: string
  order: number
  min?: number
  max?: number
  step?: number
  scale?: number
  unit?: string
  slider?: boolean
  options?: { value: string; label: string }[]
  when?: { field: string; values: string[] }
}

export interface SettingGroup {
  key: string
  label: string
  icon: string
  count: number
  order: number
}

export interface DataSourceConfig {
  provider: string
  enabled: boolean
  api_key?: string
  api_url?: string
  tushare_token?: string
  tdx_host?: string
  tdx_port?: number
  duckdb_path?: string
  db_url?: string
}

export interface CacheStats {
  total_size_mb: number
  hit_rate: number
  last_update: string
  symbol_count: number
}
