import { useEffect, useState } from 'react'
import { Row, Col, Card, Table, Tag, Typography } from 'antd'
import { TrendUp, Warning, ArrowUpRight, Sparkle } from '@phosphor-icons/react'
import { dashboardApi } from '@/api/dashboard'
import EquityChart from '@/components/Chart/EquityChart'
import { useNotificationStore } from '@/stores/notificationStore'

const { Text } = Typography

export default function Dashboard() {
  const [metrics, setMetrics] = useState<any>({})
  const [signals, setSignals] = useState<any[]>([])
  const [tasks, setTasks] = useState<any[]>([])
  const notifications = useNotificationStore((s) => s.notifications)

  useEffect(() => {
    Promise.all([
      dashboardApi.metrics().then((r: any) => setMetrics(r.metrics ?? {})).catch(() => {}),
      dashboardApi.signals().then(setSignals).catch(() => setSignals([])),
      dashboardApi.recentBacktests().then(setTasks).catch(() => setTasks([])),
    ]).finally(() => {})
  }, [])

  const metricItems = [
    { label: '总权益', value: '¥1.23M', icon: <TrendUp size={18} />, color: '#f0f0f0' },
    { label: '今日盈亏', value: '+¥12,345', icon: <ArrowUpRight size={18} weight="bold" />, color: '#10b981' },
    { label: '持仓数', value: '3', icon: <Sparkle size={18} />, color: '#f0f0f0' },
    { label: '年化收益', value: metrics['Annualized Return'] ? `${metrics['Annualized Return']?.toFixed(1)}%` : '-', icon: <TrendUp size={18} />, color: metrics['Annualized Return'] >= 0 ? '#10b981' : '#ef4444' },
    { label: '最大回撤', value: metrics['Max Drawdown'] ? `${(metrics['Max Drawdown'] as number)?.toFixed(1)}%` : '-', icon: <Warning size={18} />, color: '#ef4444' },
    { label: '夏普比率', value: metrics['Sharpe Ratio'] ? `${metrics['Sharpe Ratio']}` : '-', icon: <TrendUp size={18} />, color: typeof metrics['Sharpe Ratio'] === 'number' && metrics['Sharpe Ratio'] >= 1 ? '#10b981' : '#f59e0b' },
  ]

  const backtestColumns = [
    { title: '策略', dataIndex: 'strategy_name', key: 'name', width: 200, render: (s: string) => <Text strong>{s}</Text> },
    { title: '状态', dataIndex: 'status', key: 'status', width: 90, render: (s: string) => (
      <Tag color={s === 'completed' ? 'green' : s === 'running' ? 'blue' : 'default'}>{s}</Tag>
    )},
    { title: '收益率', key: 'return', width: 120, render: (_: any, r: any) => {
      const ret = r.metrics?.['Annualized Return']
      if (!ret) return <Text type="secondary">-</Text>
      const num = typeof ret === 'string' ? parseFloat(ret) : ret
      return <Text style={{ color: num >= 0 ? '#10b981' : '#ef4444', fontFamily: 'var(--font-mono)' }}>{num >= 0 ? '+' : ''}{num}%</Text>
    }},
    { title: '夏普', key: 'sharpe', width: 80, render: (_: any, r: any) => {
      const s = r.metrics?.['Sharpe Ratio']
      return s ? <Text style={{ fontFamily: 'var(--font-mono)' }}>{s}</Text> : <Text type="secondary">-</Text>
    }},
    { title: '创建时间', dataIndex: 'created_at', key: 'time', width: 160, render: (d: string) => new Date(d).toLocaleString() },
  ]

  return (
    <div style={{ maxWidth: 1400 }}>
      {/* Metric grid */}
      <Row gutter={[12, 8]} style={{ marginBottom: 20 }}>
        {metricItems.map((m) => (
          <Col xs={24} sm={12} md={8} lg={4} key={m.label}>
            <Card size="small" styles={{ body: { padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 10 } }}>
              <div style={{ color: m.color, opacity: 0.8 }}>{m.icon}</div>
              <div>
                <div style={{ fontSize: 10, color: '#666', textTransform: 'uppercase', letterSpacing: '0.05em', lineHeight: 1.2 }}>{m.label}</div>
                <div style={{ fontSize: 16, fontWeight: 600, fontFamily: 'var(--font-mono)', color: m.color, lineHeight: 1.3 }}>{m.value}</div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* Charts row */}
      <Row gutter={[12, 12]} style={{ marginBottom: 20 }}>
        <Col xs={24} lg={16}>
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.03em' }}>权益曲线</span>} styles={{ body: { padding: '12px' } }}>
            <EquityChart data={Array.from({ length: 30 }, (_: number, _idx: number) => 1_000_000 + Math.random() * 200_000)} height={240} />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.03em' }}>AI 信号</span>} styles={{ body: { padding: '12px 14px' } }}>
            {signals.length === 0 && notifications.length === 0 && (
              <div style={{ textAlign: 'center', padding: '40px 0', color: '#555', fontSize: 12 }}>
                <Sparkle size={32} weight="duotone" style={{ color: '#0066FF', marginBottom: 8, display: 'block' }} />
                暂无活跃信号
              </div>
            )}
            {[...signals, ...notifications.slice(0, 4)].slice(0, 5).map((s: any) => (
              <div key={s.id ?? s.title} style={{
                padding: '8px 0', borderBottom: '1px solid #1a1a1a',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 500, color: '#ddd', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {s.title ?? s.reason ?? 'Signal'}
                  </div>
                  <div style={{ fontSize: 11, color: '#555', marginTop: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {s.message ?? s.symbol ?? ''}
                  </div>
                </div>
                <span style={{ fontSize: 10, color: '#444', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap', marginLeft: 8 }}>
                  {s.time ?? ''}
                </span>
              </div>
            ))}
          </Card>
        </Col>
      </Row>

      {/* Backtest table */}
      <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.03em' }}>回测历史</span>} styles={{ body: { padding: '0' } }}>
        <Table
          dataSource={tasks}
          columns={backtestColumns}
          rowKey="task_id"
          pagination={false}
          size="small"
          scroll={{ x: 600 }}
        />
      </Card>
    </div>
  )
}
