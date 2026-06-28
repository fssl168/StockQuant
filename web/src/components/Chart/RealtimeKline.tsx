import { useEffect, useMemo, useRef, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import type EChartsReact from 'echarts-for-react'
import { useChartPreload } from '@/hooks/useChartPreload'

interface KlineItem {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface KeyLevel {
  price: number
  type: 'support' | 'resistance'
}

interface RealtimeKlineProps {
  symbol: string
  data: KlineItem[]
  height?: number
  indicators?: string[]
  /** 可选：外部实时价格（如 WebSocket 行情推送）。传入时优先使用，跳过内部模拟 */
  livePrice?: number
  /** 分段加载回调：用户滚动到边界时触发，返回追加的 K 线数据 */
  onLoadMore?: (direction: 'left' | 'right') => Promise<KlineItem[]>
  /** 关键价位列表（支撑位/阻力位），用于触发闪烁 */
  keyLevels?: KeyLevel[]
  /** 是否启用分段加载，默认 true */
  enableSegmentedLoad?: boolean
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

/** 默认初始可见 K 线数量 */
const DEFAULT_VISIBLE_BARS = 60
/** dataZoom 起始位置 ≤ 此百分比时触发左边界加载 */
const LOAD_MORE_THRESHOLD = 0.05
/**
 * 闪烁动画持续时间 — 必须与 key-level-flash.scss 实际时长对齐：
 * `animation: key-level-flash 0.8s ease-in-out 3` = 0.8s × 3 = 2.4s = 2400ms
 * 之前设为 1200ms 会导致动画在第 2 个循环就被移除（P1-6 修复）
 */
const FLASH_DURATION_MS = 2400

export default function RealtimeKline({
  symbol,
  data,
  height = 400,
  indicators = ['MA5', 'MA10', 'MA20'],
  livePrice,
  onLoadMore,
  keyLevels,
  enableSegmentedLoad = true,
}: RealtimeKlineProps) {
  const chartRef = useRef<EChartsReact>(null)
  // 集成 useChartPreload：进入视口时触发 onVisible，离开触发 onHide
  // 用 useChartPreload 的 ref 替代原 containerRef，确保可见性检测与容器绑定一致
  const preloadedRef = useRef(false)
  const { ref: containerRef } = useChartPreload({
    enabled: true,
    onVisible: () => {
      // 图表可见时恢复动画并 resize 确保正确渲染
      const chart = chartRef.current?.getEchartsInstance()
      if (chart) {
        chart.setOption({ animation: true })
        chart.resize()
      }
      // 首次可见时预加载右侧（最新）数据，避免阻塞首屏渲染
      if (preloadedRef.current) return
      preloadedRef.current = true
      if (onLoadMore && enableSegmentedLoad) {
        onLoadMore('right').catch(() => { /* 预加载失败静默处理 */ })
      }
    },
    onHide: () => {
      // 图表不可见时暂停动画，节省性能
      const chart = chartRef.current?.getEchartsInstance()
      if (chart) chart.setOption({ animation: false })
    },
  })

  const [simPrice, setSimPrice] = useState<number | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)

  // 可见区间：默认显示最后 N 根
  const [visibleRange, setVisibleRange] = useState<{ start: number; end: number }>(() => {
    if (!enableSegmentedLoad || !data || data.length === 0) return { start: 0, end: Number.MAX_SAFE_INTEGER }
    const end = data.length
    const start = Math.max(0, end - DEFAULT_VISIBLE_BARS)
    return { start, end }
  })

  // 已闪烁过的价位集合（避免重复闪烁）
  const flashedLevelsRef = useRef<Set<string>>(new Set())
  // P1-6: 当前闪烁动画的定时器引用 — 重新触发前必须清除，否则旧定时器会提前移除新动画的 class
  const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 基准收盘价：取日线最后一根的 close
  const baseClose = useMemo(() => {
    if (!data || data.length === 0) return null
    return data[data.length - 1].close
  }, [data])

  // 模拟 Tick 价格抖动
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

  // 实时价格：外部 livePrice 优先
  const tickPrice = livePrice ?? simPrice

  // 应用可见区间 + 实时价格更新最后一根 K 线
  const displayData = useMemo<KlineItem[]>(() => {
    if (!data || data.length === 0) return []
    const start = Math.min(visibleRange.start, data.length)
    const end = Math.min(visibleRange.end, data.length)
    const slice = data.slice(start, end)
    if (slice.length === 0) return slice
    if (tickPrice == null) return slice
    const last = slice[slice.length - 1]
    const updated: KlineItem = {
      ...last,
      close: tickPrice,
      high: Math.max(last.high, tickPrice),
      low: Math.min(last.low, tickPrice),
    }
    return [...slice.slice(0, -1), updated]
  }, [data, tickPrice, visibleRange])

  // 关键价位突破检测 + 闪烁
  useEffect(() => {
    if (!keyLevels || keyLevels.length === 0 || tickPrice == null) return
    const container = containerRef.current
    if (!container) return

    for (const level of keyLevels) {
      const key = `${level.type}@${level.price}`
      if (flashedLevelsRef.current.has(key)) continue

      // 支撑位向上突破（价格从下方升至上方）
      const supportBreak = level.type === 'support' && tickPrice > level.price
      // 阻力位向下突破（价格从上方降至下方）
      const resistanceBreak = level.type === 'resistance' && tickPrice < level.price

      if (supportBreak || resistanceBreak) {
        flashedLevelsRef.current.add(key)
        const flashClass = supportBreak ? 'key-level-flash' : 'key-level-flash-danger'
        // P1-6: 移除可能残留的旧 class，并清除上一个未完成的定时器，避免新旧动画冲突
        container.classList.remove('key-level-flash', 'key-level-flash-danger')
        if (flashTimerRef.current) {
          clearTimeout(flashTimerRef.current)
          flashTimerRef.current = null
        }
        container.classList.add(flashClass)
        flashTimerRef.current = setTimeout(() => {
          container.classList.remove(flashClass)
          flashTimerRef.current = null
        }, FLASH_DURATION_MS)
        // 同一价位只闪一次
        break
      }
    }
  }, [tickPrice, keyLevels])

  // P1-6: 组件卸载时清除定时器，避免内存泄漏
  useEffect(() => {
    return () => {
      if (flashTimerRef.current) {
        clearTimeout(flashTimerRef.current)
        flashTimerRef.current = null
      }
    }
  }, [])

  // MA 基于展示数据
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

  // dataZoom 事件监听：触发分段加载
  const handleDataZoom = async (params: unknown) => {
    if (!onLoadMore || !enableSegmentedLoad) return
    const p = params as { batch?: Array<{ start: number; end: number }>; start?: number; end?: number }
    // ECharts dataZoom 事件可能为 batch 或单次
    const startPct = p.batch?.[0]?.start ?? p.start ?? 0
    const endPct = p.batch?.[0]?.end ?? p.end ?? 100

    // 接近左边界（≤5%）触发加载历史数据
    if (startPct <= LOAD_MORE_THRESHOLD * 100 && !loadingMore) {
      setLoadingMore(true)
      try {
        const more = await onLoadMore('left')
        if (more && more.length > 0) {
          // 追加到原 data 前面，并调整 visibleRange
          // 注意：这里我们假设父组件会更新 data prop，因此仅在 visibleRange 上做平移
          setVisibleRange((prev) => ({
            start: prev.start + more.length,
            end: prev.end + more.length,
          }))
        }
      } catch (e) {
        console.warn('loadMore failed:', e)
      } finally {
        setLoadingMore(false)
      }
    }
    void endPct
  }

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
    <div ref={containerRef} style={{ position: 'relative' }}>
      <ReactECharts
        ref={chartRef}
        option={option}
        notMerge={false}
        style={{ height, width: '100%' }}
        opts={{ renderer: 'canvas' }}
        onEvents={{
          datazoom: handleDataZoom,
        }}
      />
      {loadingMore && (
        <div
          style={{
            position: 'absolute',
            top: 8,
            left: '50%',
            transform: 'translateX(-50%)',
            padding: '4px 12px',
            background: 'rgba(59,130,246,0.15)',
            border: '1px solid rgba(59,130,246,0.4)',
            borderRadius: 4,
            fontSize: 11,
            color: '#3b82f6',
            pointerEvents: 'none',
            zIndex: 10,
          }}
        >
          加载历史数据中…
        </div>
      )}
    </div>
  )
}
