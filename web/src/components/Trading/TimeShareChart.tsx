# -*- coding: utf-8 -*-
"""TimeShareChart 组件 - 分时走势 + 均价线"""

import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'

export interface TimeShareItem {
  time: string       // 时间 HH:MM:SS
  price: number      // 当前价
  volume: number     // 成交量
  avgPrice?: number  // 均价
}

interface TimeShareChartProps {
  data: TimeShareItem[]
  height?: number
  title?: string
  symbol?: string
}

export default function TimeShareChart({ 
  data, 
  height = 280, 
  title = '分时走势',
  symbol = ''
}: TimeShareChartProps) {
  const chartOption = useMemo((): EChartsOption => {
    if (!data || data.length === 0) {
      return {
        title: { text: title, left: 'center' },
        graphic: {
          type: 'text',
          left: 'center',
          top: 'middle',
          style: {
            text: '暂无数据',
            fill: '#999',
            fontSize: 14,
          },
        },
      }
    }

    const times = data.map(d => d.time)
    const prices = data.map(d => d.price)
    const volumes = data.map(d => d.volume)
    
    // 计算均价线
    let cumVolume = 0
    let cumAmount = 0
    const avgPrices = data.map(d => {
      cumVolume += d.volume
      cumAmount += d.price * d.volume
      return cumVolume > 0 ? cumAmount / cumVolume : d.price
    })

    // 计算涨跌
    const firstPrice = prices[0]
    const lastPrice = prices[prices.length - 1]
    const change = lastPrice - firstPrice
    const changePercent = (change / firstPrice) * 100

    // 价格颜色
    const priceColor = change >= 0 ? '#e74c3c' : '#27ae60'
    const lineColor = change >= 0 ? '#e74c3c' : '#27ae60'

    return {
      title: {
        text: title,
        subtext: symbol ? `${symbol}  ${change >= 0 ? '↑' : '↓'} ${change.toFixed(2)} (${changePercent.toFixed(2)}%)` : undefined,
        left: 'center',
        textStyle: {
          fontSize: 13,
          fontWeight: 500,
        },
        subtextStyle: {
          color: priceColor,
          fontSize: 12,
        },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          lineStyle: {
            type: 'dashed',
          },
        },
        formatter: (params: any) => {
          if (!params || !params.length) return ''
          const time = params[0]?.axisValue
          const priceData = params.find((p: any) => p.seriesName === '价格')
          const avgData = params.find((p: any) => p.seriesName === '均价')
          const volData = params.find((p: any) => p.seriesName === '成交量')
          
          return `<div style="font-size:12px">
            <div>时间: ${time}</div>
            <div style="color:${priceData?.color}">当前价: ${priceData?.value?.[1]?.toFixed(2) || '-'}</div>
            <div style="color:#409eff">均价: ${avgData?.value?.[1]?.toFixed(2) || '-'}</div>
            <div>成交量: ${(volData?.value?.[1] || 0).toLocaleString()}</div>
          </div>`
        },
      },
      legend: {
        data: ['价格', '均价', '成交量'],
        bottom: 5,
        itemWidth: 12,
        itemHeight: 12,
      },
      grid: [
        {
          left: 50,
          right: 30,
          top: 50,
          height: '55%',
        },
        {
          left: 50,
          right: 30,
          top: '72%',
          height: '18%',
        },
      ],
      xAxis: [
        {
          type: 'category',
          data: times,
          gridIndex: 0,
          axisLabel: { show: false },
          axisLine: { lineStyle: { color: '#e8e8e8' } },
          axisTick: { show: false },
        },
        {
          type: 'category',
          data: times,
          gridIndex: 1,
          axisLabel: { 
            formatter: (value: string) => value.substring(0, 5),
            fontSize: 10,
          },
          axisLine: { lineStyle: { color: '#e8e8e8' } },
          axisTick: { show: false },
          splitLine: { show: false },
        },
      ],
      yAxis: [
        {
          type: 'value',
          gridIndex: 0,
          axisLabel: {
            formatter: (value: number) => value.toFixed(2),
            fontSize: 11,
          },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: {
            lineStyle: { type: 'dashed', opacity: 0.3 },
          },
        },
        {
          type: 'value',
          gridIndex: 1,
          axisLabel: {
            formatter: (value: number) => {
              if (value >= 10000) return (value / 10000).toFixed(0) + '万'
              return value.toString()
            },
            fontSize: 10,
          },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: '价格',
          type: 'line',
          data: prices,
          xAxisIndex: 0,
          yAxisIndex: 0,
          smooth: true,
          symbol: 'none',
          lineStyle: { color: lineColor, width: 1.5 },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: change >= 0 ? 'rgba(231, 76, 60, 0.25)' : 'rgba(39, 174, 96, 0.25)' },
                { offset: 1, color: 'rgba(255, 255, 255, 0)' },
              ],
            },
          },
        },
        {
          name: '均价',
          type: 'line',
          data: avgPrices,
          xAxisIndex: 0,
          yAxisIndex: 0,
          smooth: true,
          symbol: 'none',
          lineStyle: { color: '#409eff', width: 1, type: 'dashed' },
        },
        {
          name: '成交量',
          type: 'bar',
          data: volumes,
          xAxisIndex: 1,
          yAxisIndex: 1,
          itemStyle: {
            color: (params: any) => {
              const idx = params.dataIndex
              if (!prices[idx]) return '#999'
              return prices[idx] >= prices[0] ? 'rgba(231, 76, 60, 0.6)' : 'rgba(39, 174, 96, 0.6)'
            },
          },
          barWidth: '60%',
        },
      ],
    }
  }, [data, title, symbol])

  return <ReactECharts option={chartOption} style={{ height }} />
}

// 生成模拟分时数据
export function generateMockTimeShare(basePrice: number = 100, points: number = 240): TimeShareItem[] {
  const data: TimeShareItem[] = []
  let price = basePrice
  let cumVolume = 0
  let cumAmount = 0

  // 模拟从 9:30 到 15:00 的分时数据
  for (let i = 0; i < points; i++) {
    // 随机波动
    const change = (Math.random() - 0.5) * 0.005 * price
    price = Math.max(price + change, price * 0.95) // 限制涨跌幅
    
    // 随机成交量
    const volume = Math.floor(Math.random() * 5000) + 1000
    cumVolume += volume
    cumAmount += price * volume
    
    // 时间格式 HH:MM:SS
    const totalSeconds = 9 * 3600 + 30 * 60 + (i * 225) // 每225秒一个点
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)
    const seconds = totalSeconds % 60
    const time = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`

    data.push({
      time,
      price: Number(price.toFixed(2)),
      volume,
      avgPrice: Number((cumAmount / cumVolume).toFixed(2)),
    })
  }

  return data
}

