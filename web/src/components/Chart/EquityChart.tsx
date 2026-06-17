import ReactECharts from 'echarts-for-react'

interface EquityChartProps {
  data: number[]
  height?: number
  title?: string
  benchmarkData?: number[]
  dates?: string[]
  benchmarkLabel?: string
}

export default function EquityChart({ data, height = 280, benchmarkData, dates, benchmarkLabel }: EquityChartProps) {
  if (!data || data.length === 0) return null

  const maxVal = Math.max(...data, ...(benchmarkData ?? []))
  const minVal = Math.min(...data, ...(benchmarkData ?? []))
  const diff = maxVal - minVal

  const xAxisData = dates && dates.length === data.length ? dates : data.map((_, i) => i + 1)

  const series: unknown[] = [
    {
      name: '策略',
      type: 'line',
      data,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#3b82f6', width: 2 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(59,130,246,0.2)' },
            { offset: 1, color: 'rgba(59,130,246,0)' },
          ],
        },
      },
    },
  ]

  if (benchmarkData && benchmarkData.length > 0) {
    series.push({
      name: benchmarkLabel || '基准',
      type: 'line',
      data: benchmarkData,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#f97316', width: 1.5, type: 'dashed' },
    })
  }

  return (
    <ReactECharts
      option={{
        backgroundColor: 'transparent',
        legend: benchmarkData && benchmarkData.length > 0 ? {
          show: true,
          top: 0,
          right: 16,
          textStyle: { color: '#a1a1aa', fontSize: 11 },
          itemWidth: 16,
          itemHeight: 2,
        } : undefined,
        grid: { left: 64, right: 16, top: benchmarkData && benchmarkData.length > 0 ? 28 : 12, bottom: 24 },
        xAxis: {
          type: 'category',
          data: xAxisData,
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
            formatter: (v: number) => {
              if (diff > 1_000_000) return (v / 1_000_000).toFixed(1) + 'M'
              if (diff > 1_000) return (v / 1_000).toFixed(0) + 'k'
              return v.toFixed(0)
            },
          },
        },
        series,
        tooltip: {
          trigger: 'axis',
          backgroundColor: '#18181b',
          borderColor: '#27272a',
          textStyle: { color: '#fafafa', fontSize: 12 },
          formatter: (params: unknown[]) => {
            const items = (params as { seriesName: string; value: number }[]).map(
              (p) => `<span style="display:inline-block;margin-right:4px;border-radius:50%;width:6px;height:6px;background:${p.seriesName === '策略' ? '#3b82f6' : '#f97316'}"></span>${p.seriesName}: ${p.value?.toLocaleString()}`
            )
            return items.join('<br/>')
          },
        },
      }}
      style={{ height, width: '100%' }}
      opts={{ renderer: 'canvas' }}
    />
  )
}
