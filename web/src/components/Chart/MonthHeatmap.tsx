import ReactECharts from 'echarts-for-react'

interface MonthHeatmapProps {
  data: Record<string, number>
  height?: number
}

export default function MonthHeatmap({ data, height = 260 }: MonthHeatmapProps) {
  const months = Object.keys(data).sort()
  const values = months.map((m) => data[m])

  if (months.length === 0) return null

  return (
    <ReactECharts
      option={{
        backgroundColor: 'transparent',
        grid: { left: 50, right: 16, top: 8, bottom: 40 },
        xAxis: {
          type: 'category',
          data: months.map((m) => m.slice(5)),
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
            formatter: (v: number) => v.toFixed(0) + '%',
          },
        },
        series: [{
          type: 'bar',
          data: values.map((v) => ({
            value: v * 100,
            itemStyle: {
              color: v >= 0 ? '#10b981' : '#ef4444',
              borderRadius: [2, 2, 0, 0],
            },
          })),
          barMaxWidth: 30,
        }],
        tooltip: {
          trigger: 'axis',
          backgroundColor: '#18181b',
          borderColor: '#27272a',
          textStyle: { color: '#fafafa', fontSize: 12 },
          formatter: (params: unknown[]) => {
            const p = params[0] as { name: string; value: number }
            return `${p.name}\n${(p.value ?? 0).toFixed(2)}%`
          },
        },
      }}
      style={{ height, width: '100%' }}
      opts={{ renderer: 'canvas' }}
    />
  )
}
