import { useState, useEffect } from 'react'
import { Form, Input, Select, Checkbox, InputNumber, Tabs, Space, Button, message, Typography } from 'antd'
import { useAlertStore, type AlertRule } from '@/stores/alertStore'
import type { AlertType } from '@/types/alert'

const { Text } = Typography

const NOTIFY_OPTIONS = [
  { value: 'dingtalk', label: '钉钉' },
  { value: 'email', label: '邮件' },
  { value: 'telegram', label: 'Telegram' },
  { value: 'sound', label: '声音' },
  { value: 'browser', label: '浏览器通知' },
]

interface AlertRuleFormProps {
  initialData?: AlertRule | null
  onSubmitSuccess: () => void
}

const TABS = [
  { key: 'price', label: '价格预警', type: 'price' as const },
  { key: 'depth_change', label: '盘口厚度变化', type: 'depth_change' as const },
  { key: 'index_correlation', label: '指数联动', type: 'index_correlation' as const },
  { key: 'sector_correlation', label: '板块联动', type: 'sector_correlation' as const },
]

export default function AlertRuleForm({ initialData, onSubmitSuccess }: AlertRuleFormProps) {
  const [form] = Form.useForm()
  const { createRule, updateRule } = useAlertStore()
  const [activeTab, setActiveTab] = useState<AlertType>(initialData?.type ?? 'price')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (initialData) {
      form.setFieldsValue({
        name: initialData.name,
        type: initialData.type,
        symbol: initialData.symbol,
        indexSymbol: initialData.indexSymbol,
        sector: initialData.sector,
        notifyVia: initialData.notifyVia,
        ...initialData.conditions,
      })
      setActiveTab(initialData.type)
    }
  }, [initialData, form])

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)

      const payload = {
        name: values.name,
        type: activeTab,
        symbol: values.symbol || undefined,
        indexSymbol: values.indexSymbol || undefined,
        sector: values.sector || undefined,
        enabled: true,
        notifyVia: values.notifyVia,
        conditions: Object.fromEntries(
          Object.entries(values).filter(([k]) => !['name', 'symbol', 'indexSymbol', 'sector', 'notifyVia'].includes(k))
        ),
      }

      if (initialData) {
        await updateRule(initialData.id, payload)
        message.success('预警规则已更新')
      } else {
        await createRule(payload)
        message.success('预警规则已创建')
      }

      onSubmitSuccess()
    } catch {
      // validation error, antd handles display
    } finally {
      setSubmitting(false)
    }
  }

  const renderConditionFields = () => {
    switch (activeTab) {
      case 'price':
        return (
          <>
            <Form.Item name="priceThreshold" label="价格阈值" style={{ marginBottom: 8 }}
              rules={[{ required: true, message: '请输入价格阈值' }]}>
              <InputNumber style={{ width: '100%' }} min={0} precision={2} placeholder="如: 10.00" />
            </Form.Item>
            <Form.Item name="priceDirection" label="触发方向" style={{ marginBottom: 0 }}
              initialValue='above'>
              <Select style={{ width: '100%' }}
                options={[
                  { value: 'above', label: '价格 >= 阈值' },
                  { value: 'below', label: '价格 <= 阈值' },
                  { value: 'cross_above', label: '价格由下向上穿越阈值' },
                  { value: 'cross_below', label: '价格由上向下穿越阈值' },
                ]}
              />
            </Form.Item>
          </>
        )

      case 'depth_change':
        return (
          <>
            <Form.Item name="changeThreshold" label="挂单量变化阈值 (%)" style={{ marginBottom: 8 }}
              rules={[{ required: true, message: '请输入变化阈值' }]}>
              <InputNumber style={{ width: '100%' }} min={0} max={100} precision={1} placeholder="如: 50" addonAfter="%" />
            </Form.Item>
            <Form.Item name="depthDirection" label="变化方向" style={{ marginBottom: 0 }}
              initialValue='any'>
              <Select style={{ width: '100%' }}
                options={[
                  { value: 'any', label: '任意方向' },
                  { value: 'decrease', label: '挂单量减少' },
                  { value: 'increase', label: '挂单量增加' },
                ]}
              />
            </Form.Item>
          </>
        )

      case 'index_correlation':
        return (
          <>
            <Form.Item name="indexSymbol" label="指数标的" style={{ marginBottom: 8 }}
              rules={[{ required: true, message: '请输入指数代码' }]}>
              <Input placeholder="如: 000300 (沪深300)" />
            </Form.Item>
            <Form.Item name="deviationThreshold" label="偏离阈值 (%)" style={{ marginBottom: 8 }}
              rules={[{ required: true, message: '请输入偏离阈值' }]}>
              <InputNumber style={{ width: '100%' }} min={0} precision={1} placeholder="如: 2.0" addonAfter="%" />
            </Form.Item>
            <Form.Item name="correlationDirection" label="触发方向" style={{ marginBottom: 0 }}
              initialValue='diverge'>
              <Select style={{ width: '100%' }}
                options={[
                  { value: 'diverge', label: '与指数偏离超过阈值' },
                  { value: 'follow', label: '与指数同步变动超过阈值' },
                ]}
              />
            </Form.Item>
          </>
        )

      case 'sector_correlation':
        return (
          <>
            <Form.Item name="sector" label="板块名称" style={{ marginBottom: 8 }}
              rules={[{ required: true, message: '请输入板块名称' }]}>
              <Input placeholder="如: 半导体" />
            </Form.Item>
            <Form.Item name="linkThreshold" label="联动阈值 (%)" style={{ marginBottom: 8 }}
              rules={[{ required: true, message: '请输入联动阈值' }]}>
              <InputNumber style={{ width: '100%' }} min={0} max={100} precision={1} placeholder="如: 30" addonAfter="%" />
            </Form.Item>
            <Form.Item name="linkDirection" label="联动方向" style={{ marginBottom: 0 }}
              initialValue='same'>
              <Select style={{ width: '100%' }}
                options={[
                  { value: 'same', label: '同向变动超过阈值' },
                  { value: 'opposite', label: '反向变动超过阈值' },
                ]}
              />
            </Form.Item>
          </>
        )

      default:
        return null
    }
  }

  return (
    <Form form={form} layout="vertical" onFinish={handleSubmit}>
      <Form.Item name="name" label="规则名称" style={{ marginBottom: 12 }}
        rules={[{ required: true, message: '请输入规则名称' }]}>
        <Input placeholder="如: 茅台价格突破 1800" />
      </Form.Item>

      <Tabs
        activeKey={activeTab}
        onChange={(key) => { setActiveTab(key as AlertType); form.resetFields() }}
        items={TABS.map((t) => ({
          key: t.key,
          label: t.label,
          children: (
            <div>
              {t.key === 'price' && (
                <Form.Item name="symbol" label="标的代码" style={{ marginBottom: 12 }}
                  rules={[{ required: true, message: '请输入标的代码' }]}>
                  <Input placeholder="如: 600519" />
                </Form.Item>
              )}
              {renderConditionFields()}
            </div>
          ),
        }))}
      />

      <div style={{ marginTop: 12 }}>
        <Text style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>通知渠道</Text>
      </div>
      <Form.Item name="notifyVia" style={{ marginBottom: 20, marginTop: 4 }}
        rules={[{ required: true, message: '请至少选择一个通知渠道' }]}
        valuePropName="channels">
        <Checkbox.Group options={NOTIFY_OPTIONS} />
      </Form.Item>

      <Form.Item style={{ marginBottom: 0 }}>
        <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
          <Button onClick={onSubmitSuccess}>取消</Button>
          <Button type="primary" htmlType="submit" loading={submitting}>
            {initialData ? '保存' : '创建'}
          </Button>
        </Space>
      </Form.Item>
    </Form>
  )
}
