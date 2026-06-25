import { Card, Form, InputNumber, Slider, Space, Typography } from 'antd'
import { WalletOutlined } from '@ant-design/icons'
import type { SettingEntry } from './types'

const { Text: AntText } = Typography

interface TradingSettingsProps {
  values: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
}

const TRADING_COST_ITEMS: SettingEntry[] = [
  { key: 'system.commission_rate', value: 0.00025, defaultValue: 0.00025, value_type: 'float', label: '佣金费率', min: 0, max: 0.003, step: 0.00001, scale: 100000, unit: '%', slider: true },
  { key: 'system.min_commission', value: 5, defaultValue: 5, value_type: 'number', label: '最低佣金', min: 0, max: 50, step: 0.5 },
  { key: 'system.stamp_tax_rate', value: 0.0005, defaultValue: 0.0005, value_type: 'float', label: '印花税率', min: 0, max: 0.01, step: 0.0001, scale: 10000, unit: '%', slider: true },
]

const EXECUTION_ITEMS: SettingEntry[] = [
  { key: 'system.slippage', value: 0, defaultValue: 0, value_type: 'float', label: '滑点', min: 0, max: 1, step: 0.01, scale: 100, unit: '分', slider: true },
  { key: 'system.lot_size', value: 100, defaultValue: 100, value_type: 'number', label: '最小交易单位', min: 100, max: 1000, step: 100 },
  { key: 'system.price_limit_ratio', value: 0.1, defaultValue: 0.1, value_type: 'float', label: '涨跌停比例', min: 0.05, max: 0.3, step: 0.01, scale: 100, unit: '%', slider: true },
]

function isVisible(item: SettingEntry, allValues: Record<string, unknown>): boolean {
  if (!item.when) return true
  return item.when.values.includes(allValues[item.when.field] as string)
}

function renderField(item: SettingEntry, value: unknown, onChange: (v: unknown) => void) {
  if (item.value_type === 'float' && item.slider) {
    return (
      <Space direction="vertical" style={{ width: '100%' }}>
        <Slider value={(value as number) * (item.scale ?? 1)} min={0} max={(item.max ?? 1) * (item.scale ?? 1)} onChange={(v) => onChange(v / (item.scale ?? 1))} tooltip={{ formatter: (v) => v ? `${(v * (item.scale ?? 1)).toFixed(2)}${item.unit ?? ''}` : '' }} />
        <InputNumber value={value as number} onChange={onChange} size="small" style={{ width: '100%' }} />
      </Space>
    )
  }
  return <InputNumber value={value as number} onChange={onChange} size="small" min={item.min} max={item.max} step={item.step} style={{ width: '100%' }} />
}

export default function TradingSettings({ values, onChange }: TradingSettingsProps) {
  const renderSection = (title: string, icon: React.ReactNode, items: SettingEntry[]) => (
    <Card size="small" title={<Space>{icon}<AntText>{title}</AntText></Space>} style={{ marginBottom: 16 }}>
      <Form layout="vertical">
        {items.filter(item => isVisible(item, values)).map(item => (
          <Form.Item key={item.key} label={<AntText strong style={{ fontSize: 13 }}>{item.label}</AntText>} tooltip={item.description} style={{ marginBottom: 12 }}>
            {renderField(item, values[item.key] ?? item.defaultValue, (v) => onChange(item.key, v))}
          </Form.Item>
        ))}
      </Form>
    </Card>
  )

  return (
    <div style={{ maxWidth: 800 }}>
      {renderSection('交易成本', <WalletOutlined />, TRADING_COST_ITEMS)}
      {renderSection('执行参数', <WalletOutlined />, EXECUTION_ITEMS)}
    </div>
  )
}
