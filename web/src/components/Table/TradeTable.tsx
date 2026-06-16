import { Card, Table, Tag, Typography } from 'antd'

const { Text } = Typography

interface TradeRecord {
  date: string
  symbol: string
  side: string
  quantity: number
  price: number
  pnl?: number
}

interface TradeTableProps {
  trades: TradeRecord[]
}

export default function TradeTable({ trades }: TradeTableProps) {
  const columns = [
    { title: '时间', dataIndex: 'date', key: 'date', width: 150, render: (d: string) => new Date(d).toLocaleString() },
    { title: '标的', dataIndex: 'symbol', key: 'symbol', width: 100, render: (s: string) => (
      <Text style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{s}</Text>
    )},
    { title: '方向', dataIndex: 'side', key: 'side', width: 70, render: (d: string) => (
      <Tag color={d === 'BUY' ? 'green' : d === 'SELL' ? 'red' : 'default'}>{d}</Tag>
    )},
    { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 80, render: (v: number) => v.toLocaleString() },
    { title: '价格', dataIndex: 'price', key: 'price', width: 100, render: (v: number) => v.toFixed(2) },
    { title: '盈亏', dataIndex: 'pnl', key: 'pnl', width: 100, render: (v: number | undefined) => v != null ? (
      <Text style={{ color: v >= 0 ? '#10b981' : '#ef4444', fontFamily: 'var(--font-mono)' }}>
        {v >= 0 ? '+' : ''}{v.toFixed(0)}
      </Text>
    ) : <Text type="secondary">-</Text> },
  ]

  return (
    <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>交易明细</span>} styles={{ body: { padding: '0' } }}>
      <Table
        dataSource={trades}
        rowKey={(_, i) => String(i)}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 笔` }}
        size="small"
        scroll={{ x: 500 }}
        columns={columns}
      />
    </Card>
  )
}
