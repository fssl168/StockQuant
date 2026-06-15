import ReactECharts from 'echarts-for-react'

interface DrawdownChartProps {
  data: number[]
  height?: number
}

export default function DrawdownChart({ data, height = 200 }: DrawdownChartProps) {
  if (!data || data.length === 0) return null

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
            formatter: (v: number) => (v * 100).toFixed(0) + '%',
          },
        },
        series: [{
          type: 'line',
          data: data.map((v) => v * 100),
          smooth: true,
          symbol: 'none',
          lineStyle: { color: '#ef4444', width: 1.5 },
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(239,68,68,0.12)' },
                { offset: 1, color: 'rgba(239,68,68,0)' },
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
            const p = params[0] as { value: number }
            return (p.value ?? 0).toFixed(1) + '%'
          },
        },
      }}
      style={{ height, width: '100%' }}
      opts={{ renderer: 'canvas' }}
    />
  )
}
