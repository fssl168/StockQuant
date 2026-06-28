import { useEffect, useState } from 'react'
import { Row, Col, Card, Table, Tag, Typography, Empty, Skeleton } from 'antd'
import { TrendUp, Warning, ArrowUpRight, Sparkle } from '@phosphor-icons/react'
import { dashboardApi } from '@/api/dashboard'
import client from '@/api/client'
import EquityChart from '@/components/Chart/EquityChart'
import { useNotificationStore } from '@/stores/notificationStore'
import MetricCard from '@/components/Card/MetricCard'
import MetricTable from '@/components/Table/MetricTable'
import NotificationList from '@/components/AI/NotificationList'

const { Text, Title } = Typography

export default function Dashboard() {
  const [metrics, setMetrics] = useState<Record<string, unknown>>({})
  const [signals, setSignals] = useState<unknown[]>([])
  const [tasks, setTasks] = useState<unknown[]>([])
  const [equityCurve, setEquityCurve] = useState<{ dates: string[]; values: number[] } | null>(null)
  const [benchmarkData, setBenchmarkData] = useState<{ dates: string[]; values: number[] } | null>(null)
  const [loading, setLoading] = useState(true)
  const [aggMetrics, setAggMetrics] = useState<{ totalEquity?: number; dailyPnl?: number; positionCount?: number }>({})
  const notifications = useNotificationStore((s) => s.notifications)

  useEffect(() => {
    // 基准（沪深300）K 线日期范围：最近 60 天，与权益曲线窗口对齐
    const today = new Date()
    const startDate = new Date(today.getTime() - 60 * 86400000)
    const fmtDate = (d: Date) => d.toISOString().slice(0, 10)
    Promise.all([
      // 聚合指标（总权益、今日盈亏、持仓数）
      client.get('/api/dashboard/metrics')
        .then((r: any) => { if (r) { setMetrics(r); setAggMetrics(r) } })
        .catch((e: any) => console.warn('[Dashboard] 获取聚合指标失败:', e?.message)),
      dashboardApi.signals()
        .then((r: any) => { if (r) setSignals(Array.isArray(r) ? r : (r?.signals ?? r?.data ?? [])) })
        .catch((e: any) => { console.warn('[Dashboard] 获取信号失败:', e?.message); setSignals([]) }),
      dashboardApi.recentBacktests()
        .then((r: any) => { if (r) setTasks(Array.isArray(r) ? r : (r?.tasks ?? r?.data ?? [])) })
        .catch((e: any) => { console.warn('[Dashboard] 获取回测历史失败:', e?.message); setTasks([]) }),
      client.get('/api/portfolio/equity-curve')
        .then((r: any) => { if (r) setEquityCurve(r) })
        .catch((e: any) => console.warn('[Dashboard] 获取权益曲线失败:', e?.message)),
      client.get(`/api/data/kline?symbol=sh000300&start=${fmtDate(startDate)}&end=${fmtDate(today)}&timeframe=1d`)
        .then((r: any) => {
          const rows = Array.isArray(r) ? r : (r?.data ?? r)
          if (Array.isArray(rows)) {
            setBenchmarkData({
              dates: rows.map((k: any) => k.date),
              values: rows.map((k: any) => k.close),
            })
          }
        })
        .catch((e: any) => console.warn('[Dashboard] 获取基准数据失败:', e?.message)),
    ]).finally(() => setLoading(false))
  }, [])

  // 从聚合指标获取真实数据（默认 0）
  const totalEquity = aggMetrics.totalEquity || 0
  const dailyPnl = aggMetrics.dailyPnl || 0
  const positionCount = aggMetrics.positionCount || 0
  const sharpe = metrics['Sharpe Ratio'] || 0
  const maxDD = metrics['Max Drawdown'] || 0
  const annRet = metrics['Annualized Return'] || 0
  const totalTrades = metrics['Total Trades'] || 0
  const winRate = metrics['Win Rate'] || 0
  const profitFactor = metrics['Profit Factor'] || 0
  const dailyVol = metrics['Daily Volatility'] || 0
  const calmarRatio = metrics['Calmar Ratio'] || 0
  const sortinoRatio = metrics['Sortino Ratio'] || 0
  const alpha = metrics['Alpha'] || 0
  const beta = metrics['Beta'] || 0
  const backtestCount = metrics['backtest_count'] || 0

  const formatMoney = (val: number) => {
    if (Math.abs(val) >= 1_000_000) return `¥${(val / 1_000_000).toFixed(2)}M`
    if (Math.abs(val) >= 1_000) return `¥${(val / 1_000).toFixed(1)}K`
    return `¥${val.toFixed(0)}`
  }

  const metricItems = [
    {
      title: '总权益',
      value: formatMoney(totalEquity),
      prefix: <TrendUp size={20} weight="bold" />,
      valueStyle: { color: 'var(--color-text-primary)' },
    },
    {
      title: '今日盈亏',
      value: formatMoney(dailyPnl),
      prefix: <ArrowUpRight size={20} weight="bold" />,
      valueStyle: { color: dailyPnl >= 0 ? '#10b981' : '#ef4444' },
    },
    {
      title: '持仓数',
      value: String(positionCount),
      prefix: <Sparkle size={20} weight="bold" />,
      valueStyle: { color: 'var(--color-text-primary)' },
    },
    {
      title: '年化收益',
      value: (annRet * 100).toFixed(1),
      suffix: '%',
      precision: 1,
      prefix: <TrendUp size={20} weight="bold" />,
      valueStyle: { color: annRet >= 0 ? '#10b981' : '#ef4444' },
    },
    {
      title: '最大回撤',
      value: (maxDD * 100).toFixed(1),
      suffix: '%',
      precision: 1,
      prefix: <Warning size={20} weight="bold" />,
      valueStyle: { color: '#ef4444' },
    },
    {
      title: '夏普比率',
      value: sharpe.toFixed(2),
      precision: 2,
      prefix: <TrendUp size={20} weight="bold" />,
      valueStyle: { color: sharpe >= 1 ? '#10b981' : sharpe >= 0 ? '#f59e0b' : '#ef4444' },
    },
  ]

  const mergedNotifications = [
    ...(signals as any[]).map((s: any) => ({
      type: s.type ?? 'signal',
      title: s.title ?? s.reason ?? 'Signal',
      message: s.message ?? s.symbol ?? '',
      time: s.time ?? '',
    })),
    ...notifications.slice(0, 4).map((n) => ({
      type: n.type,
      title: n.title,
      message: n.message,
      time: n.time,
    })),
  ]

  const backtestColumns = [
    {
      title: '策略',
      dataIndex: 'strategyName',
      key: 'name',
      width: 200,
      render: (s: string) => <Text strong>{s}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (s: string) => (
        <Tag color={s === 'completed' ? 'green' : s === 'running' ? 'blue' : 'default'}>
          {s}
        </Tag>
      ),
    },
    {
      title: '收益率',
      key: 'return',
      width: 120,
      render: (_: any, r: any) => {
        const ret = r.metrics?.['Annualized Return']
        if (!ret) return <Text type="secondary">0.0%</Text>
        const num = typeof ret === 'string' ? parseFloat(ret) : ret
        return (
          <Text style={{ color: num >= 0 ? '#10b981' : '#ef4444', fontFamily: 'var(--font-mono)' }}>
            {num >= 0 ? '+' : ''}{num}%
          </Text>
        )
      },
    },
    {
      title: '夏普',
      key: 'sharpe',
      width: 80,
      render: (_: any, r: any) => {
        const s = r.metrics?.['Sharpe Ratio']
        return s ? (
          <Text style={{ fontFamily: 'var(--font-mono)' }}>{s}</Text>
        ) : (
          <Text type="secondary">0.00</Text>
        )
      },
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      key: 'time',
      width: 160,
      render: (d: string) => new Date(d).toLocaleString('zh-CN', { hour12: false }),
    },
  ]

  return (
    <div style={{ maxWidth: 1400 }}>
      <Title level={5} style={{ margin: '0 0 16px', color: 'var(--color-text-primary)', fontWeight: 600, letterSpacing: '0.03em' }}>
        系统概览
      </Title>

      {/* Metric grid */}
      <Row gutter={[12, 8]} style={{ marginBottom: 20 }}>
        {metricItems.map((m) => (
          <Col xs={24} sm={12} md={8} lg={4} key={m.title}>
            <MetricCard {...m} />
          </Col>
        ))}
      </Row>

      {/* Charts row */}
      <Row gutter={[12, 12]} style={{ marginBottom: 20 }}>
        <Col xs={24} lg={16}>
          <Card
            size="small"
            title={<span style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.03em' }}>权益曲线</span>}
            styles={{ body: { padding: '12px' } }}
          >
            {loading ? (
              <Skeleton active paragraph={{ rows: 8 }} />
            ) : (
              <EquityChart
                data={equityCurve ? equityCurve.values : []}
                dates={equityCurve ? equityCurve.dates : undefined}
                benchmarkData={benchmarkData ? benchmarkData.values : undefined}
                benchmarkLabel="沪深300"
                height={240}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card
            size="small"
            title={<span style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.03em' }}>AI 信号</span>}
            styles={{ body: { padding: '12px 16px' } }}
          >
            <NotificationList notifications={mergedNotifications} maxItems={5} />
          </Card>
        </Col>
      </Row>

      {/* Metrics table */}
      <Card
        size="small"
        title={<span style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.03em' }}>核心指标</span>}
        styles={{ body: { padding: 0 } }}
        style={{ marginBottom: 12 }}
      >
        {loading ? (
          <Skeleton active paragraph={{ rows: 4 }} style={{ padding: 16 }} />
        ) : (
          <MetricTable metrics={metrics as any} />
        )}
      </Card>

      {/* Backtest table */}
      <Card
        size="small"
        title={<span style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.03em' }}>回测历史</span>}
        styles={{ body: { padding: '0' } }}
      >
        <Table
          dataSource={tasks}
          columns={backtestColumns}
          rowKey="taskId"
          pagination={false}
          size="small"
          scroll={{ x: 600 }}
          locale={{ emptyText: <Empty description="暂无回测记录" /> }}
        />
      </Card>
    </div>
  )
}
