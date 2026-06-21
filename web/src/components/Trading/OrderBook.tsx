

import { useMemo } from 'react'
import { Card, Typography, Row, Col } from 'antd'
import { ArrowUp, ArrowDown } from '@phosphor-icons/react'

const { Text } = Typography

export interface OrderBookLevel {
  price: number
  volume: number
  total?: number  // 累计量
}

export interface OrderBookData {
  bids: OrderBookLevel[]   // 买方五档
  asks: OrderBookLevel[]   // 卖方五档
  lastPrice?: number       // 最新价
  change?: number          // 涨跌
  changePercent?: number   // 涨跌幅(%)
  timestamp?: number       // 更新时间戳
}

interface OrderBookProps {
  data: OrderBookData
  height?: number
}

// 模拟数据生成器（实际项目中替换为 WebSocket 推送）
export function generateMockOrderBook(lastPrice: number = 100.0): OrderBookData {
  const bids: OrderBookLevel[] = []
  const asks: OrderBookLevel[] = []
  let bidTotal = 0
  let askTotal = 0

  for (let i = 0; i < 5; i++) {
    const bidPrice = lastPrice - (i + 1) * 0.01 * lastPrice
    const bidVolume = Math.floor(Math.random() * 10000) + 1000
    bidTotal += bidVolume
    bids.push({
      price: Number(bidPrice.toFixed(2)),
      volume: bidVolume,
      total: bidTotal,
    })

    const askPrice = lastPrice + (i + 1) * 0.01 * lastPrice
    const askVolume = Math.floor(Math.random() * 10000) + 1000
    askTotal += askVolume
    asks.push({
      price: Number(askPrice.toFixed(2)),
      volume: askVolume,
      total: askTotal,
    })
  }

  // 模拟涨跌
  const change = (Math.random() - 0.5) * 2
  const changePercent = (change / lastPrice) * 100

  return {
    bids,
    asks,
    lastPrice,
    change: Number(change.toFixed(2)),
    changePercent: Number(changePercent.toFixed(2)),
    timestamp: Date.now(),
  }
}

function formatVolume(vol: number): string {
  if (vol >= 10000) {
    return (vol / 10000).toFixed(1) + '万'
  }
  return vol.toString()
}

function formatPrice(price: number | undefined): string {
  if (price === undefined) return '--'
  return price.toFixed(2)
}

export default function OrderBook({ data, height = 320 }: OrderBookProps) {
  const { bids, asks, lastPrice, change, changePercent } = data

  // 计算最大累计量用于进度条宽度
  const maxTotal = useMemo(() => {
    const maxBid = bids[bids.length - 1]?.total || 1
    const maxAsk = asks[asks.length - 1]?.total || 1
    return Math.max(maxBid, maxAsk)
  }, [bids, asks])

  const priceColor = useMemo(() => {
    if (change === undefined) return '#666'
    return change > 0 ? '#e74c3c' : change < 0 ? '#27ae60' : '#666'
  }, [change])

  const renderRow = (
    level: OrderBookLevel,
    type: 'bid' | 'ask',
    index: number
  ) => {
    const widthPercent = ((level.total || level.volume) / maxTotal) * 100
    const barColor = type === 'bid' ? 'rgba(231, 76, 60, 0.15)' : 'rgba(39, 174, 96, 0.15)'
    const textColor = type === 'bid' ? '#e74c3c' : '#27ae60'
    const align = type === 'bid' ? 'left' : 'right'

    return (
      <Row
        key={`${type}-${index}`}
        className="orderbook-row"
        style={{ position: 'relative', margin: '2px 0' }}
      >
        {/* 背景进度条 */}
        <div
          style={{
            position: 'absolute',
            [type === 'bid' ? 'right' : 'left']: 0,
            top: 0,
            bottom: 0,
            width: `${widthPercent}%`,
            background: barColor,
            zIndex: 0,
          }}
        />
        
        {/* 价格 */}
        <Col span={8} style={{ textAlign: align, zIndex: 1, padding: '0 8px' }}>
          <Text strong style={{ color: textColor }}>
            {formatPrice(level.price)}
          </Text>
        </Col>
        
        {/* 数量 */}
        <Col span={8} style={{ textAlign: 'center', zIndex: 1 }}>
          <Text>{formatVolume(level.volume)}</Text>
        </Col>
        
        {/* 累计 */}
        <Col span={8} style={{ textAlign: type === 'bid' ? 'right' : 'left', zIndex: 1, padding: '0 8px' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {formatVolume(level.total || 0)}
          </Text>
        </Col>
      </Row>
    )
  }

  return (
    <Card
      size="small"
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>盘口</span>
          {lastPrice !== undefined && (
            <span style={{ color: priceColor, fontWeight: 600 }}>
              {formatPrice(lastPrice)}
            </span>
          )}
          {change !== undefined && (
            <span style={{ color: priceColor, fontSize: 12, display: 'flex', alignItems: 'center' }}>
              {change > 0 ? <ArrowUp size={14} /> : change < 0 ? <ArrowDown size={14} /> : null}
              {formatPrice(change)} ({changePercent?.toFixed(2)}%)
            </span>
          )}
        </div>
      }
      styles={{ body: { padding: '8px', height: height - 46, overflow: 'auto' } }}
    >
      {/* 表格头部 */}
      <Row style={{ marginBottom: 4, opacity: 0.6 }}>
        <Col span={8} style={{ textAlign: 'left', padding: '0 8px' }}>
          <Text type="secondary" style={{ fontSize: 11 }}>卖价</Text>
        </Col>
        <Col span={8} style={{ textAlign: 'center' }}>
          <Text type="secondary" style={{ fontSize: 11 }}>数量</Text>
        </Col>
        <Col span={8} style={{ textAlign: 'right', padding: '0 8px' }}>
          <Text type="secondary" style={{ fontSize: 11 }}>累计</Text>
        </Col>
      </Row>

      {/* 卖盘五档 */}
      <div style={{ marginBottom: 8 }}>
        {asks.slice().reverse().map((level, idx) => renderRow(level, 'ask', idx))}
      </div>

      {/* 分隔线 */}
      <div style={{ 
        height: 1, 
        background: '#e8e8e8', 
        margin: '8px 0',
        position: 'relative'
      }}>
        <div style={{
          position: 'absolute',
          left: '50%',
          top: '-4px',
          transform: 'translateX(-50%)',
          background: '#fff',
          padding: '0 8px',
          fontSize: 11,
          color: '#999'
        }}>
          {formatPrice(lastPrice)}
        </div>
      </div>

      {/* 买盘五档 */}
      <div>
        {bids.map((level, idx) => renderRow(level, 'bid', idx))}
      </div>
    </Card>
  )
}


