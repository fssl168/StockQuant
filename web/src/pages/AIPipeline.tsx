import { useEffect, useState } from 'react'
import { Card, Typography, Button, Space, Input, Table, Tag, Row, Col, message } from 'antd'
import { Funnel, Play, ArrowClockwise } from '@phosphor-icons/react'

const { Text } = Typography

/** 带 JWT 认证的 fetch 封装 */
function authFetch(url: string, options?: RequestInit): Promise<Response> {
  const token = localStorage.getItem('auth_token')
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(url, { ...options, headers: { ...headers, ...(options?.headers as Record<string, string> || {}) } })
}

interface PipelineTask {
  task_id: string
  status: string
  created_at: string
  completed_at?: string
  symbols?: string[]
  sources?: string[]
  articles_count?: number
  result?: Record<string, unknown>
  error?: string
}

export default function AIPipelinePage() {
  const [symbolsInput, setSymbolsInput] = useState('sh600519,sz000858')
  const [running, setRunning] = useState(false)
  const [tasks, setTasks] = useState<PipelineTask[]>([])
  const [selectedTask, setSelectedTask] = useState<PipelineTask | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchTasks = async () => {
    setLoading(true)
    try {
      const data = await authFetch('/api/pipeline/status').then(r => r.json()).catch(() => [])
      setTasks(Array.isArray(data) ? data : [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTasks()
    const interval = setInterval(fetchTasks, 3000)
    return () => clearInterval(interval)
  }, [])

  const runFull = async () => {
    const symbols = symbolsInput.split(',').map(s => s.trim()).filter(Boolean)
    if (!symbols.length) { message.warning('请输入股票代码'); return }
    setRunning(true)
    try {
      const resp = await authFetch('/api/pipeline/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbols }),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        message.error(err.detail || `运行失败 (${resp.status})`)
        return
      }
      const data = await resp.json()
      message.success(`管线任务已启动: ${data.task_id}`)
      fetchTasks()
    } catch (e) {
      message.error('运行失败')
    } finally {
      setRunning(false)
    }
  }

  const statusColor = (status: string) => ({
    queued: 'blue', running: 'cyan', completed: 'green', failed: 'red',
  }[status] || 'default')

  const taskColumns = [
    { title: '任务ID', dataIndex: 'task_id', key: 'task_id', width: 140 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: string) => <Tag color={statusColor(v)}>{v}</Tag>,
    },
    {
      title: '标的',
      dataIndex: 'symbols',
      key: 'symbols',
      render: (v: string[]) => v?.join(', ') || '-',
    },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 160, render: (v: string) => new Date(v).toLocaleString('zh-CN') },
    { title: '完成时间', dataIndex: 'completed_at', key: 'completed_at', width: 160, render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, r: PipelineTask) => (
        <Button size="small" type="text" onClick={() => setSelectedTask(r)}>查看</Button>
      ),
    },
  ]

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Funnel size={20} weight="fill" />
          <Text strong style={{ fontSize: 16 }}>AI 信息管线监控</Text>
        </div>
        <Button icon={<Play size={16} />} onClick={runFull} loading={running}>运行完整管线</Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card size="small" title="管线控制">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text type="secondary">股票代码：</Text>
                <Input value={symbolsInput} onChange={e => setSymbolsInput(e.target.value)} placeholder="sh600519,sz000858" />
              </div>
              <Space>
                <Button onClick={() => { message.info('采集功能已集成') }} size="small">采集</Button>
                <Button onClick={() => { message.info('降噪功能已集成') }} size="small">降噪</Button>
                <Button onClick={() => { message.info('总结功能已集成') }} size="small">总结</Button>
                <Button onClick={() => { message.info('升华功能已集成') }} size="small">升华</Button>
              </Space>
            </Space>
          </Card>
        </Col>
        <Col span={16}>
          <Card size="small" title="运行状态" extra={<Button icon={<ArrowClockwise size={14} />} onClick={fetchTasks} loading={loading}>刷新</Button>}>
            <Table
              dataSource={tasks}
              columns={taskColumns}
              rowKey={(r) => r.task_id}
              size="small"
              pagination={{ pageSize: 10 }}
              scroll={{ x: 800 }}
            />
          </Card>
        </Col>
      </Row>

      {selectedTask && (
        <Card size="small" title={`任务详情: ${selectedTask.task_id}`} style={{ marginTop: 8 }}>
          <pre style={{ maxHeight: 400, overflow: 'auto', fontSize: 12 }}>
            {JSON.stringify(selectedTask, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  )
}
