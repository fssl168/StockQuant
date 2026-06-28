import { useState, useEffect } from 'react'
import { Form, Input, Select, InputNumber, Radio, Divider, Button, Space, message, Typography, Card, DatePicker } from 'antd'
import { Plus, Trash, BookOpen, CheckCircle } from '@phosphor-icons/react'
import dayjs from 'dayjs'
import { useConditionalOrderStore } from '@/stores/conditionalOrderStore'

const { Text } = Typography

const FIELD_OPTIONS = [
  { value: 'price', label: '价格' },
  { value: 'volume', label: '成交量' },
  { value: 'indicator', label: '指标' },
  { value: 'time', label: '时间' },
]

const OPERATOR_OPTIONS = [
  { value: 'gt', label: '> 大于' },
  { value: 'lt', label: '< 小于' },
  { value: 'gte', label: '>= 大于等于' },
  { value: 'lte', label: '<= 小于等于' },
  { value: 'cross_above', label: '↑ 向上穿越' },
  { value: 'cross_below', label: '↓ 向下穿越' },
]

const TEMPLATE_OPTIONS = [
  { value: 'breakout_buy', label: '突破买入模板' },
  { value: 'pullback_sell', label: '回落卖出模板' },
]

interface ConditionalOrderCondition {
  id: string
  field: 'price' | 'volume' | 'indicator' | 'time'
  operator: 'gt' | 'lt' | 'gte' | 'lte' | 'cross_above' | 'cross_below'
  value: number | string
  label?: string
}

interface ConditionalOrderFormProps {
  initialData?: any
  onSubmitSuccess: () => void
}

// 内置模板：突破买入 - 价格突破 N 日高点时买入
const BREAKOUT_BUY_TEMPLATE: Omit<ConditionalOrderCondition, 'id'>[] = [
  { field: 'price', operator: 'cross_above', value: 20, label: '20日最高价' },
]

// 内置模板：回落卖出 - 价格从高点回落 N% 时卖出
const PULLBACK_SELL_TEMPLATE: Omit<ConditionalOrderCondition, 'id'>[] = [
  { field: 'price', operator: 'cross_below', value: 3, label: '日内高点回落 3%' },
]

