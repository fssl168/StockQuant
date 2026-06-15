import { useEffect, useState } from 'react'
import { Row, Col, Card, Statistic, Table, Tag, Spin, Alert } from 'antd'
import {
  TrendUpOutlined,
  TrendDownOutlined,
  AlertOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons'
import { useNotificationStore } from '@/stores/notificationStore'
import { useMarketStore } from '@/stores/marketStore'
import { backtestApi } from '@/api/backtest'
import ReactECharts from 'echarts-for-react'

export default function Dashboard() {
  const [tasks, setTasks] = useState<unknown[]>([])
  const [loading, setLoading] = useState(true)
  const notifications = useNotificationStore((s) => s.notifications)

  useEffect(() => {
    backtestApi.list()
      .then((r) => setTasks(r))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const columns = [
    { title: '策略', dataIndex: 'strategy_name', key: 'name' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={s === 'completed' ? 'green' : 'orange'}>{s}</Tag> },
    { title: '创建时间', dataIndex: 'created_at', key: 'time' },
  ]

  const recentSignals = notifications.slice(0, 5)

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card>
            <Statistic title="总资产" value={1234567} prefix="¥" precision={0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="今日收益" value={12345} prefix="¥" suffix="+" valueStyle={{ color: '#3f8600' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="持仓数量" value={3} suffix="只" />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="回测任务" value={tasks.length} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={16}>
          <Card title="权益曲线">
            <Spin spinning={loading}>
              <ReactECharts
                option={{
                  xAxis: { type: 'category', data: Array.from({ length: 30 }, (_, i) => `${i + 1}日`) },
                  yAxis: { type: 'value' },
                  series: [{ type: 'line', data: Array.from({ length: 30 }, () => 1000000 + Math.random() * 200000), smooth: true }],
                }}
                style={{ height: 300 }}
              />
            </Spin>
          </Card>
        </Col>
        <Col span={8}>
          <Card title="最近信号">
            {recentSignals.length === 0 ? <Alert message="暂无信号" type="info" showIcon /> : null}
            {recentSignals.map((s) => (
              <div key={s.id} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
                <Tag color={s.type === 'alert' ? 'red' : 'blue'}>{s.title}</Tag>
                <span>{s.message}</span>
                <span style={{ float: 'right', color: '#999', fontSize: 12 }}>{s.time}</span>
              </div>
            ))}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card title="回测任务列表">
            <Table dataSource={tasks} columns={columns} rowKey="task_id" pagination={false} size="small" />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
