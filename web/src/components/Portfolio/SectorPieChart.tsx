import { Card } from 'antd'
import ReactECharts from 'echarts-for-react'

interface SectorPieChartProps {
  data: Array<{ sector: string; value: number; weight: number }>
  height?: number
}

export default function SectorPieChart({ data, height = 200 }: SectorPieChartProps) {
  const chartData = data.map((d) => ({ name: d.sector, value: d.value }))

  return (
    <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>行业分布</span>} styles={{ body: { padding: '12px' } }}>
      <ReactECharts
        option={{
          tooltip: { trigger: 'item' },
          series: [{
            type: 'pie', radius: ['40%', '70%'], center: ['50%', '55%'],
            avoidLabelOverlap: false,
            label: { show: true, fontSize: 11, color: 'var(--color-chart-axis)' },
            data: chartData,
            itemStyle: { borderRadius: 4 },
            color: ['#3b82f6', '#10b981', '#f59e0b', '#2563eb'],
          }],
        }}
        style={{ height }}
      />
    </Card>
  )
}
