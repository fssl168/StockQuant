import { useState } from 'react'
import { Card, Row, Col, Table, Select, InputNumber, Button } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'

const { Option } = Select

export default function Portfolio() {
  const [selectedPositions, setSelectedPositions] = useState(['sh600519', 'sz000858', 'sh601318'])

  const positions = [
    { key: '1', symbol: 'sh600519', name: '贵州茅台', shares: 100, cost: 1680, price: 1725.5, pnl: 4550, pnlPct: 2.71 },
    { key: '2', symbol: 'sz000858', name: '五粮液', shares: 500, cost: 152, price: 148.3, pnl: -1850, pnlPct: -2.43 },
    { key: '3', symbol: 'sh601318', name: '中国平安', shares: 300, cost: 45.5, price: 47.8, pnl: 690, pnlPct: 5.05 },
  ]

  const totalValue = positions.reduce((s, p) => s + p.shares * p.price, 0)
  const totalCost = positions.reduce((s, p) => s + p.shares * p.cost, 0)
  const totalPnl = totalValue - totalCost

  const positionColumns = [
    { title: '代码', dataIndex: 'symbol', key: 'symbol' },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '持仓数量', dataIndex: 'shares', key: 'shares' },
    { title: '成本价', dataIndex: 'cost', key: 'cost', render: (v: number) => `¥${v.toFixed(2)}` },
    { title: '现价', dataIndex: 'price', key: 'price', render: (v: number) => `¥${v.toFixed(2)}` },
    { title: '盈亏', key: 'pnl', render: (_, r) => <span style={{ color: r.pnl >= 0 ? '#3f8600' : '#cf1322' }}>{r.pnl >= 0 ? '+' : ''}¥{r.pnl.toFixed(0)}</span> },
    { title: '盈亏率', key: 'pnlPct', render: (_, r) => <span style={{ color: r.pnlPct >= 0 ? '#3f8600' : '#cf1322' }}>{r.pnlPct >= 0 ? '+' : ''}{r.pnlPct.toFixed(2)}%</span> },
  ]

  const industryData = [
    { value: 40, name: '白酒' },
    { value: 25, name: '金融' },
    { value: 20, name: '消费' },
    { value: 15, name: '其他' },
  ]

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col span={6}><Card><StatItem label="总资产" value={`¥${totalValue.toFixed(0)}`} /></Card></Col>
        <Col span={6}><Card><StatItem label="总成本" value={`¥${totalCost.toFixed(0)}`} /></Card></Col>
        <Col span={6}><Card><StatItem label="累计盈亏" value={`¥${totalPnl.toFixed(0)}`} color={totalPnl >= 0} /></Card></Col>
        <Col span={6}><Card><StatItem label="持仓数量" value={positions.length} suffix="只" /></Card></Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={14}>
          <Card title="持仓明细">
            <Table dataSource={positions} columns={positionColumns} rowKey="key" pagination={false} size="middle" />
          </Card>
        </Col>
        <Col span={10}>
          <Card title="行业分布">
            <ReactECharts
              option={{
                tooltip: { trigger: 'item' },
                series: [{ type: 'pie', radius: ['40%', '70%'], data: industryData }],
              }}
              style={{ height: 300 }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

function StatItem({ label, value, color, suffix }: { label: string; value: string | number; color?: boolean; suffix?: string }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 12, color: '#999' }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 600, color: color === false ? '#cf1322' : undefined }}>
        {value}{suffix || ''}
      </div>
    </div>
  )
}
