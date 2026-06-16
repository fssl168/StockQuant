import { Card, Row, Col } from 'antd'

interface PortfolioSummaryProps {
  totalValue: number
  totalCost: number
  totalPnl: number
  totalPnlPct: number
  positionCount: number
}

export default function PortfolioSummary({ totalValue, totalCost, totalPnl, totalPnlPct, positionCount }: PortfolioSummaryProps) {
  const summaryItems = [
    { label: '总市值', value: totalValue.toLocaleString(undefined, { maximumFractionDigits: 0 }) },
    { label: '总成本', value: totalCost.toLocaleString(undefined, { maximumFractionDigits: 0 }) },
    { label: '累计盈亏', value: `${totalPnl >= 0 ? '+' : ''}¥${totalPnl.toFixed(0)}`, color: totalPnl >= 0 ? 'var(--color-success)' : 'var(--color-danger)' },
    { label: '收益率', value: `${totalPnlPct}%`, color: totalPnl >= 0 ? 'var(--color-success)' : 'var(--color-danger)' },
    { label: '持仓数', value: String(positionCount) },
  ]

  return (
    <Row gutter={[8, 8]} style={{ marginBottom: 16 }}>
      {summaryItems.map((s) => (
        <Col xs={24} sm={12} md={6} key={s.label}>
          <Card size="small" styles={{ body: { padding: '10px 14px' } }}>
            <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</div>
            <div style={{ fontSize: 15, fontWeight: 600, fontFamily: 'var(--font-mono)', marginTop: 2, color: s.color || 'var(--color-text-primary)' }}>
              {s.value}
            </div>
          </Card>
        </Col>
      ))}
    </Row>
  )
}
