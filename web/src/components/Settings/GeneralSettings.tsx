import { useState, useCallback } from 'react'
import { Card, Form, Input, Switch, Select, InputNumber, Slider, Button, Space, message, Typography, Divider } from 'antd'
import { SaveOutlined, DatabaseOutlined, LaptopOutlined, CloudServerOutlined } from '@ant-design/icons'
import type { SettingEntry } from './types'

const { Text } = Typography

interface GeneralSettingsProps {
  values: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
}

const DATABASE_ITEMS: SettingEntry[] = [
  { key: 'database.url', value: '', defaultValue: '', value_type: 'password', label: '数据库URL', description: '连接字符串', secret: true },
  { key: 'database.pool_size', value: 10, defaultValue: 10, value_type: 'number', label: '连接池大小', min: 1, max: 100, step: 1 },
  { key: 'database.max_overflow', value: 20, defaultValue: 20, value_type: 'number', label: '最大溢出', min: 0, max: 100, step: 1 },
  { key: 'database.pool_timeout', value: 30, defaultValue: 30, value_type: 'number', label: '超时时间', min: 1, max: 300, step: 1 },
  { key: 'database.echo', value: false, defaultValue: false, value_type: 'boolean', label: 'SQL 日志' },
]

const SYSTEM_ITEMS: SettingEntry[] = [
  { key: 'trading.mode', value: 'simulator', defaultValue: 'simulator', value_type: 'select', label: '交易模式', options: [{ value: 'backtest', label: '回测模式' }, { value: 'simulator', label: '模拟实盘' }, { value: 'live', label: '实盘' }] },
  { key: 'system.log_level', value: 'INFO', defaultValue: 'INFO', value_type: 'select', label: '日志级别', options: [{ value: 'DEBUG', label: 'DEBUG' }, { value: 'INFO', label: 'INFO' }, { value: 'WARNING', label: 'WARNING' }, { value: 'ERROR', label: 'ERROR' }] },
  { key: 'system.web_port', value: 8000, defaultValue: 8000, value_type: 'number', label: 'Web 端口', min: 1, max: 65535, step: 1 },
  { key: 'system.initial_capital', value: 1000000, defaultValue: 1000000, value_type: 'number', label: '初始资金', min: 10000, max: 1_000_000_000, step: 100000 },
]

const DATA_SOURCE_ITEMS: SettingEntry[] = [
  { key: 'data_provider.source', value: 'alphafeed', defaultValue: 'alphafeed', value_type: 'select', label: '默认数据源', options: [{ value: 'alphafeed', label: 'AlphaFeed (推荐)' }, { value: 'baostock', label: 'BaoStock' }, { value: 'akshare', label: 'AkShare' }, { value: 'csv', label: 'CSV' }] },
  { key: 'data_provider.alphafeed_key', value: '', defaultValue: '', value_type: 'password', label: 'AlphaFeed Key', secret: true, when: { field: 'data_provider.source', values: ['alphafeed'] } },
  { key: 'data_provider.api_key', value: '', defaultValue: '', value_type: 'password', label: 'API Key', secret: true, when: { field: 'data_provider.source', values: ['akshare'] } },
  { key: 'baostock.enabled', value: true, defaultValue: true, value_type: 'boolean', label: '启用 BaoStock', when: { field: 'data_provider.source', values: ['baostock'] } },
]

function isVisible(item: SettingEntry, allValues: Record<string, unknown>): boolean {
  if (!item.when) return true
  return item.when.values.includes(allValues[item.when.field] as string)
}

function renderField(item: SettingEntry, value: unknown, onChange: (v: unknown) => void) {
  switch (item.value_type) {
    case 'boolean':
      return <Switch checked={value as boolean} onChange={onChange} size="small" />
    case 'select':
      return <Select value={String(value)} onChange={onChange} size="small" style={{ minWidth: 160 }} options={item.options} />
    case 'number':
      return <InputNumber value={value as number} onChange={onChange} size="small" min={item.min} max={item.max} step={item.step} style={{ width: '100%' }} />
    case 'float':
      return item.slider ? (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Slider value={(value as number) * (item.scale ?? 1)} min={0} max={(item.max ?? 1) * (item.scale ?? 1)} onChange={(v) => onChange(v / (item.scale ?? 1))} />
          <InputNumber value={value as number} onChange={onChange} size="small" style={{ width: '100%' }} />
        </Space>
      ) : <InputNumber value={value as number} onChange={onChange} size="small" min={item.min} max={item.max} step={item.step} style={{ width: '100%' }} />
    case 'password':
      return <Input.Password value={String(value)} size="small" onChange={(e) => onChange(e.target.value)} />
    default:
      return <Input value={String(value)} size="small" onChange={(e) => onChange(e.target.value)} />
  }
}

export default function GeneralSettings({ values, onChange }: GeneralSettingsProps) {
  const [loading, setLoading] = useState(false)
  const handleSave = useCallback(() => { setLoading(true); setTimeout(() => { setLoading(false); message.success('设置已保存') }, 500) }, [])

  const renderSection = (title: string, icon: React.ReactNode, items: SettingEntry[]) => (
    <Card size="small" title={<Space>{icon}<Text>{title}</Text></Space>} style={{ marginBottom: 16 }}>
      <Form layout="vertical">
        {items.filter(item => isVisible(item, values)).map(item => (
          <Form.Item key={item.key} label={<Text strong style={{ fontSize: 13 }}>{item.label}</Text>} tooltip={item.description} style={{ marginBottom: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              {renderField(item, values[item.key] ?? item.defaultValue, (v) => onChange(item.key, v))}
              {item.secret && <Text type="secondary" style={{ fontSize: 12 }}>🔒 敏感信息</Text>}
            </Space>
          </Form.Item>
        ))}
      </Form>
    </Card>
  )

  return (
    <div style={{ maxWidth: 800 }}>
      <Space style={{ marginBottom: 16 }}><Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={loading}>保存设置</Button></Space>
      {renderSection('数据库设置', <DatabaseOutlined />, DATABASE_ITEMS)}
      {renderSection('系统控制', <LaptopOutlined />, SYSTEM_ITEMS)}
      {renderSection('数据源', <CloudServerOutlined />, DATA_SOURCE_ITEMS)}
    </div>
  )
}
