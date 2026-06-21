# -*- coding: utf-8 -*-
"""TickDataPanel 组件 - 逐笔成交记录"""

import { useState, useEffect } from 'react'
import { Card, Table, Typography, Tag, Space } from 'antd'
import { ArrowUp, ArrowDown } from '@phosphor-icons/react'

const { Text } = Typography

export interface TickRecord {
  time: string        // 时间 HH:MM:SS
  price: number       // 成交价
  volume: number      // 成交量
  turnover: number    // 成交额
  type: 'buy' | 'sell' | 'auto'  // 主动买/卖/自动
}

interface TickDataPanelProps {
  symbol?: string
  height?: number
  maxRecords?: number
}

// 模拟逐笔成交数据生成
export function generateMockTicks(basePrice: number = 100, count: number = 50): TickRecord[] {
  const ticks: TickRecord[] = []
  let price = basePrice

  for (let i = 0; i < count; i++) {
    // 价格随机波动
    const change = (Math.random() - 0.5) * 0.002 * price
    price = price + change
    
    // 随机成交量
    const volume = Math.floor(Math.random() * 5000) + 100
    const turnover = volume * price
    
    // 随机主动买/卖
    const rand = Math.random()
    let type: 'buy' | 'sell' | 'auto' = 'auto'
    if (rand < 0.4) type = 'buy'
    else if (rand < 0.8) type = 'sell'
    
    // 时间递进
    const totalSeconds = 9 * 3600 + 30 * 60 + i * 5
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)
    const seconds = totalSeconds % 60
    const time = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`

    ticks.push({
      time,
      price: Number(price.toFixed(2)),
      volume,
      turnover: Number(turnover.toFixed(0)),
      type,
    })
  }

  return ticks.reverse() // 最新在前
}

function formatVolume(vol: number): string {
  if (vol >= 10000) return (vol / 10000).toFixed(1) + '万'
  if (vol >= 1000) return (vol / 1000).toFixed(1) + '千'
  return vol.toString()
}

function formatTurnover(amt: number): string {
  if (amt >= 100000000) return (amt / 100000000).toFixed(2) + '亿'
  if (amt >= 10000) return (amt / 10000).toFixed(1) + '万'
  if (amt >= 1000) return (amt / 1000).toFixed(1) + '千'
  return amt.toString()
}

export default function TickDataPanel({ 
  symbol = '', 
  height = 320,
  maxRecords = 100 
}: TickDataPanelProps) {
  const [ticks, setTicks] = useState<TickRecord[]>([])

  // 模拟实时更新
  useEffect(() => {
    // 初始数据
    setTicks(generateMockTicks(100, maxRecords))

    // 每3秒更新一条
    const interval = setInterval(() => {
      setTicks(prev => {
        const newTick = generateMockTicks(100, 1)[0]
        const updated = [newTick, ...prev.slice(0, maxRecords - 1)]
        return updated
      })
    }, 3000)

    return () => clearInterval(interval)
  }, [maxRecords])

  const columns = [
    {
      title: '时间',
      dataIndex: 'time',
      key: 'time',
      width: 80,
      render: (time: string) => (
        <Text type="secondary" style={{ fontSize: 12 }}>{time}</Text>
      ),
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      width: 80,
      render: (price: number, record: TickRecord) => {
        const color = record.type === 'buy' ? '#e74c3c' : record.type === 'sell' ? '#27ae60' : '#666'
        return (
          <Text strong style={{ color, fontSize: 12 }}>
            {price.toFixed(2)}
          </Text>
        )
      },
    },
    {
      title: '成交量',
      dataIndex: 'volume',
      key: 'volume',
      width: 80,
      render: (vol: number) => (
        <Text style={{ fontSize: 12 }}>{formatVolume(vol)}</Text>
      ),
    },
    {
      title: '性质',
      dataIndex: 'type',
      key: 'type',
      width: 70,
      render: (type: string) => {
        const config = {
          buy: { color: 'red', text: '买', icon: <ArrowUp size={12} /> },
          sell: { color: 'green', text: '卖', icon: <ArrowDown size={12} /> },
          auto: { color: 'default', text: '自', icon: null },
        }
        const { color, text, icon } = config[type as keyof typeof config] || config.auto
        return (
          <Tag color={color} style={{ margin: 0, fontSize: 11, padding: '0 4px' }}>
            <Space size={2}>
              {icon}
              {text}
            </Space>
          </Tag>
        )
      },
    },
  ]

  return (
    <Card
      size="small"
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>逐笔成交</span>
          {symbol && <Text type="secondary" style={{ fontSize: 12 }}>{symbol}</Text>}
          <Text type="secondary" style={{ fontSize: 11 }}>(实时)</Text>
        </div>
      }
      styles={{ body: { padding: 0, height: height - 46, overflow: 'auto' } }}
    >
      <Table
        dataSource={ticks}
        columns={columns}
        rowKey={(record, index) => `${record.time}-${index}`}
        pagination={false}
        size="small"
        scroll={{ y: height - 60 }}
      />
    </Card>
  )
}

