# -*- coding: utf-8 -*-
"""TradingDemo Page - Demo page for professional trading components"""

import { useState, useEffect } from 'react'
import { Card, Row, Col, Tabs, Select, Typography, Space, Statistic } from 'antd'
import { 
  OrderBook, 
  generateMockOrderBook,
  DepthChart, 
  TimeShareChart, 
  generateMockTimeShare,
  TickDataPanel 
} from '@/components/Trading'

const { Title, Text } = Typography
const { Option } = Select

const SAMPLE_SYMBOLS = [
  { value: 'sh600519', label: '贵州茅台' },
  { value: 'sh600036', label: '招商银行' },
  { value: 'sz000858', label: '五粮液' },
  { value: 'sz002594', label: '比亚迪' },
]

export default function TradingDemo() {
  const [symbol, setSymbol] = useState('sh600519')
  const [orderBookData, setOrderBookData] = useState(generateMockOrderBook(1720))
  const [timeShareData, setTimeShareData] = useState(generateMockTimeShare(1720, 240))
  
  // Simulate real-time updates
  useEffect(() => {
    const interval = setInterval(() => {
      const newPrice = orderBookData.lastPrice! + (Math.random() - 0.5) * 2
      setOrderBookData(generateMockOrderBook(newPrice))
    }, 3000)
    
    return () => clearInterval(interval)
  }, [orderBookData.lastPrice])
  
  const handleSymbolChange = (newSymbol: string) => {
    setSymbol(newSymbol)
    const basePrice = 100 + Math.random() * 100
    setOrderBookData(generateMockOrderBook(basePrice))
    setTimeShareData(generateMockTimeShare(basePrice, 240))
  }

  const tabItems = [
    {
      key: 'orderbook',
      label: '盘口',
      children: (
        <OrderBook 
          data={orderBookData} 
          height={400}
        />
      ),
    },
    {
      key: 'depth',
      label: '深度图',
      children: (
        <DepthChart 
          data={orderBookData} 
          height={400}
          title={`${SAMPLE_SYMBOLS.find(s => s.value === symbol)?.label || symbol} - 市场深度`}
        />
      ),
    },
    {
      key: 'timeshare',
      label: '分时',
      children: (
        <TimeShareChart 
          data={timeShareData}
          height={400}
          title="分时走势"
          symbol={symbol}
        />
      ),
    },
    {
      key: 'tick',
      label: '逐笔',
      children: (
        <TickDataPanel 
          symbol={symbol}
          height={400}
          maxRecords={50}
        />
      ),
    },
  ]

  return (
    <div style={{ padding: 16, background: '#f5f5f5', minHeight: '100vh' }}>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Card size="small">
            <Space>
              <Text strong>选择股票：</Text>
              <Select 
                value={symbol} 
                onChange={handleSymbolChange}
                style={{ width: 200 }}
              >
                {SAMPLE_SYMBOLS.map(s => (
                  <Option key={s.value} value={s.value}>
                    {s.label} ({s.value})
                  </Option>
                ))}
              </Select>
              <Text type="secondary">| 模拟数据，每3秒更新</Text>
            </Space>
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Card 
            size="small" 
            title="实时行情组件"
            style={{ marginBottom: 16 }}
          >
            <Tabs items={tabItems} />
          </Card>
        </Col>
        
        <Col xs={24} lg={12}>
          <Card size="small" title="组件说明" style={{ marginBottom: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text strong>OrderBook 盘口</Text>
                <br />
                <Text type="secondary">显示买五卖五盘口，含背景进度条和实时涨跌</Text>
              </div>
              <div>
                <Text strong>DepthChart 深度图</Text>
                <br />
                <Text type="secondary">展示买卖挂单量累计分布，支持hover查看详情</Text>
              </div>
              <div>
                <Text strong>TimeShareChart 分时图</Text>
                <br />
                <Text type="secondary">分时走势 + 均价线 + 成交量柱状图，双坐标轴</Text>
              </div>
              <div>
                <Text strong>TickDataPanel 逐笔</Text>
                <br />
                <Text type="secondary">逐笔成交记录，实时更新，3秒刷新</Text>
              </div>
            </Space>
          </Card>
          
          <Card size="small" title="技术栈">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text>
                • React + TypeScript + Ant Design
                <br />
                • ECharts 图表库
                <br />
                • WebSocket 实时推送（待集成）
                <br />
                • React Query 状态管理
              </Text>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
