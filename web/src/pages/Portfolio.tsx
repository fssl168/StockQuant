import { Card, Row, Col, Table, Typography, Tag } from 'antd'
import { ArrowUpRight, ArrowDownRight } from '@phosphor-icons/react'
import ReactECharts from 'echarts-for-react'

const { Title, Text } = Typography

export default function Portfolio() {
  const positions = [
    { key: '1', symbol: 'sh600519', name: '贵州茅台', shares: 100, cost: 1680, price: 1725.5, pnl: 4550, pnlPct: 2.71 },
    { key: '2', symbol: 'sz000858', name: '五粮液', shares: 500, cost: 152, price: 148.3, pnl: -1850, pnlPct: -2.43 },
    { key: '3', symbol: 'sh601318', name: '中国平安', shares: 300, cost: 45.5, price: 47.8, pnl: 690, pnlPct: 5.05 },
  ]

  const totalValue = positions.reduce((s, p) => s + p.shares * p.price, 0)
  const totalCost = positions.reduce((s, p) => s + p.shares * p.cost, 0)
  const totalPnl = totalValue - totalCost
  const totalPnlPct = ((totalPnl / totalCost) * 100).toFixed(2)

  const industryData = [
    { value: 40, name: '白酒' },
    { value: 25, name: '金融' },
    { value: 20, name: '消费' },
    { value: 15, name: '其他' },
  ]

  const pnlData = positions.map((p) => ({
    name: p.symbol,
    value: p.pnl,
    itemStyle: { color: p.pnl >= 0 ? '#10b981' : '#ef4444' },
  }))

  const columns = [
    { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 110, render: (s: string) => (
      <Text style={{ fontFamily: 'var(--font-mono)' }}>{s}</Text>
    )},
    { title: '名称', dataIndex: 'name', key: 'name', width: 120 },
    { title: '股数', dataIndex: 'shares', key: 'shares', width: 90, render: (v: number) => v.toLocaleString() },
    { title: '成本', dataIndex: 'cost', key: 'cost', width: 90, render: (v: number) => v.toFixed(2) },
    { title: '现价', dataIndex: 'price', key: 'price', width: 90, render: (v: number) => v.toFixed(2) },
    { title: '市值', key: 'value', width: 110, render: (_: any, r: any) => (r.shares * r.price).toFixed(0) },
    { title: '盈亏', key: 'pnl', width: 110, render: (_pnl: any, r: any) => (
      <Text style={{ color: r.pnl >= 0 ? '#10b981' : '#ef4444', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
        {r.pnl >= 0 ? <ArrowUpRight size={12} weight="bold" /> : <ArrowDownRight size={12} weight="bold" />}
        {' '}¥{Math.abs(r.pnl).toFixed(0)}
      </Text>
    )},
    { title: '盈亏%', key: 'pnlPct', width: 80, render: (_: any, r: any) => (
      <Tag color={r.pnlPct >= 0 ? 'green' : 'red'} style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
        {r.pnlPct >= 0 ? '+' : ''}{r.pnlPct.toFixed(2)}%
      </Tag>
    )},
  ]

  return (
    <div style={{ maxWidth: 1200 }}>
      <Title level={4} style={{ marginBottom: 4, fontWeight: 600, fontSize: 16 }}>投资组合</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 20, fontSize: 12 }}>
        持仓汇总与盈亏分析
      </Text>

      {/* Summary */}
      <Row gutter={[8, 8]} style={{ marginBottom: 16 }}>
        {[
          { label: '总市值', value: totalValue.toLocaleString(undefined, { maximumFractionDigits: 0 }) },
          { label: '总成本', value: totalCost.toLocaleString(undefined, { maximumFractionDigits: 0 }) },
          { label: '累计盈亏', value: `${totalPnl >= 0 ? '+' : ''}¥${totalPnl.toFixed(0)}`, color: totalPnl >= 0 ? '#10b981' : '#ef4444' },
          { label: '收益率', value: `${totalPnlPct}%`, color: totalPnl >= 0 ? '#10b981' : '#ef4444' },
          { label: '持仓数', value: String(positions.length) },
        ].map((s) => (
          <Col xs={24} sm={12} md={6} key={s.label}>
            <Card size="small" styles={{ body: { padding: '10px 14px' } }}>
              <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</div>
              <div style={{ fontSize: 15, fontWeight: 600, fontFamily: 'var(--font-mono)', marginTop: 2, color: s.color || 'var(--color-text-primary)' }}>
                {s.value}
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={16}>
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>持仓明细</span>}>
            <Table dataSource={positions} columns={columns} rowKey="key" pagination={false} size="small" scroll={{ x: 800 }} />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>行业分布</span>} styles={{ body: { padding: '12px' } }}>
            <ReactECharts
              option={{
                tooltip: { trigger: 'item' },
                series: [{
                  type: 'pie', radius: ['40%', '70%'], center: ['50%', '55%'],
                  avoidLabelOverlap: false,
                  label: { show: true, fontSize: 11, color: 'var(--color-text-secondary)' },
                  data: industryData,
                  itemStyle: { borderRadius: 4 },
                  color: ['var(--color-brand-primary)', '#10b981', '#f59e0b', '#6366f1'],
                }],
              }}
              style={{ height: 200 }}
            />
          </Card>
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>盈亏分布</span>} styles={{ body: { padding: '12px' } }} style={{ marginTop: 12 }}>
            <ReactECharts
              option={{
                tooltip: { trigger: 'axis' },
                grid: { left: 60, right: 8, top: 8, bottom: 24 },
                xAxis: { type: 'category', data: positions.map((p) => p.symbol), axisLine: { lineStyle: { color: 'var(--color-bg-elevated)' } } },
                yAxis: { type: 'value', axisLine: { show: false }, splitLine: { lineStyle: { color: 'var(--color-bg-surface)' } }, axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10, formatter: (v: number) => `¥${v >= 1000 ? (v/1000).toFixed(0)+'k' : v}` } },
                series: [{
                  type: 'bar', data: pnlData, barMaxWidth: 30,
                  itemStyle: { borderRadius: [2, 2, 0, 0] },
                }],
              }}
              style={{ height: 160 }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
