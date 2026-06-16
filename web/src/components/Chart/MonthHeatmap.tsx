import ReactECharts from 'echarts-for-react'

interface MonthHeatmapProps {
  data: Record<string, number>
  height?: number
}

export default function MonthHeatmap({ data, height = 260 }: MonthHeatmapProps) {
  if (Object.keys(data).length === 0) return null

  // 解析年份和月份，提取唯一年份列表
  const yearSet = new Set<string>()
  Object.keys(data).forEach((key) => {
    const year = key.slice(0, 4)
    yearSet.add(year)
  })
  const years = Array.from(yearSet).sort()

  // 转换为 heatmap 数据格式 [monthIndex, yearIndex, value*100]
  const heatmapData = Object.entries(data).map(([key, value]) => {
    const year = key.slice(0, 4)
    const month = parseInt(key.slice(5, 7), 10)
    const yearIndex = years.indexOf(year)
    return [month - 1, yearIndex, +(value * 100).toFixed(2)]
  })

  return (
    <ReactECharts
      option={{
        backgroundColor: 'transparent',
        grid: { left: 60, right: 16, top: 8, bottom: 40 },
        xAxis: {
          type: 'category',
          data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
          axisLine: { lineStyle: { color: '#27272a' } },
          axisLabel: { color: '#a1a1aa', fontSize: 10 },
          splitArea: { show: true, areaStyle: { color: ['rgba(39,39,42,0.3)', 'rgba(39,39,42,0.1)'] } },
        },
        yAxis: {
          type: 'category',
          data: years,
          axisLine: { lineStyle: { color: '#27272a' } },
          axisLabel: { color: '#a1a1aa', fontSize: 10 },
        },
        visualMap: {
          min: -15,
          max: 15,
          calculable: true,
          orient: 'horizontal',
          left: 'center',
          bottom: 0,
          inRange: {
            color: ['#ef4444', '#fca5a5', '#f5f5f5', '#86efac', '#10b981'],
          },
          textStyle: { color: '#a1a1aa', fontSize: 10 },
          formatter: (v: number) => `${v.toFixed(0)}%`,
        },
        series: [{
          type: 'heatmap',
          data: heatmapData,
          label: {
            show: true,
            fontSize: 10,
            formatter: (p: any) => `${p.value[2].toFixed(1)}%`,
          },
          emphasis: {
            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' },
          },
        }],
        tooltip: {
          trigger: 'item',
          backgroundColor: '#18181b',
          borderColor: '#27272a',
          textStyle: { color: '#fafafa', fontSize: 12 },
          formatter: (p: any) => `${years[p.value[1]]}年${p.value[0] + 1}月\n${p.value[2].toFixed(2)}%`,
        },
      }}
      style={{ height, width: '100%' }}
      opts={{ renderer: 'canvas' }}
    />
  )
}
