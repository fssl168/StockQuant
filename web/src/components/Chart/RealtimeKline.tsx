import { useEffect, useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'

interface KlineItem {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface RealtimeKlineProps {
  symbol: string
  data: KlineItem[]
  height?: number
  indicators?: string[]
  /** 可选：外部实时价格（如 WebSocket 行情推送）。传入时优先使用，跳过内部模拟 */
  livePrice?: number
}

function computeMA(closes: number[], period: number): (number | null)[] {
  return closes.map((_, i) => {
    if (i < period - 1) return null
    let sum = 0
    for (let j = i - period + 1; j <= i; j++) sum += closes[j]
    return Number((sum / period).toFixed(2))
  })
}

const MA_COLORS: Record<string, string> = {
  MA5: '#e6a23c',
  MA10: '#409eff',
  MA20: '#f56c6c',
}

// 模拟 Tick：每 2 秒更新一次，在最新收盘价 ±0.5% 范围内随机波动
const TICK_INTERVAL_MS = 2000
const TICK_JITTER_RATIO = 0.005

export default function RealtimeKline({
  symbol,
  data,
  height = 400,
  indicators = ['MA5', 'MA10', 'MA20'],
  livePrice,
}: RealtimeKlineProps) {
  const [simPrice, setSimPrice] = useState<number | null>(null)

  // 基准收盘价：取日线最后一根的 close
  const baseClose = useMemo(() => {
    if (!data || data.length === 0) return null
    return data[data.length - 1].close
  }, [data])

  // 模拟 Tick 价格抖动：每 2 秒在基准收盘价 ±0.5% 范围内随机波动
  useEffect(() => {
    if (baseClose == null) return
    setSimPrice(baseClose)
    const timer = setInterval(() => {
      setSimPrice(() => {
        const range = baseClose * TICK_JITTER_RATIO
        const jitter = (Math.random() * 2 - 1) * range
        return Number((baseClose + jitter).toFixed(2))
      })
    }, TICK_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [baseClose])

  // 实时价格：外部 livePrice 优先（兼容 WebSocket 推送），否则使用内部模拟
  const tickPrice = livePrice ?? simPrice

  // 基于原始日线 + tickPrice 计算用于渲染的数据（仅更新最后一根 K 线）
  const displayData = useMemo<KlineItem[]>(() => {
    if (!data || data.length === 0) return []
    if (tickPrice == null) return data
    const last = data[data.length - 1]
    const updated: KlineItem = {
      ...last,
      close: tickPrice,
      high: Math.max(last.high, tickPrice),
      low: Math.min(last.low, tickPrice),
    }
    return [...data.slice(0, -1), updated]
  }, [data, tickPrice])

  // MA 基于展示数据（含实时价格），随 tick 动态更新
  const maData = useMemo(() => {
    if (displayData.length === 0) return {}
    const closes = displayData.map((d) => d.close)
    const result: Record<string, (number | null)[]> = {}
    for (const ind of indicators) {
      const period = parseInt(ind.replace('MA', ''), 10)
      if (!isNaN(period)) {
        result[ind] = computeMA(closes, period)
      }
    }
    return result
  }, [displayData, indicators])

  if (!data || data.length === 0) return null

  const dates = displayData.map((d) => d.date)
  const ohlc = displayData.map((d) => [d.open, d.close, d.low, d.high])
  const upVolumes = displayData.map((d) => (d.close >= d.open ? d.volume : 0))
  const downVolumes = displayData.map((d) => (d.close < d.open ? d.volume : 0))

  const maSeries = indicators
    .filter((ind) => maData[ind])
    .map((ind) => ({
      name: ind,
      type: 'line' as const,
      data: maData[ind],
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1, color: MA_COLORS[ind] || '#a1a1aa' },
      xAxisIndex: 0,
      yAxisIndex: 0,
    }))

  const option = {
    backgroundColor: 'transparent',
    animation: true,
    animationDuration: 600,
    animationDurationUpdate: 600,
    animationEasingUpdate: 'cubicOut',
    legend: {
      show: true,
      top: 0,
      right: 16,
      textStyle: { color: '#a1a1aa', fontSize: 11 },
      itemWidth: 16,
      itemHeight: 2,
      data: indicators
        .filter((ind) => maData[ind])
        .map((ind) => ({ name: ind })),
    },
    grid: [
      { left: 64, right: 16, top: 28, height: '55%' },
      { left: 64, right: 16, top: '75%', height: '20%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: '#27272a' } },
        axisLabel: { color: '#a1a1aa', fontSize: 10 },
        axisTick: { show: false },
        gridIndex: 0,
      },
      {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: '#27272a' } },
        axisLabel: { show: false },
        axisTick: { show: false },
        gridIndex: 1,
      },
    ],
    yAxis: [
      {
        type: 'value',
        scale: true,
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#18181b' } },
        axisLabel: { color: '#a1a1aa', fontSize: 10 },
        gridIndex: 0,
      },
      {
        type: 'value',
        scale: false,
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#18181b' } },
        axisLabel: { color: '#a1a1aa', fontSize: 10 },
        gridIndex: 1,
      },
    ],
    dataZoom: [
      {
        type: 'slider',
        xAxisIndex: [0, 1],
        bottom: 4,
        height: 18,
        borderColor: '#27272a',
        fillerColor: 'rgba(59,130,246,0.15)',
        handleStyle: { color: '#3b82f6' },
        textStyle: { color: '#a1a1aa' },
        dataBackground: {
          lineStyle: { color: '#27272a' },
          areaStyle: { color: '#18181b' },
        },
        selectedDataBackground: {
          lineStyle: { color: '#3b82f6' },
          areaStyle: { color: 'rgba(59,130,246,0.15)' },
        },
      },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#18181b',
      borderColor: '#27272a',
      textStyle: { color: '#fafafa', fontSize: 12 },
      formatter: (params: unknown[]) => {
        const items = params as {
          seriesName: string
          value: number | number[]
          axisValue: string
          axisIndex: number
        }[]
        if (!items || items.length === 0) return ''
        const date = items[0].axisValue
        let html = `<div style="margin-bottom:4px;font-weight:600">${symbol} ${date}</div>`
        for (const p of items) {
          if (p.seriesName === 'K线') {
            const v = p.value as number[]
            const color = v[1] >= v[0] ? '#ef5350' : '#26a69a'
            html += `<div style="color:${color}">开 ${v[0]} 收 ${v[1]} 低 ${v[2]} 高 ${v[3]}</div>`
          } else if (p.seriesName === '成交量-涨' || p.seriesName === '成交量-跌') {
            if (p.value !== 0 && p.value != null) {
              const color = p.seriesName === '成交量-涨' ? '#ef5350' : '#26a69a'
              html += `<div style="color:${color}">量 ${p.value}</div>`
            }
          } else {
            const color = MA_COLORS[p.seriesName] || '#a1a1aa'
            html += `<div><span style="display:inline-block;margin-right:4px;border-radius:50%;width:6px;height:6px;background:${color}"></span>${p.seriesName}: ${p.value}</div>`
          }
        }
        return html
      },
    },
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: '#ef5350',
          color0: '#26a69a',
          borderColor: '#ef5350',
          borderColor0: '#26a69a',
        },
        // 实时更新动画：tick 到来时平滑过渡
        animationDurationUpdate: 500,
        animationEasingUpdate: 'linear',
      },
      ...maSeries,
      {
        name: '成交量-涨',
        type: 'bar',
        data: upVolumes,
        xAxisIndex: 1,
        yAxisIndex: 1,
        stack: 'volume',
        itemStyle: { color: 'rgba(239,83,80,0.5)' },
        barMaxWidth: 8,
      },
      {
        name: '成交量-跌',
        type: 'bar',
        data: downVolumes,
        xAxisIndex: 1,
        yAxisIndex: 1,
        stack: 'volume',
        itemStyle: { color: 'rgba(38,166,154,0.5)' },
        barMaxWidth: 8,
      },
    ],
  }

  return (
    <ReactECharts
      option={option}
      notMerge={false}
      style={{ height, width: '100%' }}
      opts={{ renderer: 'canvas' }}
    />
  )
}
