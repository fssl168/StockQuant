import { useEffect, useState } from 'react'
import { Row, Col, Card, Table, Tag, Typography, Empty, Skeleton } from 'antd'
import { TrendUp, Warning, ArrowUpRight, Sparkle } from '@phosphor-icons/react'
import { dashboardApi } from '@/api/dashboard'
import EquityChart from '@/components/Chart/EquityChart'
import { useNotificationStore } from '@/stores/notificationStore'

const { Text, Title } = Typography

interface MetricCardProps {
  label: string
  value: React.ReactNode
  icon: React.ReactNode
  color: string
}

function MetricCard({ label, value, icon, color }: MetricCardProps) {
  return (
    <Card
      size="small"
      styles={{ body: { padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 } }}
    >
      <div style={{ color, opacity: 0.7, display: 'flex', alignItems: 'center' }}>{icon}</div>
      <div>
        <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', lineHeight: 1.2 }}>
          {label}
        </div>
        <div style={{ fontSize: 18, fontWeight: 600, fontFamily: 'var(--font-mono)', color, lineHeight: 1.3 }}>
          {value}
        </div>
      </div>
    </Card>
  )
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState<Record<string, unknown>>({})
  const [signals, setSignals] = useState<unknown[]>([])
  const [tasks, setTasks] = useState<unknown[]>([])
  const [loading, setLoading] = useState(true)
  const notifications = useNotificationStore((s) => s.notifications)

  useEffect(() => {
    Promise.all([
      dashboardApi.metrics()
        .then((r: any) => setMetrics(r.metrics ?? {}))
        .catch(() => {}),
      dashboardApi.signals()
        .then((r: unknown[]) => setSignals(r))
        .catch(() => setSignals([])),
      dashboardApi.recentBacktests()
        .then((r: unknown[]) => setTasks(r))
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
      label: '总权益',
      value: '¥1.23M',
      icon: <TrendUp size={20} weight="bold" />,
      color: 'var(--color-text-primary)',
    },
    {
      label: '今日盈亏',
      value: <Text style={{ color: '#10b981', fontFamily: 'var(--font-mono)' }}>+¥12,345</Text>,
      icon: <ArrowUpRight size={20} weight="bold" />,
      color: '#10b981',
    },
    {
      label: '持仓数',
      value: '3',
      icon: <Sparkle size={20} weight="bold" />,
      color: 'var(--color-text-primary)',
    },
    {
      label: '年化收益',
      value: isNaN(annualizedReturn)
        ? <Text type="secondary">-</Text>
        : <Text style={{ color: annualizedReturn >= 0 ? '#10b981' : '#ef4444', fontFamily: 'var(--font-mono)' }}>
            {(annualizedReturn * 100).toFixed(1)}%
          </Text>,
      icon: <TrendUp size={20} weight="bold" />,
      color: isNaN(annualizedReturn) ? 'var(--color-text-tertiary)' : (annualizedReturn >= 0 ? '#10b981' : '#ef4444'),
    },
    {
      label: '最大回撤',
      value: isNaN(maxDrawdown)
        ? <Text type="secondary">-</Text>
        : <Text style={{ color: '#ef4444', fontFamily: 'var(--font-mono)' }}>
            {(maxDrawdown * 100).toFixed(1)}%
          </Text>,
      icon: <Warning size={20} weight="bold" />,
      color: isNaN(maxDrawdown) ? 'var(--color-text-tertiary)' : '#ef4444',
    },
    {
      label: '夏普比率',
      value: isNaN(sharpeRatio)
        ? <Text type="secondary">-</Text>
        : <Text style={{ color: sharpeRatio >= 1 ? '#10b981' : sharpeRatio >= 0 ? '#f59e0b' : '#ef4444', fontFamily: 'var(--font-mono)' }}>
            {sharpeRatio.toFixed(2)}
          </Text>,
      icon: <TrendUp size={20} weight="bold" />,
      color: isNaN(sharpeRatio) ? 'var(--color-text-tertiary)' : (sharpeRatio >= 1 ? '#10b981' : sharpeRatio >= 0 ? '#f59e0b' : '#ef4444'),
    },
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
          <Col xs={24} sm={12} md={8} lg={4} key={m.label}>
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
            {signals.length === 0 && notifications.length === 0 && (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  <span style={{ color: 'var(--color-text-tertiary)', fontSize: 12 }}>
                    <Sparkle size={24} weight="duotone" style={{ color: '#3b82f6', marginBottom: 8, display: 'block' }} />
                    暂无活跃信号
                  </span>
                }
              />
            )}
            <div style={{ maxHeight: 220, overflow: 'auto' }}>
              {([...signals, ...notifications.slice(0, 4)] as any[]).slice(0, 5).map((s: any) => (
                <div
                  key={s.id ?? s.title}
                  style={{
                    padding: '10px 0',
                    borderBottom: '1px solid var(--color-border-default)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 500,
                        color: 'var(--color-text-secondary)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {s.title ?? s.reason ?? 'Signal'}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: 'var(--color-text-tertiary)',
                        marginTop: 2,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {s.message ?? s.symbol ?? ''}
                    </div>
                  </div>
                  <span
                    style={{
                      fontSize: 10,
                      color: 'var(--color-text-disabled)',
                      fontFamily: 'var(--font-mono)',
                      whiteSpace: 'nowrap',
                      marginLeft: 12,
                    }}
                  >
                    {s.time ?? ''}
                  </span>
                </div>
              ))}
            </div>
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
