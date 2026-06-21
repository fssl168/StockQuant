# -*- coding: utf-8 -*-
"""DepthChart 组件 - 买卖挂单量分布"""

import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { OrderBookData } from './OrderBook'

interface DepthChartProps {
  data: OrderBookData
  height?: number
  title?: string
}

export default function DepthChart({ data, height = 280, title = '市场深度' }: DepthChartProps) {
  const { bids, asks } = data

  // 准备图表数据
  const chartOption = useMemo((): EChartsOption => {
    // 合并买卖盘数据
    const allPrices = [
      ...bids.map(b => b.price),
      ...asks.map(a => a.price),
    ].sort((a, b) => a - b)

    const bidData: [number, number][] = []
    const askData: [number, number][] = []
    let cumulativeBid = 0
    let cumulativeAsk = 0

    // 卖盘从低到高累计
    const sortedAsks = [...asks].sort((a, b) => a.price - b.price)
    for (const ask of sortedAsks) {
      cumulativeAsk += ask.volume
      askData.push([ask.price, cumulativeAsk])
    }

    // 买盘从高到低累计
    const sortedBids = [...bids].sort((a, b) => b.price - a.price)
    for (const bid of sortedBids) {
      cumulativeBid += bid.volume
      bidData.push([bid.price, cumulativeBid])
    }

    return {
      title: {
        text: title,
        left: 'center',
        textStyle: {
          fontSize: 13,
          fontWeight: 500,
        },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
        },
        formatter: (params: any) => {
          if (!params || !params.length) return ''
          const price = params[0]?.value[0]?.toFixed(2) || '-'
          const bidVol = params.find((p: any) => p.seriesName === '买盘')?.value[1] || 0
          const askVol = params.find((p: any) => p.seriesName === '卖盘')?.value[1] || 0
          return `价格: ${price}<br/>买盘累计: ${bidVol.toLocaleString()}<br/>卖盘累计: ${askVol.toLocaleString()}`
        },
      },
      legend: {
        data: ['买盘', '卖盘'],
        bottom: 5,
        itemWidth: 12,
        itemHeight: 12,
      },
      grid: {
        left: 50,
        right: 30,
        top: 40,
        bottom: 40,
      },
      xAxis: {
        type: 'value',
        name: '价格',
        nameLocation: 'middle',
        nameGap: 25,
        axisLabel: {
          formatter: (value: number) => value.toFixed(0),
        },
        splitLine: {
          show: true,
          lineStyle: {
            type: 'dashed',
            opacity: 0.3,
          },
        },
      },
      yAxis: {
        type: 'value',
        name: '累计量',
        nameLocation: 'middle',
        nameGap: 35,
        axisLabel: {
          formatter: (value: number) => {
            if (value >= 10000) return (value / 10000).toFixed(0) + '万'
            return value.toString()
          },
        },
        splitLine: {
          show: true,
          lineStyle: {
            type: 'dashed',
            opacity: 0.3,
          },
        },
      },
      series: [
        {
          name: '买盘',
          type: 'line',
          data: bidData,
          smooth: true,
          symbol: 'none',
          lineStyle: {
            color: '#e74c3c',
            width: 2,
          },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(231, 76, 60, 0.4)' },
                { offset: 1, color: 'rgba(231, 76, 60, 0.05)' },
              ],
            },
          },
        },
        {
          name: '卖盘',
          type: 'line',
          data: askData,
          smooth: true,
          symbol: 'none',
          lineStyle: {
            color: '#27ae60',
            width: 2,
          },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(39, 174, 96, 0.4)' },
                { offset: 1, color: 'rgba(39, 174, 96, 0.05)' },
              ],
            },
          },
        },
      ],
    }
  }, [bids, asks, title])

  return <ReactECharts option={chartOption} style={{ height }} />
}

