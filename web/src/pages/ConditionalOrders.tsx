import { useState, useEffect } from 'react'
import { Table, Button, Modal, Radio, Space, Typography, Tag, Popconfirm, message } from 'antd'
import { Plus, Trash, Warning, TrendUp, TrendDown } from '@phosphor-icons/react'
import { useConditionalOrderStore, type ConditionalOrder } from '@/stores/conditionalOrderStore'
import ConditionalOrderForm from '@/components/Trading/ConditionalOrderForm'

const { Text } = Typography

// Local condition display type
interface CondTag {
  id: string
  field: 'price' | 'volume' | 'indicator' | 'time'
  operator: 'gt' | 'lt' | 'gte' | 'lte' | 'cross_above' | 'cross_below'
  value: number | string
  label?: string
}

// Status and label maps
const STATUS_LABELS: Record<string, string> = {
  active: '激活',
  triggered: '已触发',
  expired: '已失效',
  cancelled: '已取消',
}

const STATUS_COLORS: Record<string, string> = {
  active: '#10b981',
  triggered: '#f59e0b',
  expired: '#6b7280',
  cancelled: '#ef4444',
}

const TYPE_LABELS: Record<string, string> = {
  breakout_buy: '突破买入',
  pullback_sell: '回落卖出',
}

const FIELD_LABELS: Record<string, string> = {
  price: '价格',
  volume: '成交量',
  indicator: '指标',
  time: '时间',
}

type OrderStatus = 'active' | 'triggered' | 'expired' | 'cancelled'

export default function ConditionalOrders() {
  const { orders, loading, fetchOrders, cancelOrder, deleteOrder } = useConditionalOrderStore()
  const [createModal, setCreateModal] = useState(false)
  const [editingOrder, setEditingOrder] = useState<ConditionalOrder | null>(null)
  const [filterStatus, setFilterStatus] = useState<string>('all')

  useEffect(() => { fetchOrders() }, [fetchOrders])

  const handleCancel = async (id: string) => {
    try {
      await cancelOrder(id)
      message.success('条件单已取消')
    } catch (e: any) {
      message.error(e.message || '取消失败')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteOrder(id)
      message.success('条件单已删除')
    } catch (e: any) {
      message.error(e.message || '删除失败')
    }
  }

  const filteredOrders = filterStatus === 'all'
    ? orders
    : orders.filter((o) => o.status === filterStatus)

  const renderConditionTags = (conditions: CondTag[]) => {
    if (!conditions?.length) return <Text type="secondary" style={{ fontSize: 11 }}>未配置条件</Text>
    return (
      <Space size={4} wrap>
        {conditions.map((c) => (
          <Tag key={c.id} style={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}>
            {FIELD_LABELS[c.field] ?? c.field} {c.operator} {c.value}
          </Tag>
        ))}
      </Space>
    )
  }

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 140,
      render: (name: string) => <strong>{name}</strong>,
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      render: (type: string) => (
        <Tag color={type === 'breakout_buy' ? 'blue' : 'orange'}>
          {type === 'breakout_buy' ? <TrendUp size={12} /> : <TrendDown size={12} />}
          {' '}{TYPE_LABELS[type]}
        </Tag>
      ),
    },
    {
      title: '标的',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 100,
      render: (symbol: string) => <code style={{ fontSize: 12 }}>{symbol}</code>,
    },
    {
      title: '条件',
      dataIndex: 'conditions',
      key: 'conditions',
      width: 280,
      render: (conditions: CondTag[]) => renderConditionTags(conditions),
    },
    {
      title: '逻辑',
      dataIndex: 'logic',
      key: 'logic',
      width: 60,
      render: (logic: string) => (
        <Tag color={logic === 'AND' ? 'purple' : 'cyan'}>{logic}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: OrderStatus) => (
        <Tag color={STATUS_COLORS[status]}>{STATUS_LABELS[status]}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: any, record: ConditionalOrder) => (
        <Space size={4}>
          {record.status === 'active' && (
            <Popconfirm title="确定取消此条件单？" onConfirm={() => handleCancel(record.id)}>
              <Button size="small" type="link" icon={<Warning size={14} />}>取消</Button>
            </Popconfirm>
          )}
          <Popconfirm title="确定删除此条件单？" onConfirm={() => handleDelete(record.id)}>
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
          <Typography.Title level={4} style={{ margin: 0, fontWeight: 600, fontSize: 16 }}>条件单管理</Typography.Title>
          <Text type="secondary" style={{ fontSize: 12 }}>设置触发条件后自动下单的自动化策略</Text>
        </div>
        <Button
          icon={<Plus size={16} />}
          onClick={() => { setEditingOrder(null); setCreateModal(true) }}
        >
          新建条件单
        </Button>
      </div>

      {/* 状态筛选 */}
      <div style={{ marginBottom: 12, flexShrink: 0 }}>
        <Radio.Group value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} buttonStyle="solid">
          <Radio.Button value="all">全部 ({orders.length})</Radio.Button>
          <Radio.Button value="active">激活 ({orders.filter((o) => o.status === 'active').length})</Radio.Button>
          <Radio.Button value="triggered">已触发 ({orders.filter((o) => o.status === 'triggered').length})</Radio.Button>
          <Radio.Button value="expired">已失效 ({orders.filter((o) => o.status === 'expired').length})</Radio.Button>
          <Radio.Button value="cancelled">已取消 ({orders.filter((o) => o.status === 'cancelled').length})</Radio.Button>
        </Radio.Group>
      </div>

      <Table
        dataSource={filteredOrders}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 条条件单` }}
        style={{ flex: 1, overflow: 'auto' }}
      />

      {/* 新建 / 编辑 Modal */}
      <Modal
        title={editingOrder ? '编辑条件单' : '新建条件单'}
        open={createModal || !!editingOrder}
        onCancel={() => { setCreateModal(false); setEditingOrder(null) }}
        footer={null}
        width={720}
        destroyOnClose
      >
        <ConditionalOrderForm
          initialData={editingOrder}
          onSubmitSuccess={() => {
            setCreateModal(false)
            setEditingOrder(null)
          }}
        />
      </Modal>
    </div>
  )
}
