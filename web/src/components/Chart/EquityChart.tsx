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

  return (
    <ReactECharts
      option={{
        backgroundColor: 'transparent',
        grid: { left: 64, right: 16, top: 12, bottom: 24 },
        xAxis: {
          type: 'category',
          data: data.map((_, i) => i + 1),
          axisLine: { lineStyle: { color: '#333' } },
          axisLabel: { color: '#555', fontSize: 10 },
          axisTick: { show: false },
        },
        yAxis: {
          type: 'value',
          scale: true,
          axisLine: { show: false },
          splitLine: { lineStyle: { color: '#1a1a1a' } },
          axisLabel: {
            color: '#555',
            fontSize: 10,
            formatter: (v: number) => {
              const diff = maxVal - minVal
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
          lineStyle: { color: '#0066FF', width: 1.5 },
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(0,102,255,0.15)' },
                { offset: 1, color: 'rgba(0,102,255,0)' },
              ],
            },
          },
        }],
        tooltip: {
          trigger: 'axis',
          backgroundColor: '#141414',
          borderColor: '#222',
          textStyle: { color: '#f0f0f0', fontSize: 12 },
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
