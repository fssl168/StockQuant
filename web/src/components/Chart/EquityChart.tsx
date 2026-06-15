import ReactECharts from 'echarts-for-react'

interface EquityChartProps {
  data: number[]
  height?: number
  title?: string
}

export default function EquityChart({ data, height = 280 }: EquityChartProps) {
  if (!data || data.length === 0) return null

  const maxVal = Math.max(...data)
  const minVal = Math.min(...data)
  const diff = maxVal - minVal

  return (
    <ReactECharts
      option={{
        backgroundColor: 'transparent',
        grid: { left: 64, right: 16, top: 12, bottom: 24 },
        xAxis: {
          type: 'category',
          data: data.map((_, i) => i + 1),
          axisLine: { lineStyle: { color: '#27272a' } },
          axisLabel: { color: '#71717a', fontSize: 10 },
          axisTick: { show: false },
        },
        yAxis: {
          type: 'value',
          scale: true,
          axisLine: { show: false },
          splitLine: { lineStyle: { color: '#18181b' } },
          axisLabel: {
            color: '#71717a',
            fontSize: 10,
            formatter: (v: number) => {
              if (diff > 1_000_000) return (v / 1_000_000).toFixed(1) + 'M'
              if (diff > 1_000) return (v / 1_000).toFixed(0) + 'k'
              return v.toFixed(0)
            },
          },
        },
        series: [{
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
        }],
        tooltip: {
          trigger: 'axis',
          backgroundColor: '#18181b',
          borderColor: '#27272a',
          textStyle: { color: '#fafafa', fontSize: 12 },
          formatter: (params: unknown[]) => {
            const p = params[0] as { value: number; data: number }
            return `${p.value?.toLocaleString()}`
          },
        },
      }}
      style={{ height, width: '100%' }}
      opts={{ renderer: 'canvas' }}
    />
  )
}
