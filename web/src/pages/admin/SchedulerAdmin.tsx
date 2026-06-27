import { useEffect, useState } from 'react'
import { Card, Table, Button, Typography, Space, Tag, Modal, Form, Input, Select, message } from 'antd'
import { Play, Stop, Plus, Clock } from '@phosphor-icons/react'
import client from '@/api/client'
import dayjs from 'dayjs'

const { Title, Text } = Typography

interface SchedulerStatus {
  running: boolean
  taskCount: number
  lastRun?: string
  nextRun?: string
}

export default function SchedulerAdmin() {
  const [generalStatus, setGeneralStatus] = useState<SchedulerStatus | null>(null)
  const [pipelineStatus, setPipelineStatus] = useState<SchedulerStatus | null>(null)
  const [addModal, setAddModal] = useState(false)
  const [addForm] = Form.useForm()

  useEffect(() => { fetchStatus() }, [])

  const fetchStatus = async () => {
    try {
      const [generalRes, pipelineRes] = await Promise.all([
        client.get('/api/scheduler/status'),
        client.get('/api/pipeline/scheduler/status'),
      ])
      setGeneralStatus(generalRes as unknown as SchedulerStatus)
      setPipelineStatus(pipelineRes as unknown as SchedulerStatus)
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
      await fetchStatus()
      message.success(`调度器已${action === 'start' ? '启动' : '停止'}`)
    } catch (e: any) {
      message.error(e.message || '操作失败')
    }
  }

  const handleAddTask = async () => {
    try {
      const values = addForm.getFieldsValue()
      await client.post('/api/scheduler/tasks', values)
      setAddModal(false)
      addForm.resetFields()
      message.success('任务创建成功')
    } catch (e: any) {
      message.error(e.message || '创建失败')
    }
  }

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
            <Button size="small" icon={<Plus size={14} />} onClick={() => setAddModal(true)}>新增任务</Button>
          </Space>
        )}
        <Table
          pagination={false}
          size="small"
          locale={{ emptyText: '暂无任务' }}
        />
      </Card>

      {/* AI 管线调度器面板 */}
      <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Clock size={14} weight="fill" style={{ color: 'var(--color-warning)' }} /> AI 管线调度器
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
          </Space>
        )}
        <Table
          pagination={false}
          size="small"
          locale={{ emptyText: '暂无任务' }}
        />
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
