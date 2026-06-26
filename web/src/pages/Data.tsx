import { useState, useEffect } from 'react'
import { Table, Button, Card, Space, Tag, Typography, Input, DatePicker, Switch, Modal, message } from 'antd'
import { Database, Download, CloudArrowDown } from '@phosphor-icons/react'
import ReactECharts from 'echarts-for-react'
import dayjs from 'dayjs'
import { useDataStore } from '@/stores/dataStore'
import { dataApi } from '@/api/data'
import client from '@/api/client'
import CacheStats from '@/components/Data/CacheStats'

const { Title, Text } = Typography

export default function Data() {
  const { sources, cacheStats, fetchSources, fetchCacheStats } = useDataStore()

  useEffect(() => {
    fetchSources()
    fetchCacheStats()
    // Fetch health status on page load (Task 2.11)
    dataApi.health()
      .then((res: any) => {
        // client 响应拦截器返回 axios response（数据在 .data）；后端返回数组，按 provider 转 map
        const arr = Array.isArray(res) ? res : (res?.data && Array.isArray(res.data)) ? res.data : []
        const map: Record<string, { healthy: boolean }> = {}
        arr.forEach((p: any) => {
          if (p?.provider) map[p.provider] = { healthy: !!p.healthy }
        })
        setHealthData(map)
      })
      .catch(() => setHealthData({}))
  }, [])

  // K-line query state
  const [klineSymbol, setKlineSymbol] = useState('sh600519')
  const [klineDates, setKlineDates] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([dayjs().subtract(60, 'day'), dayjs()])
  const [klineLoading, setKlineLoading] = useState(false)
  const [klineResult, setKlineResult] = useState<{ dates: string[]; data: [number, number, number, number, number][] } | null>(null)
  const [clearingCache, setClearingCache] = useState(false)

  // Health status state (Task 2.11)
  const [healthData, setHealthData] = useState<Record<string, { healthy: boolean }>>({})

  // Collect state (Task 2.10)
  const [klineError, setKlineError] = useState<string | null>(null)
  const [collectingProvider, setCollectingProvider] = useState<string | null>(null)
  const [collectSymbol, setCollectSymbol] = useState('sh600519')
  const [collectModalOpen, setCollectModalOpen] = useState(false)
  const [collectTargetProvider, setCollectTargetProvider] = useState<string>('')
  const [logData, setLogData] = useState<any[]>([])

  const handleClearCache = async () => {
    setClearingCache(true)
    try {
      await dataApi.clearCache()
      fetchCacheStats()
    } catch (e: any) {
      console.warn('[Data] 清除缓存失败:', e?.message)
    } finally {
      setClearingCache(false)
    }
  }

  const handleToggleSource = async (provider: string, enabled: boolean) => {
    try {
      await dataApi.updateSource({ provider, enabled } as any)
      fetchSources()
    } catch (e: any) {
      console.warn('[Data] 切换数据源失败:', e?.message)
    }
  }

  // Collect handler (Task 2.10)
  const handleCollect = async (provider: string) => {
    setCollectingProvider(provider)
    const start = dayjs().subtract(1, 'year').format('YYYY-MM-DD')
    const end = dayjs().format('YYYY-MM-DD')
    try {
      await dataApi.collect({ symbol: collectSymbol, source: provider, start, end })
      message.success(`${provider} 采集成功`)
    } catch {
      message.error(`${provider} 采集失败`)
    } finally {
      setCollectingProvider(null)
      setCollectModalOpen(false)
    }
  }

  // 标准化图表数据：{dates, data} 或 raw OHLCV 对象数组
  const klineData = (() => {
    if (!klineResult) return { dates: [] as string[], data: [] as unknown[] }
    // 必须是对象且包含 data 属性
    const r = klineResult as { dates?: unknown[]; data?: unknown[] }
    if (typeof klineResult === 'object' && !Array.isArray(klineResult) && r.data !== undefined) {
      return { dates: Array.isArray(r.dates) ? r.dates as string[] : [], data: Array.isArray(r.data) ? r.data : [] }
    }
    // raw OHLCV 对象数组 [{date, open, ...}, ...]
    if (Array.isArray(klineResult)) {
      const arr = klineResult as { date: string; open: number; close: number; low: number; high: number; volume: number }[]
      return {
        dates: arr.map((r) => r.date),
        data: arr.map((r) => [r.open, r.close, r.low, r.high, r.volume]),
      }
    }
    return { dates: [] as string[], data: [] as unknown[] }
  })()

  // 预览表格数据（最近10条）
  const previewData = (Array.isArray(klineData.dates) ? klineData.dates : []).slice(-10).map((d: string, i: number) => {
    const row = klineData.data[klineData.dates.length - 10 + i] as number[] | undefined
    return { date: d, open: row?.[0], close: row?.[1], low: row?.[2], high: row?.[3], volume: row?.[4] }
  })

  const handleFetchKline = () => {
    setKlineLoading(true)
    setKlineError(null)
    const start = klineDates[0].format('YYYY-MM-DD')
    const end = klineDates[1].format('YYYY-MM-DD')
    dataApi.fetchKline(klineSymbol, 'alphafeed', start, end)
      .then((data) => {
        const rawData = data?.data ?? data
        if (Array.isArray(rawData) && rawData.length > 0) {
          setKlineResult({ dates: (rawData as any[]).map((_: any, i: number) => dayjs().subtract(i, 'day').format('YYYY-MM-DD')), data: rawData as any })
        } else {
          setKlineError('未查询到数据')
        }
      })
      .catch((err) => {
        setKlineError(err?.message || '查询失败，请检查数据源配置')
      })
      .finally(() => setKlineLoading(false))
  }

  const dataSourceColumns = [
    { title: '数据源', dataIndex: 'provider', key: 'provider', width: 120, render: (p: string) => <strong>{p}</strong> },
    { title: '状态', key: 'health', width: 80, render: (_: any, r: any) => {
      const health = healthData[r.provider]
      if (health === undefined) return <Tag color="gold">未知</Tag>
      return health.healthy ? <Tag color="green">健康</Tag> : <Tag color="red">异常</Tag>
    }},
    { title: '启用', key: 'enabled', width: 80, render: (_: any, r: any) => (
      <Switch
        size="small"
        checked={r.enabled !== false}
        onChange={(checked) => handleToggleSource(r.provider, checked)}
      />
    ) },
    { title: '最后更新', key: 'last', width: 160, render: (_: any, r: any) => r.lastCheck ? new Date(r.lastCheck).toLocaleString('zh-CN') : '—' },
    { title: '记录数', key: 'records', width: 100, render: (_: any, r: any) => r.records != null ? Number(r.records).toLocaleString() : '—' },
    { title: '操作', key: 'action', width: 160, render: (_: any, r: any) => (
      <Space>
        <Button size="small" icon={<Download size={14} />} onClick={() => handleDownload(r.provider)}>下载</Button>
        <Button
          size="small"
          icon={<CloudArrowDown size={14} />}
          loading={collectingProvider === r.provider}
          onClick={() => {
            setCollectTargetProvider(r.provider)
            setCollectModalOpen(true)
          }}
        >
          采集
        </Button>
      </Space>
    )},
  ]

  // Load collection logs from backend
  useEffect(() => {
    client.get('/api/data/collect-logs')
      .then((data: any) => {
        const logs = Array.isArray(data) ? data : (data?.data ?? [])
        if (logs.length > 0) setLogData(logs)
      })
      .catch((e: any) => console.warn('[Data] 获取采集日志失败:', e?.message))
  }, [])

  const handleDownload = async (provider: string) => {
    try {
      message.loading({ content: `${provider} 数据下载中...`, key: 'download', duration: 0 })
      await client.get(`/api/data/download?provider=${provider}`)
      message.success({ content: `${provider} 数据下载完成`, key: 'download' })
      fetchSources()
      fetchCacheStats()
    } catch {
      message.error({ content: `${provider} 数据下载失败`, key: 'download' })
    }
  }

  return (
    <div style={{ maxWidth: 1200 }}>
      <Title level={4} style={{ marginBottom: 4, fontWeight: 600, fontSize: 16 }}>数据管理</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 20, fontSize: 12 }}>
        数据源配置、缓存管理与采集日志
      </Text>

      {/* Cache stats */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <CacheStats
          sizeMb={cacheStats?.sizeMb ?? 0}
          hitRate={cacheStats?.hitRate ?? 0}
          symbolCount={cacheStats?.symbolCount ?? 0}
          lastUpdate={cacheStats?.lastUpdate ?? '-'}
        />
        <Button size="small" danger onClick={handleClearCache} loading={clearingCache}>
          清除缓存
        </Button>
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
        {klineError ? (
          <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-danger)', fontSize: 13 }}>
            {klineError}
          </div>
        ) : (klineData.data?.length ?? 0) > 0 ? (
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
        ) : (
          <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-text-tertiary)', fontSize: 13 }}>
            输入股票代码并点击「查询」查看 K 线数据
          </div>
        )}
      </Card>

      {/* Data preview */}
      <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>数据预览</span>} style={{ marginBottom: 12 }}>
        <Table
          dataSource={previewData}
          columns={[
            { title: '日期', dataIndex: 'date', key: 'date', width: 120 },
            { title: '开盘', dataIndex: 'open', key: 'open', width: 90, render: (v: number) => v?.toFixed(2) },
            { title: '收盘', dataIndex: 'close', key: 'close', width: 90, render: (v: number) => v?.toFixed(2) },
            { title: '最高', dataIndex: 'high', key: 'high', width: 90, render: (v: number) => v?.toFixed(2) },
            { title: '最低', dataIndex: 'low', key: 'low', width: 90, render: (v: number) => v?.toFixed(2) },
            { title: '成交量', dataIndex: 'volume', key: 'volume', width: 100, render: (v: number) => v?.toLocaleString() },
          ]}
          rowKey="date"
          pagination={{ pageSize: 5, size: 'small' }}
          size="small"
        />
      </Card>

      {/* Data sources */}
      <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>数据源配置</span>} styles={{ body: { padding: '0' } }} style={{ marginBottom: 12 }}>
        <Table
          dataSource={sources}
          columns={dataSourceColumns}
          rowKey="provider"
          pagination={false}
          size="small"
          locale={{ emptyText: '暂无数据源配置' }}
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
            { title: '记录数', dataIndex: 'records', key: 'records', width: 80, render: (v: number) => v?.toLocaleString() ?? '—' },
            { title: '备注', key: 'note', render: (_: any, r: any) => r.note ? <span style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>{r.note}</span> : null },
          ]}
          rowKey="key"
          pagination={false}
          size="small"
        />
      </Card>

      {/* Collect Modal (Task 2.10) */}
      <Modal
        title={`采集数据 - ${collectTargetProvider}`}
        open={collectModalOpen}
        onOk={() => handleCollect(collectTargetProvider)}
        onCancel={() => setCollectModalOpen(false)}
        okText="开始采集"
        cancelText="取消"
        confirmLoading={collectingProvider !== null}
      >
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>股票代码</Text>
            <Input
              value={collectSymbol}
              onChange={(e) => setCollectSymbol(e.target.value)}
              placeholder="e.g. sh600519"
              size="small"
              style={{ marginTop: 4 }}
            />
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>数据源</Text>
            <div style={{ marginTop: 4 }}><Tag>{collectTargetProvider}</Tag></div>
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>日期范围</Text>
            <div style={{ marginTop: 4, fontFamily: 'var(--font-mono)', fontSize: 12 }}>
              {dayjs().subtract(1, 'year').format('YYYY-MM-DD')} ~ {dayjs().format('YYYY-MM-DD')}
            </div>
          </div>
        </Space>
      </Modal>
    </div>
  )
}
