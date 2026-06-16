import { useState, useEffect } from 'react'
import { Table, Button, Card, Space, Tag, Typography, Input, DatePicker } from 'antd'
import { Database, Download } from '@phosphor-icons/react'
import ReactECharts from 'echarts-for-react'
import dayjs from 'dayjs'
import { useDataStore } from '@/stores/dataStore'
import { dataApi } from '@/api/data'
import CacheStats from '@/components/Data/CacheStats'

const { Title, Text } = Typography

export default function Data() {
  const { sources, cacheStats, fetchSources, fetchCacheStats } = useDataStore()

  useEffect(() => {
    fetchSources()
    fetchCacheStats()
  }, [])

  // K-line query state
  const [klineSymbol, setKlineSymbol] = useState('sh600519')
  const [klineDates, setKlineDates] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([dayjs().subtract(60, 'day'), dayjs()])
  const [klineLoading, setKlineLoading] = useState(false)
  const [klineResult, setKlineResult] = useState<{ dates: string[]; data: [number, number, number, number, number][] } | null>(null)

  function generateMockKline(symbol: string, days: number) {
    const data: [number, number, number, number, number][] = []
    let basePrice = symbol.includes('600519') ? 1700 : symbol.includes('000858') ? 150 : 50
    const dates: string[] = []
    for (let i = days; i >= 0; i--) {
      const d = dayjs().subtract(i, 'day').format('YYYY-MM-DD')
      dates.push(d)
      const open = basePrice + (Math.random() - 0.48) * basePrice * 0.02
      const close = open + (Math.random() - 0.48) * basePrice * 0.03
      const high = Math.max(open, close) + Math.random() * basePrice * 0.01
      const low = Math.min(open, close) - Math.random() * basePrice * 0.01
      data.push([open, close, low, high, 0] as [number, number, number, number, number]) // ECharts candlestick: [open, close, lowest, high, volume]
      basePrice = close
    }
    return { dates, data }
  }

  const klineData = klineResult ?? generateMockKline(klineSymbol, 60)

  const handleFetchKline = () => {
    setKlineLoading(true)
    const start = klineDates[0].format('YYYY-MM-DD')
    const end = klineDates[1].format('YYYY-MM-DD')
    dataApi.fetchKline(klineSymbol, 'auto', start, end)
      .then((data) => {
        if (data && (data as any).data) {
          setKlineResult((data as any).data)
        } else if (Array.isArray(data) && data.length > 0) {
          // API returned raw kline array
          setKlineResult({ dates: data.map((_: any, i: number) => dayjs().subtract(i, 'day').format('YYYY-MM-DD')), data: data })
        }
      })
      .catch(() => {
        // Fallback to mock
        const result = generateMockKline(klineSymbol, 60)
        setKlineResult(result)
      })
      .finally(() => setKlineLoading(false))
  }

  const dataSourceColumns = [
    { title: '数据源', dataIndex: 'provider', key: 'provider', width: 120, render: (p: string) => <strong>{p}</strong> },
    { title: '状态', key: 'status', width: 80, render: () => <Tag color="green">活跃</Tag> },
    { title: '最后更新', key: 'last', width: 160, render: () => '2026-06-15 15:00' },
    { title: '记录数', key: 'records', width: 100, render: () => '1,234,567' },
    { title: '操作', key: 'action', width: 120, render: () => (
      <Space>
        <Button size="small" icon={<Download size={14} />}>下载</Button>
      </Space>
    )},
  ]

  const logData = [
    { key: '1', time: '2026-06-15 15:00', source: 'BaoStock', symbol: 'sh600519', status: 'success', records: 1200 },
    { key: '2', time: '2026-06-15 14:00', source: 'AkShare', symbol: 'sz000858', status: 'success', records: 800 },
    { key: '3', time: '2026-06-15 13:00', source: 'BaoStock', symbol: 'sh601318', status: 'warning', records: 0, note: '停牌' },
    { key: '4', time: '2026-06-15 12:00', source: 'CSV', symbol: 'sh600036', status: 'error', records: 0, note: '文件不存在' },
  ]

  return (
    <div style={{ maxWidth: 1200 }}>
      <Title level={4} style={{ marginBottom: 4, fontWeight: 600, fontSize: 16 }}>数据管理</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 20, fontSize: 12 }}>
        数据源配置、缓存管理与采集日志
      </Text>

      {/* Cache stats */}
      <div style={{ marginBottom: 16 }}>
        <CacheStats
          sizeMb={cacheStats ? cacheStats.total_size_mb : 0}
          hitRate={cacheStats ? cacheStats.hit_rate : 0}
          symbolCount={cacheStats ? cacheStats.symbol_count : 0}
          lastUpdate={cacheStats ? cacheStats.last_update : '-'}
        />
      </div>

      {/* K-line query */}
      <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Database size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> K 线查询
      </span>} style={{ marginBottom: 16 }}>
        <Space style={{ marginBottom: 12 }} size={8} wrap>
          <Input
            value={klineSymbol}
            onChange={(e) => setKlineSymbol(e.target.value)}
            placeholder="股票代码 (e.g. sh600519)"
            size="small"
            style={{ width: 180 }}
          />
          <DatePicker.RangePicker
            value={klineDates}
            onChange={(v) => { if (v?.[0] && v?.[1]) setKlineDates([v[0], v[1]]) }}
            size="small"
            format="YYYY-MM-DD"
          />
          <Button type="primary" size="small" icon={<Database size={14} />} loading={klineLoading} onClick={handleFetchKline}>
            查询
          </Button>
        </Space>
        <ReactECharts
          option={{
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
            grid: { left: 60, right: 8, top: 8, bottom: 24 },
            xAxis: { type: 'category', data: klineData.dates, axisLine: { lineStyle: { color: '#27272a' } }, axisLabel: { color: '#a1a1aa', fontSize: 10 } },
            yAxis: { scale: true, splitLine: { lineStyle: { color: '#18181b' } }, axisLabel: { color: '#a1a1aa', fontSize: 10, formatter: (v: number) => v.toFixed(0) } },
            series: [{
              type: 'candlestick',
              data: klineData.data,
              itemStyle: {
                color: '#ef4444',        // 阳线红 (A 股惯例)
                color0: '#10b981',       // 阴线绿
                borderColor: '#ef4444',
                borderColor0: '#10b981',
              },
            }],
            dataZoom: [{ type: 'inside', start: 30, end: 100 }],
          }}
          style={{ height: 320 }}
          notMerge={true}
        />
      </Card>

      {/* Data sources */}
      <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>数据源配置</span>} styles={{ body: { padding: '0' } }} style={{ marginBottom: 12 }}>
        <Table
          dataSource={sources.length > 0 ? sources : [
            { provider: 'BaoStock', enabled: true },
            { provider: 'AkShare', enabled: true },
            { provider: 'CSV 本地', enabled: true },
          ]}
          columns={dataSourceColumns}
          rowKey="provider"
          pagination={false}
          size="small"
        />
      </Card>

      {/* Collection logs */}
      <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>采集日志</span>} styles={{ body: { padding: '0' } }}>
        <Table
          dataSource={logData}
          columns={[
            { title: '时间', dataIndex: 'time', key: 'time', width: 160 },
            { title: '数据源', dataIndex: 'source', key: 'source', width: 100, render: (s: string) => <span style={{ fontFamily: 'var(--font-mono)' }}>{s}</span> },
            { title: '标的', dataIndex: 'symbol', key: 'symbol', width: 120, render: (s: string) => <span style={{ fontFamily: 'var(--font-mono)' }}>{s}</span> },
            { title: '状态', dataIndex: 'status', key: 'status', width: 80, render: (s: string) => (
              <Tag color={s === 'success' ? 'green' : s === 'warning' ? 'orange' : 'red'}>
                {s === 'success' ? '成功' : s === 'warning' ? '警告' : '失败'}
              </Tag>
            )},
            { title: '记录数', dataIndex: 'records', key: 'records', width: 80, render: (v: number) => v.toLocaleString() },
            { title: '备注', key: 'note', render: (_: any, r: any) => r.note ? <span style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>{r.note}</span> : null },
          ]}
          rowKey="key"
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  )
}
