import { useEffect, useState } from 'react'
import { Table, Button, Modal, Switch, Popconfirm, Space, Typography, Tag, message } from 'antd'
import { Trash, TrafficSignal, MegaphoneSimple } from '@phosphor-icons/react'
import { useAlertStore, type AlertRule } from '@/stores/alertStore'
import AlertRuleForm from './AlertRuleForm'

const { Text } = Typography

const TYPE_LABELS: Record<AlertRule['type'], string> = {
  price: '价格预警',
  depth_change: '盘口厚度变化',
  index_correlation: '指数联动',
  sector_correlation: '板块联动',
}

const NOTIFY_LABELS: Record<string, string> = {
  dingtalk: '钉钉',
  email: '邮件',
  telegram: 'Telegram',
  sound: '声音',
  browser: '浏览器通知',
}

const TYPE_COLORS: Record<AlertRule['type'], string> = {
  price: '#3b82f6',
  depth_change: '#f59e0b',
  index_correlation: '#8b5cf6',
  sector_correlation: '#10b981',
}

export default function AlertConfigPanel() {
  const { rules, loading, fetchRules, toggleRule, deleteRule } = useAlertStore()
  const [createModal, setCreateModal] = useState(false)
  const [editingRule, setEditingRule] = useState<AlertRule | null>(null)

  useEffect(() => { fetchRules() }, [fetchRules])

  const handleDelete = async (id: string) => {
    try {
      await deleteRule(id)
      message.success('预警规则已删除')
    } catch (e: any) {
      message.error(e.message || '删除失败')
    }
  }

  const columns = [
    {
      title: '规则名称',
      dataIndex: 'name',
      key: 'name',
      width: 160,
      render: (name: string) => <strong>{name}</strong>,
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 130,
      render: (type: AlertRule['type']) => (
        <Tag color={TYPE_COLORS[type]}>{TYPE_LABELS[type]}</Tag>
      ),
    },
    {
      title: '标的',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 120,
      render: (symbol: string, record: AlertRule) => symbol || record.indexSymbol || record.sector || '—',
    },
    {
      title: '通知渠道',
      dataIndex: 'notifyVia',
      key: 'notifyVia',
      width: 200,
      render: (channels: AlertRule['notifyVia']) => (
        <Space size={4}>
          {channels.map((ch) => (
            <Tag key={ch} style={{ fontSize: 10 }}>{NOTIFY_LABELS[ch] ?? ch}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 80,
      render: (enabled: boolean, record: AlertRule) => (
        <Switch
          size="small"
          checked={enabled}
          onChange={() => toggleRule(record.id)}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: AlertRule) => (
        <Space size={4}>
          <Button size="small" type="link" onClick={() => setEditingRule(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除此预警规则？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<Trash size={14} />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexShrink: 0 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <TrafficSignal size={18} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />
            <Typography.Title level={4} style={{ margin: 0, fontWeight: 600, fontSize: 16 }}>预警规则</Typography.Title>
          </div>
          <Text type="secondary" style={{ fontSize: 12 }}>配置自动预警和通知策略</Text>
        </div>
        <Space>
          <Button
            icon={<MegaphoneSimple size={16} />}
            onClick={() => { setEditingRule(null); setCreateModal(true) }}
          >
            新建预警
          </Button>
        </Space>
      </div>

      <Table
        dataSource={rules}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 条规则` }}
        style={{ flex: 1, overflow: 'auto' }}
      />

      {/* 新建 / 编辑 Modal */}
      <Modal
        title={editingRule ? '编辑预警规则' : '新建预警规则'}
        open={createModal || !!editingRule}
        onCancel={() => { setCreateModal(false); setEditingRule(null) }}
        footer={null}
        width={560}
        destroyOnHidden
      >
        <AlertRuleForm
          initialData={editingRule}
          onSubmitSuccess={() => {
            setCreateModal(false)
            setEditingRule(null)
          }}
        />
      </Modal>
    </div>
  )
}
