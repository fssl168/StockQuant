import { useState, useEffect } from 'react'
import {
  Card, Table, Button, Input, Select, Typography, Tag, Space, Row, Col,
  Radio, Modal, message, Statistic, Segmented, Tooltip, Divider, Badge,
  Alert, InputNumber,
} from 'antd'
import {
  CurrencyCircleDollar, Warning, ShoppingCart, XCircle,
  ArrowUpRight, ArrowDownLeft, Clock, CheckCircle,
} from '@phosphor-icons/react'
import type { ColumnsType } from 'antd/es/table'

import { useTradingStore } from '../stores/tradingStore'
import type { OrderSide, OrderType, OrderStatus, Order, TradeRecord } from '../types'

const { Text } = Typography

export default function Trading() {
  const brokerMode = useTradingStore((s) => s.brokerMode)
  const account = useTradingStore((s) => s.account)
  const orders = useTradingStore((s) => s.orders)
  const positions = useTradingStore((s) => s.positions)
  const trades = useTradingStore((s) => s.trades)
  const loading = useTradingStore((s) => s.loading)
  const placingOrder = useTradingStore((s) => s.placingOrder)
  const setBrokerMode = useTradingStore((s) => s.setBrokerMode)
  const refreshAll = useTradingStore((s) => s.refreshAll)
  const placeOrder = useTradingStore((s) => s.placeOrder)
  const cancelOrder = useTradingStore((s) => s.cancelOrder)

  // Order form state
  const [symbol, setSymbol] = useState('sh600519')
  const [side, setSide] = useState<OrderSide>('BUY')
  const [orderType, setOrderType] = useState<OrderType>('LIMIT')
  const [price, setPrice] = useState(1720)
  const [quantity, setQuantity] = useState(100)

  // Confirm modal
  const [confirmOpen, setConfirmOpen] = useState(false)

  useEffect(() => { refreshAll() }, [])
  // Auto-refresh every 10s when in paper mode
  useEffect(() => {
    if (!loading) {
      const timer = setInterval(() => refreshAll(), 10000)
      return () => clearInterval(timer)
    }
  }, [loading])

  const handlePlaceOrder = async () => {
    if (!symbol.trim()) {
      message.error('请输入股票代码')
      return
    }
    if (orderType !== 'MARKET' && price <= 0) {
      message.error('请输入有效价格')
      return
    }
    if (quantity <= 0 || quantity % 100 !== 0) {
      message.error('数量必须为正数且是100的整数倍')
      return
    }
    try {
      await placeOrder({ symbol, side, type: orderType, price, quantity })
      message.success('下单成功')
      setConfirmOpen(false)
    } catch (err) {
      console.error('[Trading] handlePlaceOrder failed:', err)
      message.error('下单失败')
    }
  }

  const handleCancel = async (orderId: string) => {
    try {
      await cancelOrder(orderId)
      message.success('撤单成功')
    } catch (err) {
      console.error('[Trading] handleCancel failed:', err)
      message.error('撤单失败')
    }
  }

  // Status tag helper
  const statusTag = (status: OrderStatus | undefined | null) => {
    if (!status) return <Tag>未知</Tag>
    const map: Record<OrderStatus, { color: string; label: string }> = {
      ORDER_PENDING: { color: 'default', label: '待提交' },
      ORDER_SUBMITTED: { color: 'processing', label: '已报' },
      ORDER_PARTIAL_FILL: { color: 'warning', label: '部分成交' },
      ORDER_FILLED: { color: 'success', label: '全部成交' },
      ORDER_CANCELLED: { color: 'error', label: '已撤销' },
      ORDER_REJECTED: { color: 'error', label: '拒单' },
    }
    const s = map[status]
    if (!s) return <Tag>{String(status)}</Tag>
    return <Tag color={s.color}>{s.label}</Tag>
  }

  return (
    <div style={{ maxWidth: 1280, margin: '0 auto' }}>
      {/* Page Title */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Typography.Title level={4} style={{ margin: 0 }}>交易执行</Typography.Title>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>下单 / 持仓 / 订单簿 / 成交记录</Typography.Text>
        </div>
        <Segmented
          size="small"
          value={brokerMode}
          onChange={(v) => setBrokerMode(v as 'paper' | 'live')}
          options={[
            { label: '模拟盘', value: 'paper' },
            { label: '实盘', value: 'live' },
          ]}
        />
      </div>

      {/* Live Mode Warning */}
      {brokerMode === 'live' && (
        <Alert
          type="warning"
          showIcon
          icon={<Warning />}
          message="实盘模式"
          description="当前为实盘交易模式，所有操作将发送至券商系统进行真实撮合。请谨慎操作。"
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Account Bar */}
      <Card size="small" style={{ marginBottom: 16 }} styles={{ body: { padding: '16px 20px' } }}>
        <Row gutter={[24, 0]} align="middle">
          <Col>
            <Statistic title="总权益" prefix={<CurrencyCircleDollar size={14} />} value={account?.totalEquity ?? 0} precision={2}
              formatter={(v) => `¥${Number(v ?? 0).toLocaleString()}`}
              valueStyle={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}
            />
          </Col>
          <Col><Divider type="vertical" style={{ height: 36 }} /></Col>
          <Col>
            <Statistic title="可用资金" value={account?.availableCash ?? 0} precision={2}
              formatter={(v) => `¥${Number(v ?? 0).toLocaleString()}`}
              valueStyle={{ fontSize: 15, color: 'var(--color-text-secondary)' }}
            />
          </Col>
          <Col><Divider type="vertical" style={{ height: 36 }} /></Col>
          <Col>
            <Statistic title="持仓市值" value={account?.marketValue ?? 0} precision={2}
              formatter={(v) => `¥${Number(v ?? 0).toLocaleString()}`}
              valueStyle={{ fontSize: 15, color: 'var(--color-text-secondary)' }}
            />
          </Col>
          <Col><Divider type="vertical" style={{ height: 36 }} /></Col>
          <Col>
            <Statistic title="今日盈亏" value={account?.dailyPnl ?? 0} precision={2}
              formatter={(v) => `${(Number(v ?? 0) >= 0 ? '+' : '')}${Number(v ?? 0).toFixed(2)}`}
              valueStyle={{
                fontSize: 15,
                color: (account?.dailyPnl ?? 0) >= 0 ? '#10b981' : '#ef4444',
                fontWeight: 600,
              }}
            />
          </Col>
          <Col><Divider type="vertical" style={{ height: 36 }} /></Col>
          <Col>
            <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>
              日收益率 {(account?.dailyPnlPct ?? 0).toFixed(2)}%
            </span>
          </Col>
        </Row>
      </Card>

      {/* Main Grid: Left (Order Form + Orders) | Right (Positions + Trades) */}
      <Row gutter={[12, 12]}>
        {/* LEFT COLUMN */}
        <Col xs={24} lg={10}>
          {/* Order Form */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <ShoppingCart size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> 下单
          </span>} style={{ marginBottom: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }} size={10}>
              {/* Symbol */}
              <div key="symbol">
                <Text type="secondary" style={{ fontSize: 11 }}>股票代码</Text>
                <Input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                  placeholder="e.g. sh600519" size="small" style={{ fontFamily: 'var(--font-mono)', marginTop: 4 }}
                  suffix={<span style={{ fontSize: 10, color: 'var(--color-text-tertiary)' }}>
                    {symbol.includes('600519') ? '贵州茅台' : symbol.includes('000858') ? '五粮液' : symbol.includes('601318') ? '中国平安' : ''}
                  </span>}
                />
              </div>

              {/* Side + Type row */}
              <Space key="side-type" size={8} style={{ width: '100%', justifyContent: 'space-between' }}>
                <div key="side-col" style={{ flex: 1 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>方向</Text>
                  <Radio.Group value={side} onChange={(e) => setSide(e.target.value)}
                    optionType="button" buttonStyle="solid" size="small" style={{ marginTop: 4, width: '100%' }}
                    options={[
                      { label: '买入', value: 'BUY' },
                      { label: '卖出', value: 'SELL' },
                    ]}
                  />
                </div>
                <div key="type-col" style={{ flex: 1 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>类型</Text>
                  <Select value={orderType} onChange={(v) => setOrderType(v as OrderType)}
                    size="small" style={{ width: '100%', marginTop: 4 }}
                    options={[
                      { label: '市价', value: 'MARKET' },
                      { label: '限价', value: 'LIMIT' },
                      { label: '止损', value: 'STOP' },
                    ]}
                  />
                </div>
              </Space>

              {/* Price */}
              <div key="price">
                <Text type="secondary" style={{ fontSize: 11 }}>
                  价格 {orderType === 'MARKET' ? '(市价)' : ''}
                </Text>
                <InputNumber value={price} onChange={(v) => setPrice(v ?? 0)}
                  disabled={orderType === 'MARKET'}
                  size="small" min={0} step={0.01} precision={2}
                  style={{ width: '100%', marginTop: 4 }}
                  formatter={(v) => `¥ ${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                />
              </div>

              {/* Quantity */}
              <div key="quantity">
                <Text type="secondary" style={{ fontSize: 11 }}>数量（股）</Text>
                <InputNumber value={quantity} onChange={(v) => setQuantity(v ?? 0)}
                  size="small" min={100} step={100}
                  style={{ width: '100%', marginTop: 4 }}
                  formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                />
                <Text type="secondary" style={{ fontSize: 10 }}>A 股最小单位 100 股</Text>
              </div>

              {/* Estimated amount */}
              <div key="estimated" style={{
                padding: '8px 12px', borderRadius: 6, background: 'var(--color-bg-elevated)',
                border: '1px solid var(--color-border-default)',
                display: 'flex', justifyContent: 'space-between',
              }}>
                <Text style={{ fontSize: 12 }}>预估金额</Text>
                <Text strong style={{ fontFamily: 'var(--font-mono)', color: side === 'BUY' ? '#ef4444' : '#10b981' }}>
                  ¥{((price || 0) * (quantity || 0)).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </Text>
              </div>

              {/* Action Buttons */}
              <Button
                key="submit"
                type="primary" block size="large"
                icon={side === 'BUY' ? <ArrowUpRight weight="bold" size={16} /> : <ArrowDownLeft weight="bold" size={16} />}
                loading={placingOrder}
                onClick={() => setConfirmOpen(true)}
                style={{ fontWeight: 600 }}
              >
                {side === 'BUY' ? '买入' : '卖出'} {symbol || '--'}
              </Button>
            </Space>
          </Card>

          {/* Order Book */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Clock size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> 订单簿
            <Badge count={orders.length} size="small" style={{ marginLeft: 4 }} />
          </span>}>
            <Table
              dataSource={orders}
              rowKey={(r) => r?.id || r?.order_id || Math.random().toString(36).slice(2)}
              size="small"
              pagination={false}
              scroll={{ y: 260 }}
              columns={[
                { title: 'ID', dataIndex: 'id', key: 'id', width: 80, render: (t: string) => <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{t?.split('-')?.[1] || t}</span> },
                { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 80, render: (t: string) => <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{t ?? ''}</span> },
                { title: '方向', dataIndex: 'side', key: 'side', width: 50, render: (t: string) =>
                  <Tag color={t === 'BUY' ? 'red' : 'green'} style={{ fontSize: 10 }}>{t === 'BUY' ? '买' : '卖'}</Tag>
                },
                { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 60, render: (n: number) => (n ?? 0).toLocaleString() },
                { title: '价格', dataIndex: 'price', key: 'price', width: 70, render: (n: number) => <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{(n ?? 0).toFixed(2)}</span> },
                { title: '状态', dataIndex: 'status', key: 'status', width: 90, render: (t: OrderStatus) => statusTag(t) },
                { title: '操作', key: 'action', width: 60, render: (_: unknown, r: Order) =>
                  (r.status === 'ORDER_PENDING' || r.status === 'ORDER_SUBMITTED') ? (
                    <Tooltip title="撤单"><Button type="link" danger size="small" icon={<XCircle size={14} />} onClick={() => handleCancel(r.id)} /></Tooltip>
                  ) : <span style={{ color: 'var(--color-text-disabled)' }}>-</span>
                },
              ] as ColumnsType<Order>}
            />
          </Card>
        </Col>

        {/* RIGHT COLUMN */}
        <Col xs={24} lg={14}>
          {/* Positions Panel */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <CurrencyCircleDollar size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> 当前持仓
          </span>} style={{ marginBottom: 12 }}>
            <Table
              dataSource={positions}
              rowKey="symbol"
              size="small"
              pagination={false}
              columns={[
                { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 85, render: (t: string) => <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{t ?? ''}</span> },
                { title: '名称', dataIndex: 'name', key: 'name', width: 80 },
                { title: '持仓', dataIndex: 'shares', key: 'shares', width: 60, render: (n: number) => (n ?? 0).toLocaleString() },
                { title: '成本价', dataIndex: 'cost', key: 'cost', width: 70, render: (n: number) => <span style={{ fontFamily: 'var(--font-mono)' }}>{(n ?? 0).toFixed(2)}</span> },
                { title: '现价', dataIndex: 'price', key: 'price', width: 70, render: (n: number) => <span style={{ fontFamily: 'var(--font-mono)' }}>{(n ?? 0).toFixed(2)}</span> },
                { title: '盈亏', dataIndex: 'pnl', key: 'pnl', width: 90, render: (n: number) =>
                  <span style={{ color: (n ?? 0) >= 0 ? '#10b981' : '#ef4444', fontFamily: 'var(--font-mono)', fontWeight: 500 }}>
                    {(n ?? 0) >= 0 ? '+' : ''}{(n ?? 0).toFixed(0)}
                  </span>
                },
                { title: '收益率', dataIndex: 'pnlPct', key: 'pnlPct', width: 70, render: (n: number) =>
                  <Tag color={(n ?? 0) >= 0 ? 'green' : 'red'} style={{ fontFamily: 'var(--font-mono)' }}>
                    {(n ?? 0) >= 0 ? '+' : ''}{(n ?? 0).toFixed(2)}%
                  </Tag>
                },
              ]}
            />
          </Card>

          {/* Trade History */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <CheckCircle size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> 成交记录
          </span>}>
            <Table
              dataSource={trades}
              rowKey={(r) => r?.id || r?.trade_id || Math.random().toString(36).slice(2)}
              size="small"
              pagination={{ pageSize: 8, size: 'small' }}
              scroll={{ x: 500 }}
              columns={[
                { title: '时间', dataIndex: 'timestamp', key: 'time', width: 140, render: (t: string) =>
                  t ? new Date(t).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '-'
                },
                { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 80, render: (t: string) => <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{t ?? ''}</span> },
                { title: '方向', dataIndex: 'side', key: 'side', width: 50, render: (t: string) =>
                  <Tag color={(t ?? '') === 'BUY' ? 'red' : 'green'} style={{ fontSize: 10 }}>{(t ?? '') === 'BUY' ? '买' : '卖'}</Tag>
                },
                { title: '价格', dataIndex: 'price', key: 'price', width: 70, render: (n: number) => <span style={{ fontFamily: 'var(--font-mono)' }}>{(n ?? 0).toFixed(2)}</span> },
                { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 60, render: (n: number) => (n ?? 0).toLocaleString() },
                { title: '手续费', dataIndex: 'commission', key: 'commission', width: 70, render: (n: number) => <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{(n ?? 0).toFixed(2)}</span> },
              ] as ColumnsType<TradeRecord>}
            />
          </Card>
        </Col>
      </Row>

      {/* Confirm Modal */}
      <Modal
        title="确认下单"
        open={confirmOpen}
        onOk={handlePlaceOrder}
        onCancel={() => setConfirmOpen(false)}
        okText="确认下单"
        cancelText="取消"
        confirmLoading={placingOrder}
        okType={side === 'BUY' ? 'primary' : 'danger'}
      >
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <div key="stock" style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Text type="secondary">股票</Text>
            <Text strong>{symbol || '--'}</Text>
          </div>
          <div key="side" style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Text type="secondary">方向</Text>
            <Tag color={side === 'BUY' ? 'red' : 'green'}>{side === 'BUY' ? '买入' : '卖出'}</Tag>
          </div>
          <div key="type" style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Text type="secondary">类型</Text>
            <Text>{orderType === 'MARKET' ? '市价' : orderType === 'LIMIT' ? '限价' : '止损'}</Text>
          </div>
          <div key="price" style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Text type="secondary">价格</Text>
            <Text strong style={{ fontFamily: 'var(--font-mono)' }}>
              {orderType === 'MARKET' ? '市价' : `¥${price.toFixed(2)}`}
            </Text>
          </div>
          <div key="quantity" style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Text type="secondary">数量</Text>
            <Text strong style={{ fontFamily: 'var(--font-mono)' }}>{quantity.toLocaleString()} 股</Text>
          </div>
          <Divider key="divider-1" style={{ margin: '8px 0' }} />
          {(() => {
            const amount = (price || 0) * (quantity || 0)
            const commission = Math.max(amount * 0.00025, 5)
            const stampTax = side === 'SELL' ? amount * 0.0005 : 0
            const transferFee = amount * 0.00001
            const totalFee = commission + stampTax + transferFee
            return (
              <>
                <div key="commission" style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Text type="secondary">佣金（万2.5，最低5元）</Text>
                  <Text style={{ fontFamily: 'var(--font-mono)' }}>¥{commission.toFixed(2)}</Text>
                </div>
                <div key="stamp" style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Text type="secondary">印花税（卖出千1）</Text>
                  <Text style={{ fontFamily: 'var(--font-mono)' }}>¥{stampTax.toFixed(2)}</Text>
                </div>
                <div key="transfer" style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Text type="secondary">过户费（十万1）</Text>
                  <Text style={{ fontFamily: 'var(--font-mono)' }}>¥{transferFee.toFixed(2)}</Text>
                </div>
                <Divider key="divider-fee" style={{ margin: '4px 0' }} />
                <div key="total-fee" style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Text strong>总费用</Text>
                  <Text strong style={{ fontFamily: 'var(--font-mono)', color: '#f59e0b' }}>¥{totalFee.toFixed(2)}</Text>
                </div>
              </>
            )
          })()}
          <Divider key="divider-2" style={{ margin: '8px 0' }} />
          {/* A-stock trading rules reminder (Task 2.12) */}
          <div key="rules" style={{
            marginTop: 8, padding: '8px 12px', borderRadius: 6,
            background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.15)',
            fontSize: 11, color: 'var(--color-text-secondary)',
          }}>
            <div>A 股规则：T+1 交易，买入当日不可卖出</div>
            <div>最小交易单位：100 股</div>
          </div>
        </Space>
      </Modal>
    </div>
  )
}
