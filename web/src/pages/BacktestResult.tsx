import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Row, Col, Card, Button, Typography, Tag, Alert, Skeleton, Dropdown, message } from 'antd'
import { ArrowCounterClockwise, DownloadSimple, FileHtml, FilePdf, FileText } from '@phosphor-icons/react'
import { backtestApi } from '@/api/dashboard'
import { analyzeBacktest, type StructuredInsight } from '@/api/ai'
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
    taskId: string
    strategyName: string
    status: string
    metrics: BacktestMetrics
    equityCurve: number[]
    benchmarkEquityCurve?: number[]
    benchmark?: string
    dates?: string[]
    trades: Trade[]
    error: string | null
  }
  const [task, setTask] = useState<BacktestTaskData | null>(null)
  const [loading, setLoading] = useState(true)
  const [aiInsight, setAiInsight] = useState<string | StructuredInsight | null>(null)
  const [insightLoading, setInsightLoading] = useState(false)

  useEffect(() => {
    if (!id) return
    let timer: ReturnType<typeof setTimeout> | null = null

    const fetchTask = () => {
      backtestApi.get(id)
        .then((task: any) => {
          setTask(task)
          // 回测仍在运行，2 秒后轮询
          if (task?.status === 'running') {
            timer = setTimeout(fetchTask, 2000)
          }
        })
        .catch(() => {
          setTask(null)
        })
        .finally(() => setLoading(false))
    }

    fetchTask()
    return () => { if (timer) clearTimeout(timer) }
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

  const exportReport = async (format: 'html' | 'pdf' | 'json') => {
    if (!id) return
    try {
      const resp = await fetch(`/api/backtest/${id}/report?format=${format}`)
      if (!resp.ok) throw new Error('导出失败')

      const ext = format === 'pdf' ? 'pdf' : format === 'json' ? 'json' : 'html'
      const mimeType = format === 'pdf' ? 'application/pdf' : format === 'json' ? 'application/json' : 'text/html'

      let blob: Blob
      if (format === 'pdf') {
        const buf = await resp.arrayBuffer()
        blob = new Blob([buf], { type: mimeType })
      } else {
        const text = await resp.text()
        blob = new Blob([text], { type: mimeType })
      }

      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `backtest-report-${id}.${ext}`
      a.click()
      URL.revokeObjectURL(url)
      message.success(`报表已导出为 ${ext.toUpperCase()}`)
    } catch (e: any) {
      message.error(`导出失败: ${e?.message || '未知错误'}`)
    }
  }

  const exportMenuItems = [
    { key: 'html', label: 'HTML 报表', icon: <FileHtml size={14} /> },
    { key: 'pdf', label: 'PDF 报表', icon: <FilePdf size={14} /> },
    { key: 'json', label: 'JSON 数据', icon: <FileText size={14} /> },
  ]

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
  if (!task) {
    const reason = id === 'undefined' || !id ? '回测任务 ID 无效' : '未找到该回测任务'
    return <Alert message={reason} type="error" />
  }

  // Access camelCase keys (snakeToCamel interceptor transforms them)
  const equityData = task.equityCurve ?? []
  const metrics = task.metrics as BacktestMetrics ?? {}
  const benchmarkData = task.benchmarkEquityCurve

  const BENCHMARK_LABELS: Record<string, string> = {
    hs300: '沪深300',
    zz500: '中证500',
    cyb: '创业板指',
  }
  const benchmarkLabel = task.benchmark ? BENCHMARK_LABELS[task.benchmark] : undefined

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

  // 百分比指标后端返回小数（如 0.1234 表示 12.34%），展示时乘以 100
  const pct = (v: unknown): number | string | undefined => typeof v === 'number' ? v * 100 : (v as string | undefined)

  const metricItems = [
    { label: '年化收益', value: pct(metrics['Annualized Return']) ?? '-', suffix: '%', color: (v: number | string) => typeof v === 'number' ? (v >= 0 ? '#10b981' : '#ef4444') : 'var(--color-text-primary)' },
    { label: '最大回撤', value: pct(metrics['Max Drawdown']) ?? '-', suffix: '%', color: '#ef4444' },
    { label: '夏普', value: metrics['Sharpe Ratio'] ?? '-', suffix: '', color: () => 'var(--color-brand-primary)' },
    { label: 'Sortino', value: metrics['Sortino Ratio'] ?? '-', suffix: '', color: () => 'var(--color-brand-primary)' },
    { label: 'Calmar', value: metrics['Calmar Ratio'] ?? '-', suffix: '', color: () => 'var(--color-brand-primary)' },
    { label: '胜率', value: pct(metrics['Win Rate']) ?? '-', suffix: '%', color: () => '#10b981' },
    { label: '总交易', value: metrics['Total Trades'] ?? '-', suffix: '', color: () => 'var(--color-text-primary)' },
    { label: 'SQN', value: metrics['SQN (System Quality Number)'] ?? '-', suffix: '', color: () => 'var(--color-brand-primary)' },
  ]

  const tradeRows = ((task.trades ?? task['trades']) as Trade[] ?? []).map((t: any) => ({
    tradeId: t.tradeId ?? '',
    date: t.time ?? t.date ?? '',
    symbol: t.symbol ?? '',
    side: t.side ?? t.direction ?? '',
    quantity: t.quantity ?? t.size ?? 0,
    price: t.price ?? 0,
    notional: t.notional ?? (t.price && t.quantity ? t.price * t.quantity : undefined),
    commission: t.commission ?? undefined,
    slippage: t.slippage ?? undefined,
    pnl: t.pnl,
  }))

  return (
    <div style={{ maxWidth: 1400 }}>
      <Link to="/backtest" style={{ marginBottom: 16, display: 'inline-block' }}>
        <Button icon={<ArrowCounterClockwise size={16} />} size="small">返回</Button>
      </Link>

      <div style={{ display: 'flex', alignItems: 'start', gap: 12, marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0, flex: 1, fontSize: 16, fontWeight: 600 }}>{task.strategyName}</Title>
        <Dropdown
          menu={{ items: exportMenuItems, onClick: ({ key }) => exportReport(key as 'html' | 'pdf' | 'json') }}
        >
          <Button size="small" icon={<DownloadSimple size={16} />}>导出报表</Button>
        </Dropdown>
        <Tag color={task.status === 'completed' ? 'green' : task.status === 'running' ? 'blue' : 'red'}>{task.status}</Tag>
      </div>

      {/* 数据诊断信息（无数据时显示） */}
      {!equityData.length && Object.keys(metrics).length === 0 && (
        <Alert message="数据诊断" description={
          <div>
            <div>status: <strong>{task.status}</strong></div>
            <div>metrics keys: <strong>{Object.keys(metrics).join(', ') || '(空)'}</strong></div>
            <div>equity length: <strong>{equityData.length}</strong></div>
            <div>trades count: <strong>{((task.trades ?? task['trades']) ?? []).length}</strong></div>
            <div>error: <strong>{(task.error ?? task['error']) || '无'}</strong></div>
          </div>
        } type={task.status === 'failed' ? 'error' : 'warning'} style={{ marginBottom: 16 }} />
      )}

      {/* 错误信息 */}
      {(task.error ?? task['error']) && (
        <Alert message="回测失败" description={String(task.error ?? task['error'])} type="error" style={{ marginBottom: 16 }} />
      )}

  {/* 空结果提示 */}
  {task.status === 'completed' && !equityData.length && Object.keys(metrics).length === 0 && !((task.trades ?? task['trades'])?.length) && (
    <Alert message="回测完成但未产生任何交易数据" type="warning" style={{ marginBottom: 16 }} />
  )}

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
        <EquityChart data={equityData} height={220} benchmarkData={benchmarkData} dates={task.dates} benchmarkLabel={benchmarkLabel} />
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
