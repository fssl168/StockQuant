import { useEffect, useState } from 'react'
import { Card, Row, Col, Table, Typography, Tag, Button } from 'antd'
import { ArrowUpRight, ArrowDownRight, CurrencyCircleDollar } from '@phosphor-icons/react'
import { useNavigate } from 'react-router-dom'
import client from '@/api/client'
import PortfolioSummary from '@/components/Portfolio/PortfolioSummary'
import SectorPieChart from '@/components/Portfolio/SectorPieChart'
import PnLTable from '@/components/Portfolio/PnLTable'

const { Title, Text } = Typography

export default function Portfolio() {
  const navigate = useNavigate()
  const [positions, setPositions] = useState([
    { key: '1', symbol: 'sh600519', name: '贵州茅台', shares: 100, cost: 1680, price: 1725.5, pnl: 4550, pnlPct: 2.71 },
    { key: '2', symbol: 'sz000858', name: '五粮液', shares: 500, cost: 152, price: 148.3, pnl: -1850, pnlPct: -2.43 },
    { key: '3', symbol: 'sh601318', name: '中国平安', shares: 300, cost: 45.5, price: 47.8, pnl: 690, pnlPct: 5.05 },
  ])

  const [summary, setSummary] = useState<{ totalValue: number; totalCost: number; totalPnl: number; totalPnlPct: number } | null>(null)

  useEffect(() => {
    client.get('/portfolio/positions')
      .then((data) => { if (Array.isArray(data) && data.length > 0) setPositions(data) })
      .catch(() => { /* use default mock data */ })
    client.get('/portfolio/account')
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

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={16}>
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>持仓明细</span>}>
            <Table dataSource={positions} columns={columns} rowKey="key" pagination={false} size="small" scroll={{ x: 800 }} />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <SectorPieChart data={industryData} />
          <PnLTable positions={positions.map((p) => ({ symbol: p.symbol, name: p.name, pnl: p.pnl, pnlPct: p.pnlPct }))} />
        </Col>
      </Row>
    </div>
  )
}
