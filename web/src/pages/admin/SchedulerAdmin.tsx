import { useEffect, useState } from 'react'
import { Card, Table, Button, Typography, Space, Tag, Modal, Form, Input, Select, Popconfirm, message } from 'antd'
import { Play, Stop, Plus, Clock, Trash, Code } from '@phosphor-icons/react'
import client from '@/api/client'
import dayjs from 'dayjs'

const { Title, Text } = Typography

interface SchedulerStatus {
  running: boolean
  taskCount: number
  lastRun?: string
  nextRun?: string
}

interface SchedulerTask {
  id: string
  name: string
  cron: string
  type: string
  enabled?: boolean
  lastRun?: string
  nextRun?: string
}

export default function SchedulerAdmin() {
  const [generalStatus, setGeneralStatus] = useState<SchedulerStatus | null>(null)
  const [pipelineStatus, setPipelineStatus] = useState<SchedulerStatus | null>(null)
  const [generalTasks, setGeneralTasks] = useState<SchedulerTask[]>([])
  const [pipelineTasks, setPipelineTasks] = useState<SchedulerTask[]>([])
  const [addModal, setAddModal] = useState(false)
  const [addForm] = Form.useForm()
  const [activeScheduler, setActiveScheduler] = useState<'general' | 'pipeline'>('general')

  useEffect(() => { fetchAll() }, [])

  const fetchAll = async () => {
    try {
      const [generalRes, pipelineRes, generalTasksRes, pipelineTasksRes] = await Promise.all([
        client.get('/api/scheduler/status'),
        client.get('/api/pipeline/scheduler/status'),
        client.get('/api/scheduler/tasks'),
        client.get('/api/pipeline/scheduler/tasks'),
      ])
      setGeneralStatus(generalRes as unknown as SchedulerStatus)
      setPipelineStatus(pipelineRes as unknown as SchedulerStatus)
      setGeneralTasks(generalTasksRes as unknown as SchedulerTask[])
      setPipelineTasks(pipelineTasksRes as unknown as SchedulerTask[])
    } catch (e: any) {
      console.warn('[Scheduler] 获取状态失败:', e?.message)
    }
  }

  const handleToggle = async (type: 'general' | 'pipeline') => {
    const status = type === 'general' ? generalStatus : pipelineStatus
    const action = status?.running ? 'stop' : 'start'
    const endpoint = type === 'general'
      ? `/api/scheduler/${action}`
      : `/api/pipeline/scheduler/${action}`
    try {
      await client.post(endpoint)
      await fetchAll()
      message.success(`调度器已${action === 'start' ? '启动' : '停止'}`)
    } catch (e: any) {
      message.error(e.message || '操作失败')
    }
  }

  const handleAddTask = async () => {
    try {
      const values = addForm.getFieldsValue()
      const endpoint = activeScheduler === 'general'
        ? '/api/scheduler/tasks'
        : '/api/pipeline/scheduler/tasks'
      await client.post(endpoint, values)
      setAddModal(false)
      addForm.resetFields()
      await fetchAll()
      message.success('任务创建成功')
    } catch (e: any) {
      message.error(e.message || '创建失败')
    }
  }

  const handleDeleteTask = async (type: 'general' | 'pipeline', id: string) => {
    try {
      const endpoint = type === 'general'
        ? `/api/scheduler/tasks/${id}`
        : `/api/pipeline/scheduler/tasks/${id}`
      await client.delete(endpoint)
      await fetchAll()
      message.success('任务已删除')
    } catch (e: any) {
      message.error(e.message || '删除失败')
    }
  }

  const taskColumns = (type: 'general' | 'pipeline'): any[] => [
    { title: '名称', dataIndex: 'name', key: 'name', width: 150 },
    { title: 'Cron', dataIndex: 'cron', key: 'cron', width: 140, render: (c: string) => <code style={{ fontSize: 11 }}>{c}</code> },
    { title: '类型', dataIndex: 'type', key: 'type', width: 100, render: (t: string) => <Tag color="blue">{t}</Tag> },
    {
      title: '上次运行',
      dataIndex: 'lastRun',
      key: 'lastRun',
      width: 140,
      render: (v?: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '—',
    },
    {
      title: '下次运行',
      dataIndex: 'nextRun',
      key: 'nextRun',
      width: 140,
      render: (v?: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '—',
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, r: SchedulerTask) => (
        <Popconfirm title="确定删除此任务？" onConfirm={() => handleDeleteTask(type, r.id)}>
          <Button size="small" danger icon={<Trash size={12} />}>删除</Button>
        </Popconfirm>
      ),
    },
  ]

  const GeneralTaskTable = () => (
    <Table
      dataSource={generalTasks}
      columns={taskColumns('general')}
      rowKey="id"
      pagination={false}
      size="small"
      locale={{ emptyText: '暂无任务' }}
    />
  )

  const PipelineTaskTable = () => (
    <Table
      dataSource={pipelineTasks}
      columns={taskColumns('pipeline')}
      rowKey="id"
      pagination={false}
      size="small"
      locale={{ emptyText: '暂无任务' }}
    />
  )

  return (
    <div style={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column', gap: 16, overflow: 'auto' }}>
      <div>
        <Title level={4} style={{ margin: 0, fontWeight: 600, fontSize: 16 }}>调度器管理</Title>
        <Text type="secondary" style={{ fontSize: 12 }}>管理通用调度器和 AI 管线调度器</Text>
      </div>

      {/* 通用调度器面板 */}
      <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Clock size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> 通用调度器
      </span>}>
        {generalStatus && (
          <Space style={{ marginBottom: 12 }} size={16}>
            <Tag color={generalStatus.running ? 'green' : 'default'}>
              {generalStatus.running ? '运行中' : '已停止'}
            </Tag>
            <Text type="secondary" style={{ fontSize: 11 }}>任务数: {generalStatus.taskCount}</Text>
            <Text type="secondary" style={{ fontSize: 11 }}>上次: {generalStatus.lastRun ? dayjs(generalStatus.lastRun).format('HH:mm:ss') : '—'}</Text>
            <Button
              size="small"
              icon={generalStatus.running ? <Stop size={14} /> : <Play size={14} />}
              onClick={() => handleToggle('general')}
            >
              {generalStatus.running ? '停止' : '启动'}
            </Button>
            <Button size="small" icon={<Plus size={14} />} onClick={() => { setActiveScheduler('general'); setAddModal(true) }}>新增任务</Button>
          </Space>
        )}
        <GeneralTaskTable />
      </Card>

      {/* AI 管线调度器面板 */}
      <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Code size={14} weight="fill" style={{ color: 'var(--color-warning)' }} /> AI 管线调度器
      </span>}>
        {pipelineStatus && (
          <Space style={{ marginBottom: 12 }} size={16}>
            <Tag color={pipelineStatus.running ? 'green' : 'default'}>
              {pipelineStatus.running ? '运行中' : '已停止'}
            </Tag>
            <Text type="secondary" style={{ fontSize: 11 }}>任务数: {pipelineStatus.taskCount}</Text>
            <Text type="secondary" style={{ fontSize: 11 }}>上次: {pipelineStatus.lastRun ? dayjs(pipelineStatus.lastRun).format('HH:mm:ss') : '—'}</Text>
            <Button
              size="small"
              icon={pipelineStatus.running ? <Stop size={14} /> : <Play size={14} />}
              onClick={() => handleToggle('pipeline')}
            >
              {pipelineStatus.running ? '停止' : '启动'}
            </Button>
            <Button size="small" icon={<Plus size={14} />} onClick={() => { setActiveScheduler('pipeline'); setAddModal(true) }}>新增任务</Button>
          </Space>
        )}
        <PipelineTaskTable />
      </Card>

      {/* 新增任务 Modal */}
      <Modal title="新增调度任务" open={addModal} onCancel={() => setAddModal(false)} footer={null} width={480}>
        <Form form={addForm} layout="vertical">
          <Form.Item name="name" label="任务名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="任务名称" />
          </Form.Item>
          <Form.Item name="cron" label="Cron 表达式" rules={[{ required: true, message: '请输入 Cron 表达式' }]}>
            <Input placeholder="e.g. 0 */6 * * *" />
          </Form.Item>
          <Form.Item name="type" label="任务类型" rules={[{ required: true, message: '请选择类型' }]}>
            <Select placeholder="选择任务类型" options={[
              { value: 'collect', label: '数据采集' },
              { value: 'backtest', label: '回测' },
              { value: 'optimize', label: '参数优化' },
            ]} />
          </Form.Item>
          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => setAddModal(false)}>取消</Button>
              <Button type="primary" onClick={handleAddTask}>创建</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
