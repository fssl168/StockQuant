import { useState } from 'react'
import { Table, Button, Input, Card, Typography, Tag, Space } from 'antd'
import { Plus, Trash } from '@phosphor-icons/react'

const { Text } = Typography

interface WatchListProps {
  symbols: string[]
  livePrices: Record<string, { price: number; change: number }>
  onRemove: (symbol: string) => void
  onAdd: (symbol: string) => void
}

export default function WatchList({ symbols, livePrices, onRemove, onAdd }: WatchListProps) {
  const [newSymbol, setNewSymbol] = useState('')

  const handleAdd = () => {
    if (newSymbol.trim()) { onAdd(newSymbol.trim()); setNewSymbol('') }
  }

  const columns = [
    { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 120, render: (s: string) => (
      <Text style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{s}</Text>
    )},
    { title: '价格', key: 'price', width: 110, render: (_: unknown, r: { symbol: string }) => {
      const lp = livePrices[r.symbol]
      return lp ? (
        <Text style={{ fontFamily: 'var(--font-mono)', fontWeight: 500, color: lp.change >= 0 ? '#10b981' : '#ef4444' }}>
          {lp.price.toFixed(2)}
        </Text>
      ) : <Text type="secondary">-</Text>
    }},
    { title: '涨跌%', key: 'change', width: 100, render: (_: unknown, r: { symbol: string }) => {
      const lp = livePrices[r.symbol]
      return lp ? (
        <Tag color={lp.change >= 0 ? 'green' : 'red'} style={{ fontFamily: 'var(--font-mono)' }}>
          {lp.change >= 0 ? '+' : ''}{lp.change.toFixed(2)}%
        </Tag>
      ) : <Tag>-</Tag>
    }},
    { title: '操作', key: 'action', render: (_: any, r: any) => (
      <Button danger size="small" icon={<Trash size={14} />} onClick={() => onRemove(r.symbol)} />
    )},
  ]

  return (
    <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>自选股列表</span>}>
      <Space style={{ marginBottom: 12 }} size={8}>
        <Input
          value={newSymbol}
          onChange={(e) => setNewSymbol(e.target.value)}
          onPressEnter={handleAdd}
          placeholder="输入股票代码 (e.g. sh600519)"
          style={{ maxWidth: 200 }}
        />
        <Button icon={<Plus size={16} />} onClick={handleAdd}>添加</Button>
      </Space>
      <Table
        dataSource={symbols.map((s) => ({ key: s, symbol: s }))}
        rowKey="symbol"
        columns={columns}
        pagination={false}
        size="small"
      />
    </Card>
  )
}
