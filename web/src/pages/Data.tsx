import { useEffect } from 'react'
import { Table, Button, Card, Space, Tag, Row, Col } from 'antd'
import { Database, Download } from '@phosphor-icons/react'
import { useDataStore } from '@/stores/dataStore'

export default function Data() {
  const { sources, cacheStats } = useDataStore()

  useEffect(() => {
    void 0
  }, [])

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
      <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 4 }}>数据管理</div>
      <div style={{ color: '#555', display: 'block', marginBottom: 20, fontSize: 12 }}>
        数据源配置、缓存管理与采集日志
      </div>

      {/* Cache stats */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        {[
          { label: '缓存大小', value: cacheStats ? `${cacheStats.total_size_mb.toFixed(1)} MB` : '-', icon: <Database size={16} /> },
          { label: '命中率', value: cacheStats ? `${(cacheStats.hit_rate * 100).toFixed(0)}%` : '-', icon: <Database size={16} /> },
          { label: '标的数', value: cacheStats ? cacheStats.symbol_count : '-', icon: <Database size={16} /> },
          { label: '最后更新', value: cacheStats ? cacheStats.last_update : '-', icon: <Database size={16} /> },
        ].map((s) => (
          <Col xs={24} sm={12} md={6} key={s.label}>
            <Card size="small" styles={{ body: { padding: '10px 14px' } }}>
              <div style={{ fontSize: 10, color: '#666', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</div>
              <div style={{ fontSize: 15, fontWeight: 600, fontFamily: 'var(--font-mono)', marginTop: 2, color: '#f0f0f0' }}>
                {s.value}
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* Data sources */}
      <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>数据源配置</span>} styles={{ body: { padding: '0' } }} style={{ marginBottom: 12 }}>
        <Table
          dataSource={sources.length > 0 ? sources : [
            { provider: 'BaoStock' },
            { provider: 'AkShare' },
            { provider: 'CSV 本地' },
          ]}
          columns={dataSourceColumns}
          rowKey={(r: any) => r.key}
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
            { title: '备注', key: 'note', render: (_: any, r: any) => r.note ? <span style={{ fontSize: 11, color: '#888' }}>{r.note}</span> : null },
          ]}
          rowKey={(r: any) => r.key}
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  )
}
