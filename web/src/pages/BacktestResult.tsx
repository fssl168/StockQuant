import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Card, Row, Col, Tag, Table, Descriptions, Alert, Spin } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { backtestApi, type BacktestTask } from '@/api/backtest'
import ReactECharts from 'echarts-for-react'

export default function BacktestResult() {
  const { id } = useParams<{ id: string }>()
  const [task, setTask] = useState<BacktestTask | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    backtestApi.get(id)
      .then(setTask)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <Spin size="large" />
  if (!task) return <Alert message="回测任务不存在" type="error" />

  const equityData = (task.equity_curve as unknown[][])?.map((p) => p[1]) ?? []

  return (
    <div>
      <Link to="/backtest"><Button icon={<ArrowLeftOutlined />} style={{ marginBottom: 16 }}>返回</Button></Link>
      <h2>{task.strategy_name}</h2>

      <Row gutter={[16, 16]}>
        <Col span={4}><Card><DescriptItem label="年化收益" value={task.metrics['Annualized Return']} /></Card></Col>
        <Col span={4}><Card><DescriptItem label="最大回撤" value={task.metrics['Max Drawdown']} /></Card></Col>
        <Col span={4}><Card><DescriptItem label="夏普比率" value={task.metrics['Sharpe Ratio']} /></Card></Col>
        <Col span={4}><Card><DescriptItem label="胜率" value={task.metrics['Win Rate']} /></Card></Col>
        <Col span={4}><Card><DescriptItem label="总交易" value={task.metrics['Total Trades']} /></Card></Col>
        <Col span={4}><Card><DescriptItem label="SQN" value={task.metrics['SQN (System Quality Number)']} /></Card></Col>
      </Row>

      <Card title="资金曲线" style={{ marginTop: 16 }}>
        <ReactECharts
          option={{
            xAxis: { type: 'category', data: equityData.map((_, i) => i + 1) },
            yAxis: { type: 'value' },
            series: [{ type: 'line', data: equityData, smooth: true, areaStyle: {} }],
          }}
          style={{ height: 300 }}
        />
      </Card>

      <Card title="交易明细" style={{ marginTop: 16 }}>
        <Table dataSource={task.trades} rowKey={(r, i) => i} pagination={{ pageSize: 20 }} size="small"
          columns={[
            { title: '时间', dataIndex: 'time', key: 'time' },
            { title: '代码', dataIndex: 'symbol', key: 'symbol' },
            { title: '方向', dataIndex: 'direction', key: 'direction', render: (d: string) => <Tag color={d === 'BUY' ? 'green' : 'red'}>{d}</Tag> },
            { title: '数量', dataIndex: 'size', key: 'size' },
            { title: '价格', dataIndex: 'price', key: 'price' },
          ]}
        />
      </Card>
    </div>
  )
}

function DescriptItem({ label, value }: { label: string; value: unknown }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 12, color: '#999' }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 600 }}>{value ?? 'N/A'}</div>
    </div>
  )
}
