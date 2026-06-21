import { useEffect, useState } from 'react'
import { Tabs, Table, Card, Typography, Button, Space, Input, Modal, Form, Select, message } from 'antd'
import { Memory, Plus, Trash, Search, ArrowsOut } from '@phosphor-icons/react'

const { Text } = Typography

interface MemoryEntry {
  id?: string
  symbol?: string
  content: string
  timestamp?: string
  confidence?: number
  metadata?: Record<string, unknown>
}

export default function MemoryPage() {
  const [l1Data, setL1Data] = useState<MemoryEntry[]>([])
  const [l2Data, setL2Data] = useState<MemoryEntry[]>([])
  const [l3Data, setL3Data] = useState<MemoryEntry[]>([])
  const [loading, setLoading] = useState(false)

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [l1, l2, l3] = await Promise.all([
        fetch('/api/memory/l1').then(r => r.json()).catch(() => []),
        fetch('/api/memory/l2').then(r => r.json()).catch(() => []),
        fetch('/api/memory/l3').then(r => r.json()).catch(() => []),
      ])
      setL1Data(Array.isArray(l1) ? l1 : [])
      setL2Data(Array.isArray(l2) ? l2 : [])
      setL3Data(Array.isArray(l3) ? l3 : [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAll() }, [])

  const columns = (type: 'L1' | 'L2' | 'L3') => [
    {
      title: '标的',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 100,
      render: (v: string) => <Text code>{v}</Text>,
    },
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
    },
    ...(type === 'L2' || type === 'L3' ? [{
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 80,
      render: (v: number) => v ? <Text style={{ color: v > 0.7 ? '#10b981' : '#f59e0b' }}>{v.toFixed(2)}</Text> : '-',
    }] : []),
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: MemoryEntry) => (
        <Button size="small" type="text" danger onClick={() => handleDelete(type, record)}>
          删除
        </Button>
      ),
    },
  ]

  const handleDelete = async (type: 'L1' | 'L2' | 'L3', record: MemoryEntry) => {
    try {
      await fetch(`/api/memory/${type.toLowerCase()}`, { method: 'DELETE' })
      message.success('已清空')
      fetchAll()
    } catch {
      message.error('清空失败')
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Memory size={20} weight="fill" />
          <Text strong style={{ fontSize: 16 }}>记忆系统管理</Text>
        </div>
        <Button icon={<ArrowsOut size={16} />} onClick={fetchAll} loading={loading}>刷新</Button>
      </div>

      <Tabs
        defaultActiveKey="l1"
        items={[
          {
            key: 'l1',
            label: 'L1 工作记忆',
            children: (
              <Card size="small">
                <div style={{ marginBottom: 8, fontSize: 12, color: '#999' }}>
                  内存存储，最近 200 条条目
                </div>
                <Table
                  dataSource={l1Data}
                  columns={columns('L1')}
                  rowKey={(_, i) => String(i)}
                  size="small"
                  pagination={{ pageSize: 20 }}
                  loading={loading}
                />
              </Card>
            ),
          },
          {
            key: 'l2',
            label: 'L2 短期记忆',
            children: (
              <Card size="small">
                <Space style={{ marginBottom: 12 }}>
                  <Input.Search placeholder="关键词搜索" allowClear onSearch={(v) => {
                    fetch(`/api/memory/l2?keyword=${v}`).then(r => r.json()).then(setL2Data).catch(() => setL2Data([]))
                  }} style={{ width: 300 }} />
                  <Button onClick={() => {
                    fetch('/api/memory/compress', { method: 'POST' }).then(() => {
                      message.success('压缩完成')
                      fetchAll()
                    })
                  }}>压缩到 L3</Button>
                  <Button danger onClick={() => handleDelete('L2', {}) as any}>清空 L2</Button>
                </Space>
                <Table
                  dataSource={l2Data}
                  columns={columns('L2')}
                  rowKey={(r) => r.id || ''}
                  size="small"
                  pagination={{ pageSize: 20 }}
                  loading={loading}
                />
              </Card>
            ),
          },
          {
            key: 'l3',
            label: 'L3 长期记忆',
            children: (
              <Card size="small">
                <Space style={{ marginBottom: 12 }}>
                  <Input.Search placeholder="关键词搜索" allowClear onSearch={(v) => {
                    fetch(`/api/memory/l3?keyword=${v}`).then(r => r.json()).then(setL3Data).catch(() => setL3Data([]))
                  }} style={{ width: 300 }} />
                  <Button danger onClick={() => handleDelete('L3', {}) as any}>清空 L3</Button>
                </Space>
                <Table
                  dataSource={l3Data}
                  columns={columns('L3')}
                  rowKey={(r) => r.id || ''}
                  size="small"
                  pagination={{ pageSize: 20 }}
                  loading={loading}
                />
              </Card>
            ),
          },
        ]}
      />
    </div>
  )
}