export default function ConditionalOrderForm({ initialData, onSubmitSuccess }: ConditionalOrderFormProps) {
  const [form] = Form.useForm()
  const { createOrder, updateOrder } = useConditionalOrderStore()
  const [conditions, setConditions] = useState<ConditionalOrderCondition[]>([])
  const [logic, setLogic] = useState<'AND' | 'OR'>('AND')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (initialData) {
      form.setFieldsValue({
        name: initialData.name,
        type: initialData.type,
        symbol: initialData.symbol,
        side: initialData.action?.side ?? 'BUY',
        quantity: initialData.action?.quantity,
        orderType: initialData.action?.orderType ?? 'MARKET',
        limitOffset: initialData.action?.limitOffset,
        validUntil: initialData.validUntil ? dayjs(initialData.validUntil) : undefined,
        templateId: initialData.templateId,
      })
      setConditions(initialData.conditions ?? [])
      setLogic(initialData.logic ?? 'AND')
    } else {
      form.setFieldsValue({
        type: 'breakout_buy',
        side: 'BUY',
        orderType: 'MARKET',
      })
      setConditions([])
      setLogic('AND')
    }
  }, [initialData, form])

  // 加载模板时自动填充条件
  const handleTemplateChange = (templateId: string) => {
    form.setFieldsValue({ templateId })
    if (templateId === 'breakout_buy') {
      setConditions(BREAKOUT_BUY_TEMPLATE.map((t) => ({ ...t, id: crypto.randomUUID() })))
    } else if (templateId === 'pullback_sell') {
      setConditions(PULLBACK_SELL_TEMPLATE.map((t) => ({ ...t, id: crypto.randomUUID() })))
    }
  }

  const addCondition = () => {
    setConditions([
      ...conditions,
      { id: crypto.randomUUID(), field: 'price', operator: 'gt', value: 0 },
    ])
  }

  const removeCondition = (id: string) => {
    setConditions(conditions.filter((c) => c.id !== id))
  }

  const updateCondition = (id: string, field: keyof ConditionalOrderCondition, value: unknown) => {
    setConditions(conditions.map((c) => (c.id === id ? { ...c, [field]: value } : c)))
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()

      if (conditions.length === 0) {
        message.warning('请至少添加一个触发条件')
        return
      }

      const payload = {
        name: values.name,
        type: values.type,
        symbol: values.symbol,
        conditions,
        logic,
        action: {
          side: values.side,
          quantity: values.quantity,
          orderType: values.orderType,
          limitOffset: values.orderType === 'LIMIT' ? values.limitOffset : undefined,
        },
        validUntil: values.validUntil ? values.validUntil.toISOString() : undefined,
        templateId: values.templateId,
      }

      if (initialData) {
        await updateOrder(initialData.id, payload)
        message.success('条件单已更新')
      } else {
        await createOrder(payload)
        message.success('条件单已创建')
      }

      onSubmitSuccess()
    } catch {
      // validation error, antd handles display
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Form form={form} layout="vertical" onFinish={handleSubmit}>
      {/* 模板选择 */}
      <Card size="small" style={{ marginBottom: 16, background: 'var(--color-bg-elevated)' }}>
        <Form.Item name="templateId" label="模板选择" style={{ marginBottom: 8 }}>
          <Select
            placeholder="选择预设模板（可选）"
            options={TEMPLATE_OPTIONS}
            onChange={handleTemplateChange}
          />
        </Form.Item>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button
            size="small"
            icon={<BookOpen size={14} />}
            onClick={() => handleTemplateChange('breakout_buy')}
          >
            突破买入模板
          </Button>
          <Button
            size="small"
            icon={<BookOpen size={14} />}
            onClick={() => handleTemplateChange('pullback_sell')}
          >
            回落卖出模板
          </Button>
        </div>
      </Card>

      {/* 基本信息 */}
      <Form.Item name="name" label="条件单名称" style={{ marginBottom: 8 }}
        rules={[{ required: true, message: '请输入条件单名称' }]}>
        <Input placeholder="如: 贵州突破买入" />
      </Form.Item>

      <Form.Item name="type" label="条件单类型" style={{ marginBottom: 8 }}
        rules={[{ required: true, message: '请选择条件单类型' }]}>
        <Select
          options={[
            { value: 'breakout_buy', label: '突破买入' },
            { value: 'pullback_sell', label: '回落卖出' },
          ]}
        />
      </Form.Item>

      <Form.Item name="symbol" label="标的代码" style={{ marginBottom: 8 }}
        rules={[{ required: true, message: '请输入标的代码' }]}>
        <Input placeholder="如: 600519" />
      </Form.Item>

      {/* 条件列表 */}
      <Divider style={{ margin: '12px 0' }}>
        <Text style={{ fontSize: 13, fontWeight: 600 }}>触发条件</Text>
      </Divider>

      <div style={{ marginBottom: 8 }}>
        <Text style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>条件间逻辑：</Text>
        <Radio.Group
          value={logic}
          onChange={(e) => setLogic(e.target.value)}
          optionType="button"
          buttonStyle="solid"
          size="small"
          style={{ marginLeft: 8 }}
        >
          <Radio.Button value="AND">AND (同时满足)</Radio.Button>
          <Radio.Button value="OR">OR (任一满足)</Radio.Button>
        </Radio.Group>
      </div>

      {conditions.map((cond) => (
        <Card
          key={cond.id}
          size="small"
          style={{ marginBottom: 8, background: 'var(--color-bg-elevated)' }}
          extra={
            conditions.length > 1 ? (
              <Button size="small" danger type="text" icon={<Trash size={14} />} onClick={() => removeCondition(cond.id)} />
            ) : null
          }
        >
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <Form.Item label="条件类型" style={{ marginBottom: 0, flex: 1, minWidth: 120 }}>
              <Select
                value={cond.field}
                onChange={(v) => updateCondition(cond.id, 'field', v)}
                options={FIELD_OPTIONS}
              />
            </Form.Item>
            <Form.Item label="运算符" style={{ marginBottom: 0, flex: 1, minWidth: 140 }}>
              <Select
                value={cond.operator}
                onChange={(v) => updateCondition(cond.id, 'operator', v)}
                options={OPERATOR_OPTIONS}
              />
            </Form.Item>
            <Form.Item label="阈值" style={{ marginBottom: 0, flex: 1, minWidth: 120 }}>
              <InputNumber
                style={{ width: '100%' }}
                value={cond.value as number}
                onChange={(v) => updateCondition(cond.id, 'value', v ?? 0)}
                placeholder="阈值"
              />
            </Form.Item>
            <Form.Item label="备注" style={{ marginBottom: 0, flex: 2, minWidth: 160 }}>
              <Input
                value={cond.label}
                onChange={(e) => updateCondition(cond.id, 'label', e.target.value)}
                placeholder="如: 20日最高价"
              />
            </Form.Item>
          </div>
        </Card>
      ))}

      <Button
        type="dashed"
        icon={<Plus size={14} />}
        onClick={addCondition}
        style={{ width: '100%', marginBottom: 16, borderColor: 'var(--color-border)' }}
      >
        添加条件
      </Button>

      {/* 执行动作 */}
      <Divider style={{ margin: '12px 0' }}>
        <Text style={{ fontSize: 13, fontWeight: 600 }}>执行动作</Text>
      </Divider>

      <div style={{ display: 'flex', gap: 12, marginBottom: 8 }}>
        <Form.Item name="side" label="方向" style={{ marginBottom: 0, flex: 1 }}
          rules={[{ required: true, message: '请选择方向' }]}>
          <Select options={[{ value: 'BUY', label: '买入' }, { value: 'SELL', label: '卖出' }]} />
        </Form.Item>
        <Form.Item name="quantity" label="数量" style={{ marginBottom: 0, flex: 1 }}
          rules={[{ required: true, message: '请输入数量' }]}>
          <InputNumber style={{ width: '100%' }} min={100} step={100} placeholder="股数" />
        </Form.Item>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 8 }}>
        <Form.Item name="orderType" label="订单类型" style={{ marginBottom: 0, flex: 1 }}
          rules={[{ required: true, message: '请选择订单类型' }]}>
          <Select
            options={[
              { value: 'MARKET', label: '市价单' },
              { value: 'LIMIT', label: '限价单' },
            ]}
            onChange={(v) => {
              if (v === 'MARKET') {
                form.setFieldsValue({ limitOffset: undefined })
              }
            }}
          />
        </Form.Item>
        <Form.Item name="limitOffset" label="限价偏移" style={{ marginBottom: 0, flex: 1 }}
          extra="相对于触发价格的偏移比例 (%)">
          <InputNumber style={{ width: '100%' }} min={0} precision={2} placeholder="如: 0.1" addonAfter="%" />
        </Form.Item>
      </div>

      {/* 有效期 */}
      <Divider style={{ margin: '12px 0' }}>
        <Text style={{ fontSize: 13, fontWeight: 600 }}>有效期</Text>
      </Divider>

      <Form.Item name="validUntil" label="有效期至">
        <DatePicker
          showTime
          style={{ width: '100%' }}
          format="YYYY-MM-DD HH:mm"
          renderExtraFooter={() => (
            <Space>
              <Button size="small" onClick={() => form.setFieldsValue({ validUntil: dayjs().add(1, 'day') })}>明天</Button>
              <Button size="small" onClick={() => form.setFieldsValue({ validUntil: dayjs().add(7, 'day') })}>一周</Button>
              <Button size="small" onClick={() => form.setFieldsValue({ validUntil: dayjs().add(30, 'day') })}>一月</Button>
              <Button size="small" type="link" onClick={() => form.setFieldsValue({ validUntil: undefined })}>永久有效</Button>
            </Space>
          )}
        />
      </Form.Item>

      <Form.Item style={{ marginBottom: 0 }}>
        <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
          <Button onClick={onSubmitSuccess}>取消</Button>
          <Button type="primary" htmlType="submit" loading={submitting} icon={<CheckCircle size={16} />}>
            {initialData ? '保存' : '创建'}
          </Button>
        </Space>
      </Form.Item>
    </Form>
  )
}
