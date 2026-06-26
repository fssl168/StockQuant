import { useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'

interface ComparisonChartProps {
  strategies: Array<{
    name: string
    metrics: {
      totalReturn?: number
      sharpeRatio?: number
      maxDrawdown?: number
      winRate?: number
      profitLossRatio?: number
    }
  }>
  height?: number
  type?: 'radar' | 'bar'
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

const RADAR_INDICATORS = [
  { key: 'totalReturn' as const, name: '收益率', max: 100 },
  { key: 'sharpeRatio' as const, name: '夏普比率', max: 100 },
  { key: 'maxDrawdown' as const, name: '最大回撤', max: 100 },
  { key: 'winRate' as const, name: '胜率', max: 100 },
  { key: 'profitLossRatio' as const, name: '盈亏比', max: 100 },
]

function normalizeVal(v: number | undefined, key: string): number {
  if (v === undefined || v === null) return 0
  if (key === 'maxDrawdown') {
    // 回撤为负值，取绝对值
    return Math.min(Math.abs(v) * 100, 100)
  }
  return Math.min(v, 100)
}

function buildRadarOption(
  strategies: ComparisonChartProps['strategies'],
  _height: number,
): echarts.EChartsOption {
  const series = strategies.map((s, i) => ({
    name: s.name,
    type: 'radar' as const,
    symbol: 'circle',
    symbolSize: 6,
    lineStyle: { width: 2, color: COLORS[i % COLORS.length] },
    areaStyle: {
      color: COLORS[i % COLORS.length] + '18',
    },
    itemStyle: { color: COLORS[i % COLORS.length] },
    label: {
      show: true,
      fontSize: 10,
      color: '#a1a1aa',
      formatter: () => s.name,
    },
    data: [
      {
        value: RADAR_INDICATORS.map((ind) =>
          normalizeVal(s.metrics[ind.key], ind.key),
        ),
        name: s.name,
      },
    ],
  }))

  return {
    backgroundColor: 'transparent',
    legend: {
      show: true,
      top: 0,
      right: 16,
      textStyle: { color: '#a1a1aa', fontSize: 11 },
      itemWidth: 16,
      itemHeight: 2,
    },
    grid: { left: 16, right: 16, top: 24, bottom: 16 },
    radar: {
      indicator: RADAR_INDICATORS.map((ind) => ({
        name: ind.name,
        max: ind.max,
      })),
      shape: 'polygon',
      radius: '65%',
      center: ['50%', '55%'],
      axisName: {
        color: '#a1a1aa',
        fontSize: 11,
      },
      splitLine: { lineStyle: { color: '#27272a' } },
      splitArea: { areaStyle: { color: ['#18181b', '#0c0c0e'] } },
      axisLine: { lineStyle: { color: '#27272a' } },
    },
    series,
    tooltip: {
      trigger: 'item',
      backgroundColor: '#18181b',
      borderColor: '#27272a',
      textStyle: { color: '#fafafa', fontSize: 12 },
    },
  }
}

function buildBarOption(
  strategies: ComparisonChartProps['strategies'],
  _height: number,
): echarts.EChartsOption {
  const metricKeys = [
    { key: 'totalReturn', name: '收益率', unit: '%' },
    { key: 'sharpeRatio', name: '夏普比率', unit: '' },
    { key: 'maxDrawdown', name: '最大回撤', unit: '%' },
    { key: 'winRate', name: '胜率', unit: '%' },
    { key: 'profitLossRatio', name: '盈亏比', unit: '' },
  ] as const

  const series = metricKeys.map((mk, idx) => ({
    name: mk.name,
    type: 'bar' as const,
    barGap: '10%',
    itemStyle: {
      color: {
        type: 'linear' as const,
        x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: COLORS[idx % COLORS.length] },
          { offset: 1, color: COLORS[idx % COLORS.length] + '60' },
        ],
      },
      borderRadius: [3, 3, 0, 0],
    },
    emphasis: {
      itemStyle: {
        color: {
          type: 'linear' as const,
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: COLORS[idx % COLORS.length] },
            { offset: 1, color: COLORS[idx % COLORS.length] + 'aa' },
          ],
        },
      },
    },
    data: strategies.map((s) => {
      const val = s.metrics[mk.key]
      if (val === undefined || val === null) return 0
      if (mk.key === 'maxDrawdown') return -(Math.abs(val) * 100)
      return Math.min(val * (mk.key === 'profitLossRatio' ? 10 : 1), 100)
    }),
  }))

  return {
    backgroundColor: 'transparent',
    legend: {
      show: true,
      top: 0,
      right: 16,
      textStyle: { color: '#a1a1aa', fontSize: 11 },
      itemWidth: 16,
      itemHeight: 2,
    },
    grid: { left: 56, right: 16, top: 28, bottom: 24 },
    xAxis: {
      type: 'category',
      data: strategies.map((s) => s.name),
      axisLine: { lineStyle: { color: '#27272a' } },
      axisLabel: { color: '#a1a1aa', fontSize: 10 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#18181b' } },
      axisLabel: {
        color: '#a1a1aa',
        fontSize: 10,
        formatter: '{value}%',
      },
    },
    series,
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#18181b',
      borderColor: '#27272a',
      textStyle: { color: '#fafafa', fontSize: 12 },
      axisPointer: { type: 'shadow' },
    },
  }
}

export default function ComparisonChart({
  strategies,
  height = 350,
  type: initialType = 'radar',
}: ComparisonChartProps) {
  const [viewType, setViewType] = useState<'radar' | 'bar'>(initialType)

  if (!strategies || strategies.length < 2) {
    return (
      <div
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#71717a',
          fontSize: 13,
        }}
      >
        至少需要 2 个策略数据进行对比
      </div>
    )
  }

  const option = useMemo(
    () => (viewType === 'radar' ? buildRadarOption(strategies, height) : buildBarOption(strategies, height)),
    [strategies, height, viewType],
  )

  return (
    <div>
      {/* 视图切换按钮 */}
      <div
        style={{
          display: 'flex',
          gap: 8,
          marginBottom: 12,
          justifyContent: 'flex-end',
        }}
      >
        {(['radar', 'bar'] as const).map((v) => (
          <button
            key={v}
            onClick={() => setViewType(v)}
            style={{
              padding: '4px 12px',
              fontSize: 12,
              borderRadius: 6,
              border: '1px solid',
              borderColor: viewType === v ? '#3b82f6' : '#27272a',
              backgroundColor: viewType === v ? '#3b82f620' : 'transparent',
              color: viewType === v ? '#3b82f6' : '#a1a1aa',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              fontWeight: viewType === v ? 600 : 400,
            }}
          >
            {v === 'radar' ? '🕸 雷达图' : '📊 柱状图'}
          </button>
        ))}
      </div>

      <ReactECharts option={option} style={{ height, width: '100%' }} opts={{ renderer: 'canvas' }} />
    </div>
  )
}
