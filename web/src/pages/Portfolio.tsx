import { useEffect, useState } from 'react'
import { Card, Row, Col, Table, Typography, Tag, Button, Skeleton, Tabs } from 'antd'
import { ArrowUpRight, ArrowDownRight, CurrencyCircleDollar } from '@phosphor-icons/react'
import { useNavigate } from 'react-router-dom'
import ReactECharts from 'echarts-for-react'
import dayjs from 'dayjs'
import client from '@/api/client'
import PortfolioSummary from '@/components/Portfolio/PortfolioSummary'
import SectorPieChart from '@/components/Portfolio/SectorPieChart'
import PnLTable from '@/components/Portfolio/PnLTable'

const { Title, Text } = Typography

export default function Portfolio() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [positions, setPositions] = useState([
    { key: '1', symbol: 'sh600519', name: '贵州茅台', shares: 100, cost: 1680, price: 1725.5, pnl: 4550, pnlPct: 2.71 },
    { key: '2', symbol: 'sz000858', name: '五粮液', shares: 500, cost: 152, price: 148.3, pnl: -1850, pnlPct: -2.43 },
    { key: '3', symbol: 'sh601318', name: '中国平安', shares: 300, cost: 45.5, price: 47.8, pnl: 690, pnlPct: 5.05 },
  ])

  const [summary, setSummary] = useState<{ totalValue: number; totalCost: number; totalPnl: number; totalPnlPct: number } | null>(null)

  useEffect(() => {
    const p1 = client.get('/portfolio/positions')
      .then((data) => { if (Array.isArray(data) && data.length > 0) setPositions(data) })
      .catch(() => { /* use default mock data */ })
    const p2 = client.get('/portfolio/account')
      .then((data: any) => {
        if (data) {
          setSummary({
            totalValue: data.totalEquity ?? data.marketValue ?? 0,
            totalCost: (data.totalEquity ?? 0) - (data.dailyPnl ?? 0),
            totalPnl: data.dailyPnl ?? 0,
            totalPnlPct: data.dailyPnlPct ?? 0,
          })
        }
      })
      .catch(() => { /* use default mock data */ })
    Promise.all([p1, p2]).finally(() => setLoading(false))
  }, [])

  const totalValue = summary?.totalValue ?? positions.reduce((s, p) => s + p.shares * p.price, 0)
  const totalCost = summary?.totalCost ?? positions.reduce((s, p) => s + p.shares * p.cost, 0)
  const totalPnl = summary?.totalPnl ?? (totalValue - totalCost)
  const totalPnlPct = summary?.totalPnlPct ?? Number(((totalPnl / totalCost) * 100).toFixed(2))

  const industryData = [
    { sector: '白酒', value: 40, weight: 40 },
    { sector: '金融', value: 25, weight: 25 },
    { sector: '消费', value: 20, weight: 20 },
    { sector: '其他', value: 15, weight: 15 },
  ]

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
      <Text style={{ color: r.pnl >= 0 ? 'var(--color-success)' : 'var(--color-danger)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
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

  const tradeHistory = [
    { tradeId: 'T001', symbol: 'sh600519', name: '贵州茅台', side: 'BUY', quantity: 100, price: 1680.0, amount: 168000, time: '2026-05-20 10:30' },
    { tradeId: 'T002', symbol: 'sz000858', name: '五粮液', side: 'BUY', quantity: 500, price: 152.0, amount: 76000, time: '2026-05-18 14:15' },
    { tradeId: 'T003', symbol: 'sh601318', name: '中国平安', side: 'BUY', quantity: 300, price: 45.5, amount: 13650, time: '2026-05-15 09:45' },
    { tradeId: 'T004', symbol: 'sh600036', name: '招商银行', side: 'SELL', quantity: 200, price: 38.2, amount: 7640, time: '2026-05-12 11:00' },
    { tradeId: 'T005', symbol: 'sz000333', name: '美的集团', side: 'SELL', quantity: 150, price: 62.8, amount: 9420, time: '2026-05-10 13:30' },
  ]

  const tradeColumns = [
    { title: '时间', dataIndex: 'time', key: 'time', width: 140 },
    { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 110, render: (s: string) => <Text style={{ fontFamily: 'var(--font-mono)' }}>{s}</Text> },
    { title: '名称', dataIndex: 'name', key: 'name', width: 100 },
    { title: '方向', dataIndex: 'side', key: 'side', width: 70, render: (s: string) => <Tag color={s === 'BUY' ? 'green' : 'red'}>{s === 'BUY' ? '买入' : '卖出'}</Tag> },
    { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 80, render: (v: number) => v.toLocaleString() },
    { title: '价格', dataIndex: 'price', key: 'price', width: 90, render: (v: number) => v.toFixed(2) },
    { title: '金额', dataIndex: 'amount', key: 'amount', width: 100, render: (v: number) => `¥${v.toLocaleString()}` },
  ]

  const riskMetrics = [
    { label: 'VaR (95%)', value: '¥-12,345', color: 'var(--color-danger)' },
    { label: '波动率', value: '18.5%' },
    { label: '夏普比率', value: '1.42', color: 'var(--color-success)' },
    { label: '最大回撤', value: '-8.3%', color: 'var(--color-danger)' },
    { label: 'Beta', value: '0.87' },
    { label: 'Alpha', value: '3.2%', color: 'var(--color-success)' },
  ]

  const equityDates = Array.from({ length: 30 }, (_, i) => dayjs().subtract(29 - i, 'day').format('MM-DD'))
  const equityValues = Array.from({ length: 30 }, (_, i) => {
    const base = 1200000
    return Math.round(base + i * 1500 + Math.sin(i / 3) * 8000 + Math.random() * 5000)
  })

  if (loading) {
    return (
      <div style={{ maxWidth: 1200 }}>
        <Skeleton active paragraph={{ rows: 8 }} />
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 1200 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <Title level={4} style={{ margin: 0, fontWeight: 600, fontSize: 16 }}>投资组合</Title>
        <Button type="primary" size="small" icon={<CurrencyCircleDollar size={14} />} onClick={() => navigate('/trading')}>
          快捷交易
        </Button>
      </div>
      <Text type="secondary" style={{ display: 'block', marginBottom: 20, fontSize: 12 }}>
        持仓汇总与盈亏分析
      </Text>

      {/* Summary */}
      <PortfolioSummary
        totalValue={totalValue}
        totalCost={totalCost}
        totalPnl={totalPnl}
        totalPnlPct={totalPnlPct}
        positionCount={positions.length}
      />

      {/* Equity Curve */}
      <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>资金曲线</span>} style={{ marginBottom: 12 }}>
        <ReactECharts
          option={{
            tooltip: { trigger: 'axis' },
            grid: { left: 60, right: 8, top: 8, bottom: 24 },
            xAxis: { type: 'category', data: equityDates, axisLine: { lineStyle: { color: 'var(--color-chart-border)' } }, axisLabel: { color: 'var(--color-chart-axis)', fontSize: 10 } },
            yAxis: { type: 'value', splitLine: { lineStyle: { color: 'var(--color-chart-grid)' } }, axisLabel: { color: 'var(--color-chart-axis)', fontSize: 10, formatter: (v: number) => `${(v / 10000).toFixed(0)}万` } },
            series: [{
              type: 'line', data: equityValues, smooth: true, showSymbol: false,
              lineStyle: { color: 'var(--color-brand-primary)', width: 2 },
              areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(59,130,246,0.3)' }, { offset: 1, color: 'rgba(59,130,246,0)' }] } },
            }],
          }}
          style={{ height: 200 }}
        />
      </Card>

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={16}>
          <Card size="small" style={{ height: '100%' }}>
            <Tabs defaultActiveKey="positions" size="small" items={[
              {
                key: 'positions',
                label: '持仓明细',
                children: <Table dataSource={positions} columns={columns} rowKey="key" pagination={false} size="small" scroll={{ x: 800 }} />,
              },
              {
                key: 'history',
                label: '历史交易',
                children: <Table dataSource={tradeHistory} columns={tradeColumns} rowKey="tradeId" pagination={{ pageSize: 5, size: 'small' }} size="small" />,
              },
            ]} />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <SectorPieChart data={industryData} />
          <PnLTable positions={positions.map((p) => ({ symbol: p.symbol, name: p.name, pnl: p.pnl, pnlPct: p.pnlPct }))} />
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>风险指标</span>} style={{ marginTop: 12 }}>
            <Row gutter={[8, 8]}>
              {riskMetrics.map((m) => (
                <Col xs={12} key={m.label}>
                  <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', textTransform: 'uppercase' }}>{m.label}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, fontFamily: 'var(--font-mono)', color: m.color || 'var(--color-text-primary)' }}>
                    {m.value}
                  </div>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
