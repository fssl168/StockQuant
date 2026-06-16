import { useEffect, useState } from 'react'
import { Row, Col, Card, Table, Tag, Typography, Empty, Skeleton } from 'antd'
import { TrendUp, Warning, ArrowUpRight, Sparkle } from '@phosphor-icons/react'
import { dashboardApi } from '@/api/dashboard'
import EquityChart from '@/components/Chart/EquityChart'
import { useNotificationStore } from '@/stores/notificationStore'
import MetricCard from '@/components/Card/MetricCard'
import NotificationList from '@/components/AI/NotificationList'

const { Text, Title } = Typography

export default function Dashboard() {
  const [metrics, setMetrics] = useState<Record<string, unknown>>({})
  const [signals, setSignals] = useState<unknown[]>([])
  const [tasks, setTasks] = useState<unknown[]>([])
  const [loading, setLoading] = useState(true)
  const notifications = useNotificationStore((s) => s.notifications)

  useEffect(() => {
    Promise.all([
      dashboardApi.metrics()
        .then((r: any) => { if (r) setMetrics(r.metrics ?? {}) })
        .catch(() => {}),
      dashboardApi.signals()
        .then((r: unknown[]) => { if (r) setSignals(r) })
        .catch(() => setSignals([])),
      dashboardApi.recentBacktests()
        .then((r: unknown[]) => { if (r) setTasks(r) })
        .catch(() => setTasks([])),
    ]).finally(() => setLoading(false))
  }, [])

  const annualizedReturn = typeof metrics['Annualized Return'] === 'number'
    ? metrics['Annualized Return'] as number
    : NaN

  const maxDrawdown = typeof metrics['Max Drawdown'] === 'number'
    ? metrics['Max Drawdown'] as number
    : NaN

  const sharpeRatio = typeof metrics['Sharpe Ratio'] === 'number'
    ? metrics['Sharpe Ratio'] as number
    : NaN

  const metricItems = [
    {
      title: '总权益',
      value: '¥1.23M',
      prefix: <TrendUp size={20} weight="bold" />,
      valueStyle: { color: 'var(--color-text-primary)' },
    },
    {
      title: '今日盈亏',
      value: '+¥12,345',
      prefix: <ArrowUpRight size={20} weight="bold" />,
      valueStyle: { color: '#10b981' },
    },
    {
      title: '持仓数',
      value: '3',
      prefix: <Sparkle size={20} weight="bold" />,
      valueStyle: { color: 'var(--color-text-primary)' },
    },
    {
      title: '年化收益',
      value: isNaN(annualizedReturn) ? '-' : annualizedReturn * 100,
      suffix: isNaN(annualizedReturn) ? undefined : '%',
      precision: 1,
      prefix: <TrendUp size={20} weight="bold" />,
      valueStyle: { color: isNaN(annualizedReturn) ? 'var(--color-text-tertiary)' : (annualizedReturn >= 0 ? '#10b981' : '#ef4444') },
    },
    {
      title: '最大回撤',
      value: isNaN(maxDrawdown) ? '-' : maxDrawdown * 100,
      suffix: isNaN(maxDrawdown) ? undefined : '%',
      precision: 1,
      prefix: <Warning size={20} weight="bold" />,
      valueStyle: { color: isNaN(maxDrawdown) ? 'var(--color-text-tertiary)' : '#ef4444' },
    },
    {
      title: '夏普比率',
      value: isNaN(sharpeRatio) ? '-' : sharpeRatio,
      precision: 2,
      prefix: <TrendUp size={20} weight="bold" />,
      valueStyle: { color: isNaN(sharpeRatio) ? 'var(--color-text-tertiary)' : (sharpeRatio >= 1 ? '#10b981' : sharpeRatio >= 0 ? '#f59e0b' : '#ef4444') },
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
      dataIndex: 'strategy_name',
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
        if (!ret) return <Text type="secondary">-</Text>
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
          <Text type="secondary">-</Text>
        )
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
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
                data={Array.from({ length: 30 }, () => 1_000_000 + Math.random() * 200_000)}
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

      {/* Backtest table */}
      <Card
        size="small"
        title={<span style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.03em' }}>回测历史</span>}
        styles={{ body: { padding: '0' } }}
      >
        <Table
          dataSource={tasks}
          columns={backtestColumns}
          rowKey="task_id"
          pagination={false}
          size="small"
          scroll={{ x: 600 }}
          locale={{ emptyText: <Empty description="暂无回测记录" /> }}
        />
      </Card>
    </div>
  )
}
