import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Row, Col, Card, Button, Typography, Tag, Alert, Skeleton } from 'antd'
import { ArrowCounterClockwise } from '@phosphor-icons/react'
import { backtestApi } from '@/api/dashboard'
import { analyzeBacktest } from '@/api/ai'
import EquityChart from '@/components/Chart/EquityChart'
import DrawdownChart from '@/components/Chart/DrawdownChart'
import MonthHeatmap from '@/components/Chart/MonthHeatmap'
import MetricTable from '@/components/Table/MetricTable'
import InsightCard from '@/components/AI/InsightCard'
import TradeTable from '@/components/Table/TradeTable'
import type { BacktestMetrics, Trade } from '@/types'

const { Title } = Typography

export default function BacktestResult() {
  const { id } = useParams<{ id: string }>()
  interface BacktestTaskData {
    task_id: string
    strategy_name: string
    status: string
    metrics: BacktestMetrics
    equity_curve: number[]
    trades: Trade[]
    error: string | null
  }
  const [task, setTask] = useState<BacktestTaskData | null>(null)
  const [loading, setLoading] = useState(true)
  const [aiInsight, setAiInsight] = useState<string | null>(null)
  const [insightLoading, setInsightLoading] = useState(false)

  useEffect(() => {
    if (!id) return
    backtestApi.get(id)
      .then(setTask)
      .catch(() => setTask(null))
      .finally(() => setLoading(false))
  }, [id])

  const fetchInsight = async () => {
    if (!id) return
    setInsightLoading(true)
    try {
      const result = await analyzeBacktest(id)
      setAiInsight(result.insight)
    } catch {
      setAiInsight('AI 解读暂时不可用，请稍后重试。')
    } finally {
      setInsightLoading(false)
    }
  }

  if (loading) return (
    <div style={{ maxWidth: 1400 }}>
      <Skeleton active paragraph={{ rows: 2 }} style={{ marginBottom: 16 }} />
      <Row gutter={[8, 8]} style={{ marginBottom: 16 }}>
        {[...Array(8)].map((_, i) => (
          <Col key={i} xs={24} sm={12} md={8} lg={6}>
            <Card size="small"><Skeleton active paragraph={{ rows: 1 }} /></Card>
          </Col>
        ))}
      </Row>
      <Skeleton active paragraph={{ rows: 6 }} style={{ marginBottom: 12 }} />
      <Row gutter={[12, 12]}>
        <Col span={24}><Skeleton active paragraph={{ rows: 4 }} /></Col>
      </Row>
      <Skeleton active paragraph={{ rows: 3 }} />
    </div>
  )
  if (!task) return <Alert message="Backtest task not found" type="error" />

  const equityData = (task.equity_curve as number[] ?? [])
  const metrics = task.metrics as BacktestMetrics ?? {}

  // Generate drawdown data from equity curve
  const drawdownData = equityData.length > 0 ? (() => {
    let peak = equityData[0]
    return equityData.map((v) => {
      if (v > peak) peak = v
      return (v - peak) / peak
    })
  })() : []

  // Generate monthly returns
  const monthlyReturns: Record<string, number> = (metrics['Monthly Returns'] as Record<string, number>) ?? {}

  const metricItems = [
    { label: '年化收益', value: metrics['Annualized Return'] ?? '-', suffix: '%', color: (v: number | string) => typeof v === 'number' ? (v >= 0 ? '#10b981' : '#ef4444') : 'var(--color-text-primary)' },
    { label: '最大回撤', value: metrics['Max Drawdown'] ?? '-', suffix: '%', color: '#ef4444' },
    { label: '夏普', value: metrics['Sharpe Ratio'] ?? '-', suffix: '', color: () => 'var(--color-brand-primary)' },
    { label: 'Sortino', value: metrics['Sortino Ratio'] ?? '-', suffix: '', color: () => 'var(--color-brand-primary)' },
    { label: 'Calmar', value: metrics['Calmar Ratio'] ?? '-', suffix: '', color: () => 'var(--color-brand-primary)' },
    { label: '胜率', value: metrics['Win Rate'] ?? '-', suffix: '%', color: () => '#10b981' },
    { label: '总交易', value: metrics['Total Trades'] ?? '-', suffix: '', color: () => 'var(--color-text-primary)' },
    { label: 'SQN', value: metrics['SQN (System Quality Number)'] ?? '-', suffix: '', color: () => 'var(--color-brand-primary)' },
  ]

  const tradeRows = (task.trades as Trade[] ?? []).map((t) => ({
    date: t.time,
    symbol: t.symbol,
    side: t.direction,
    quantity: t.size,
    price: t.price,
    pnl: t.pnl,
  }))

  return (
    <div style={{ maxWidth: 1400 }}>
      <Link to="/backtest" style={{ marginBottom: 16, display: 'inline-block' }}>
        <Button icon={<ArrowCounterClockwise size={16} />} size="small">返回</Button>
      </Link>

      <div style={{ display: 'flex', alignItems: 'start', gap: 12, marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0, flex: 1, fontSize: 16, fontWeight: 600 }}>{task.strategy_name}</Title>
        <Tag color={task.status === 'completed' ? 'green' : 'blue'}>{task.status}</Tag>
      </div>

      {/* Metric cards */}
      <Row gutter={[8, 8]} style={{ marginBottom: 16 }}>
        {metricItems.map((m) => (
          <Col xs={24} sm={12} md={8} lg={6} key={m.label}>
            <Card size="small" styles={{ body: { padding: '8px 12px', textAlign: 'center' } }}>
              <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>
                {m.label}
              </div>
              <div style={{ fontSize: 15, fontWeight: 600, fontFamily: 'var(--font-mono)', color: typeof m.color === 'function' ? m.color(m.value as number) : m.color }}>
                {typeof m.value === 'number' ? m.value.toFixed(2) : m.value}{m.suffix}
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* Equity curve */}
      <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>权益曲线</span>} styles={{ body: { padding: '12px' } }} style={{ marginBottom: 12 }}>
        <EquityChart data={equityData} height={220} />
      </Card>

      {/* Drawdown + Monthly returns */}
      <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
        <Col xs={24} lg={12}>
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>回撤曲线</span>} styles={{ body: { padding: '12px' } }}>
            <DrawdownChart data={drawdownData} height={180} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>月度收益</span>} styles={{ body: { padding: '12px' } }}>
            <MonthHeatmap data={monthlyReturns} height={180} />
          </Card>
        </Col>
      </Row>

      {/* 30+ Metrics */}
      <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>完整指标</span>} styles={{ body: { padding: 0 } }}>
        <MetricTable metrics={metrics} />
      </Card>

      {/* Trades */}
      <div style={{ marginTop: 12 }}>
        <TradeTable trades={tradeRows} />
      </div>

      {/* AI Insight */}
      <div style={{ marginTop: 12 }}>
        <InsightCard insight={aiInsight} loading={insightLoading} onGenerate={fetchInsight} />
      </div>
    </div>
  )
}
