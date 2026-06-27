import { useEffect, useState } from 'react'
import { Table, Button, Typography, Space, Input, DatePicker, Modal, Collapse, Tag } from 'antd'
import { MagnifyingGlass } from '@phosphor-icons/react'
import client from '@/api/client'
import dayjs from 'dayjs'

const { Title, Text } = Typography
const { RangePicker } = DatePicker

interface AuditLog {
  id: string
  timestamp: string
  username: string
  source: string
  symbol: string
  direction: string
  decision: string
  finalAction: string
  llmPrompt?: string
  llmResponse?: string
}

type ViewMode = 'mine' | 'all'

export default function AuditLog() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState<ViewMode>('mine')
  const [usernameFilter, setUsernameFilter] = useState('')
  const [symbolFilter, setSymbolFilter] = useState('')
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)
  const [detailModal, setDetailModal] = useState<AuditLog | null>(null)

  useEffect(() => { fetchLogs() }, [viewMode, usernameFilter, symbolFilter, dateRange])

  const fetchLogs = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (viewMode === 'all') params.append('view', 'all')
      if (usernameFilter) params.append('username', usernameFilter)
      if (symbolFilter) params.append('symbol', symbolFilter)
      if (dateRange?.[0]) params.append('start_date', dateRange[0].format('YYYY-MM-DD'))
      if (dateRange?.[1]) params.append('end_date', dateRange[1].format('YYYY-MM-DD'))

      const endpoint = viewMode === 'all'
        ? `/api/audit/logs/all?${params}`
        : `/api/audit/logs?${params}`
      const res = await client.get(endpoint)
      setLogs((res as unknown as AuditLog[]).slice(0, 100))
    } catch (e: any) {
      console.warn('[AuditLog] 获取日志失败:', e?.message)
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 160, render: (t: string) => dayjs(t).format('YYYY-MM-DD HH:mm:ss') },
    { title: '用户', dataIndex: 'username', key: 'username', width: 120 },
    { title: '信号源', dataIndex: 'source', key: 'source', width: 120, render: (s: string) => <code style={{ fontSize: 11 }}>{s}</code> },
    { title: '标的', dataIndex: 'symbol', key: 'symbol', width: 100, render: (s: string) => <code style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>{s}</code> },
    { title: '方向', dataIndex: 'direction', key: 'direction', width: 80, render: (d: string) => (
      <Tag color={d === 'BUY' ? 'green' : d === 'SELL' ? 'red' : 'default'}>{d || '—'}</Tag>
    )},
    { title: 'AI 决策摘要', dataIndex: 'decision', key: 'decision', width: 200, ellipsis: true, render: (s: string) => (
      <Text style={{ fontSize: 11 }}>{s?.substring(0, 50)}{s?.length > 50 ? '...' : ''}</Text>
    )},
    { title: '最终动作', dataIndex: 'finalAction', key: 'finalAction', width: 100, render: (a: string) => (
      <Tag color={a?.toUpperCase() === 'EXECUTED' ? 'green' : a?.toUpperCase() === 'REJECTED' ? 'red' : 'default'}>
        {a || '—'}
      </Tag>
    )},
    { title: '操作', key: 'action', width: 80, render: (_: any, r: any) => (
      <Button size="small" icon={<MagnifyingGlass size={12} />} onClick={() => setDetailModal(r)}>详情</Button>
    )},
  ]

  return (
    <div style={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column', gap: 16, overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Title level={4} style={{ margin: 0, fontWeight: 600, fontSize: 16 }}>审计日志</Title>
          <Text type="secondary" style={{ fontSize: 12 }}>查看系统操作审计记录</Text>
        </div>
        <Space>
          <Button.Group size="small">
            <Button
              type={viewMode === 'mine' ? 'primary' : 'default'}
              onClick={() => setViewMode('mine')}
            >
              我的日志
            </Button>
            <Button
              type={viewMode === 'all' ? 'primary' : 'default'}
              onClick={() => setViewMode('all')}
            >
              全部日志
            </Button>
          </Button.Group>
        </Space>
      </div>

      {/* 筛选器 */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Input
          placeholder="用户名"
          size="small"
          value={usernameFilter}
          onChange={(e) => setUsernameFilter(e.target.value)}
          style={{ width: 140 }}
        />
        <Input
          placeholder="标的"
          size="small"
          value={symbolFilter}
          onChange={(e) => setSymbolFilter(e.target.value)}
          style={{ width: 140 }}
        />
        <RangePicker
          size="small"
          value={dateRange}
          onChange={(v) => setDateRange(v as [dayjs.Dayjs, dayjs.Dayjs] | null)}
          format="YYYY-MM-DD"
        />
        <Button size="small" onClick={fetchLogs}>查询</Button>
      </div>

      {/* 日志表格 */}
      <Table
        dataSource={logs}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20, showTotal: (total) => `共 ${total} 条记录` }}
        size="small"
        locale={{ emptyText: '暂无审计日志' }}
      />

      {/* 详情 Modal */}
      <Modal
        title="审计日志详情"
        open={!!detailModal}
        onCancel={() => setDetailModal(null)}
        footer={null}
        width={700}
      >
        {detailModal && (
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '8px 16px', fontSize: 12 }}>
              <Text type="secondary">时间：</Text><Text>{dayjs(detailModal.timestamp).format('YYYY-MM-DD HH:mm:ss')}</Text>
              <Text type="secondary">用户：</Text><Text>{detailModal.username}</Text>
              <Text type="secondary">信号源：</Text><Text>{detailModal.source}</Text>
              <Text type="secondary">标的：</Text><Text>{detailModal.symbol}</Text>
              <Text type="secondary">方向：</Text><Text>{detailModal.direction}</Text>
              <Text type="secondary">AI 决策：</Text><Text>{detailModal.decision}</Text>
              <Text type="secondary">最终动作：</Text><Text>{detailModal.finalAction}</Text>
            </div>
            {detailModal.llmPrompt && (
              <Collapse size="small" items={[{
                key: 'prompt',
                label: <Text strong style={{ fontSize: 12 }}>LLM Prompt</Text>,
                children: <pre style={{ fontSize: 11, background: '#18181b', padding: 12, borderRadius: 6, overflow: 'auto', maxHeight: 300 }}>{detailModal.llmPrompt}</pre>,
              }]} />
            )}
            {detailModal.llmResponse && (
              <Collapse size="small" items={[{
                key: 'response',
                label: <Text strong style={{ fontSize: 12 }}>LLM Response</Text>,
                children: <pre style={{ fontSize: 11, background: '#18181b', padding: 12, borderRadius: 6, overflow: 'auto', maxHeight: 300 }}>{detailModal.llmResponse}</pre>,
              }]} />
            )}
          </Space>
        )}
      </Modal>
    </div>
  )
}
