import { Card } from 'antd'
import ReactECharts from 'echarts-for-react'

interface PnLTableProps {
  positions: Array<{
    symbol: string
    name: string
    pnl: number
    pnlPct: number
  }>
  height?: number
}

export default function PnLTable({ positions, height = 160 }: PnLTableProps) {
  const pnlData = positions.map((p) => ({
    name: p.symbol,
    value: p.pnl,
    itemStyle: { color: p.pnl >= 0 ? 'var(--color-success)' : 'var(--color-danger)' },
  }))

  return (
    <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>盈亏分布</span>} styles={{ body: { padding: '12px' } }} style={{ marginTop: 12 }}>
      <ReactECharts
        option={{
          tooltip: { trigger: 'axis' },
          grid: { left: 60, right: 8, top: 8, bottom: 24 },
          xAxis: {
            type: 'category',
            data: positions.map((p) => p.symbol),
            axisLine: { lineStyle: { color: 'var(--color-chart-border)' } },
          },
          yAxis: {
            type: 'value',
            axisLine: { show: false },
            splitLine: { lineStyle: { color: 'var(--color-chart-grid)' } },
            axisLabel: {
              color: 'var(--color-chart-axis)',
              fontSize: 10,
              formatter: (v: number) => `¥${v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v}`,
            },
          },
          series: [{
            type: 'bar', data: pnlData, barMaxWidth: 30,
            itemStyle: { borderRadius: [2, 2, 0, 0] },
          }],
        }}
        style={{ height }}
      />
    </Card>
  )
}
