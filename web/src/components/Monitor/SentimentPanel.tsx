import { useState, useEffect } from 'react'
import { Typography, Tag, Spin } from 'antd'
import ReactECharts from 'echarts-for-react'
import client from '@/api/client'

const { Text } = Typography

interface SentimentData {
  symbol: string
  score: number
  trend: number[]
  topics: string[]
  summary: string
  news_count?: number
}

interface SentimentPanelProps {
  symbol: string | null
  height?: number  // default 300
}

export default function SentimentPanel({ symbol, height = 300 }: SentimentPanelProps) {
  const [data, setData] = useState<SentimentData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!symbol) {
      setData(null)
      return
    }
    setLoading(true)
    setError('')
    client.get(`/api/ai/sentiment?symbol=${symbol}`)
      .then((res: any) => setData(res))
      .catch(() => setError('获取情绪数据失败'))
      .finally(() => setLoading(false))
  }, [symbol])

  if (!symbol) {
    return (
      <div style={{ textAlign: 'center', padding: 20, color: 'var(--color-text-tertiary)', fontSize: 12 }}>
        选择标的查看情绪数据
      </div>
    )
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 20 }}>
        <Spin size="small" />
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: 20, color: 'var(--color-danger)', fontSize: 12 }}>
        {error}
      </div>
    )
  }

  if (!data) return null

  // 情绪颜色：低分红、中分黄、高分绿
  const sentimentColor = data.score >= 70 ? '#10b981' : data.score >= 40 ? '#eab308' : '#ef4444'
  const sentimentLabel = data.score >= 80 ? '极度乐观' : data.score >= 60 ? '乐观' : data.score >= 40 ? '中性' : data.score >= 20 ? '谨慎' : '悲观'

  // Gauge chart option
  const gaugeOption = {
    series: [{
      type: 'gauge',
      startAngle: 220,
      endAngle: -40,
      min: 0,
      max: 100,
      radius: '90%',
      center: ['50%', '55%'],
      progress: {
        show: true,
        width: 12,
        roundCap: true,
        itemStyle: { color: sentimentColor },
      },
      pointer: { show: false },
      axisLine: {
        lineStyle: { width: 12, color: [[1, '#18181b']] },
      },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      detail: {
        fontSize: 24,
        fontWeight: 'bold',
        formatter: '{value}',
        color: sentimentColor,
        offsetCenter: [0, '20%'],
      },
      data: [{ value: data.score, name: sentimentLabel }],
    }],
  }

  // Trend line chart option
  const trendOption = {
    backgroundColor: 'transparent',
    grid: { left: 40, right: 16, top: 16, bottom: 24 },
    xAxis: {
      type: 'category',
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      axisLine: { lineStyle: { color: '#27272a' } },
      axisLabel: { color: '#a1a1aa', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      splitLine: { lineStyle: { color: '#18181b' } },
      axisLabel: { color: '#a1a1aa', fontSize: 10 },
    },
    series: [{
      type: 'line',
      data: data.trend,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { color: sentimentColor, width: 2 },
      itemStyle: { color: sentimentColor },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: `${sentimentColor}33` },
            { offset: 1, color: `${sentimentColor}00` },
          ],
        },
      },
    }],
  }

  return (
    <div>
      {/* Gauge */}
      <div style={{ textAlign: 'center', height }}>
        <ReactECharts option={gaugeOption} style={{ height: height - 40 }} opts={{ renderer: 'canvas' }} />
      </div>

      {/* Trend */}
      <div style={{ marginTop: 8 }}>
        <ReactECharts option={trendOption} style={{ height: 120 }} opts={{ renderer: 'canvas' }} />
      </div>

      {/* Topics */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
        {data.topics.map((topic) => (
          <Tag key={topic} style={{ fontSize: 10, borderRadius: 4 }}>{topic}</Tag>
        ))}
      </div>

      {/* Summary */}
      <Text style={{ fontSize: 11, color: 'var(--color-text-tertiary)', lineHeight: 1.5, display: 'block', marginTop: 6 }}>
        {data.summary}
      </Text>
    </div>
  )
}
