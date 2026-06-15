import { Typography } from 'antd'
import type { BacktestMetrics } from '@/types'

const { Text } = Typography

interface MetricTableProps {
  metrics: BacktestMetrics
}

const METRIC_GROUPS = [
  {
    label: '收益指标',
    keys: ['Annualized Return', '累计收益率', 'Alpha', 'Beta'],
  },
  {
    label: '风险指标',
    keys: ['Max Drawdown', 'Max Drawdown Duration', 'Avg Drawdown', 'VaR (95%)', 'CVaR (95%)', 'Volatility (Annual)'],
  },
  {
    label: '风险调整收益',
    keys: ['Sharpe Ratio', 'Sortino Ratio', 'Calmar Ratio', 'Omega Ratio', 'Information Ratio', 'Treynor Ratio'],
  },
  {
    label: '交易统计',
    keys: ['Total Trades', 'Win Rate', 'Profit Factor', 'Avg Win', 'Avg Loss', 'Longest Win Streak', 'Longest Loss Streak', 'SQN (System Quality Number)'],
  },
  {
    label: '费用',
    keys: ['Total Commission', 'Total Slippage', 'Avg Trade Return'],
  },
]

function formatMetric(key: string, value: unknown): React.ReactNode {
  if (value === null || value === undefined) return <Text type="secondary">—</Text>

  const num = typeof value === 'number' ? value : parseFloat(String(value))
  if (isNaN(num)) return <Text>{String(value)}</Text>

  const isPct = ['Annualized Return', '累计收益率', 'Win Rate', 'VaR (95%)', 'CVaR (95%)'].includes(key)
  const suffix = isPct ? '%' : ''

  const colorMap: Record<string, string> = {
    'Annualized Return': num >= 0 ? '#10b981' : '#ef4444',
    'Win Rate': num >= 50 ? '#10b981' : '#f59e0b',
    'Max Drawdown': '#ef4444',
    'Sharpe Ratio': num >= 1 ? '#10b981' : num >= 0 ? '#f59e0b' : '#ef4444',
  }

  return (
    <Text style={{ color: colorMap[key] || 'var(--color-text-primary)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
      {num.toFixed(2)}{suffix}
    </Text>
  )
}

export default function MetricTable({ metrics }: MetricTableProps) {
  const allKeys = new Set(METRIC_GROUPS.flatMap((g) => g.keys))
  const rows = Array.from(allKeys).map((key) => ({ key, value: metrics[key] }))

  return (
    <div style={{ padding: 16 }}>
      {METRIC_GROUPS.map((group) => {
        const visibleRows = rows.filter((r) => group.keys.includes(r.key) && r.value != null)
        if (visibleRows.length === 0) return null
        return (
          <div key={group.label} style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8, fontWeight: 600 }}>
              {group.label}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 8 }}>
              {visibleRows.map((r) => (
                <div
                  key={r.key}
                  style={{
                    background: 'var(--color-bg-hover)',
                    borderRadius: 6,
                    padding: '8px 12px',
                    border: '1px solid var(--color-border-default)',
                  }}
                >
                  <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginBottom: 4 }}>{r.key}</div>
                  {formatMetric(r.key, r.value)}
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
