import { Space, Switch, Select, Input, InputNumber, Slider, Typography } from 'antd'
import { Brain } from '@phosphor-icons/react'

const { Text } = Typography

interface SettingEntry {
  key: string
  value: unknown
  defaultValue: unknown
  valueType: string
  label: string
  description: string
  secret: boolean
  min?: number
  max?: number
  step?: number
  scale?: number
  unit?: string
  slider?: boolean
  options?: { value: string; label: string }[]
  when?: { field: string; values: string[] }
}

const isVisible = (item: SettingEntry, allValues: Record<string, unknown>): boolean => {
  if (!item.when) return true
  const fieldValue = allValues[item.when.field]
  return item.when.values.includes(String(fieldValue))
}

const AI_MODEL_ITEMS: SettingEntry[] = [
  { key: 'ai.provider', value: 'openai', defaultValue: 'openai', valueType: 'select', label: 'AI 模型', description: '主模型', secret: false, options: [{ value: 'openai', label: 'OpenAI' }, { value: 'anthropic', label: 'Anthropic' }, { value: 'custom', label: '自定义' }] },
  { key: 'ai.model', value: 'gpt-4o', defaultValue: 'gpt-4o', valueType: 'string', label: '主模型', description: 'OpenAI / 兼容 API 模型名称', secret: false, when: { field: 'ai.provider', values: ['openai', 'custom'] } },
  { key: 'ai.api_key', value: '', defaultValue: '', valueType: 'password', label: 'API Key', description: 'OpenAI / 兼容 API 密钥', secret: true },
  { key: 'ai.api_base', value: '', defaultValue: '', valueType: 'string', label: 'API Base URL', description: '自定义 API 地址（留空用官方默认）', secret: false },
  { key: 'ai.temperature', value: 0.7, defaultValue: 0.7, valueType: 'float', label: 'Temperature', description: '生成温度 (0-2)', secret: false, min: 0, max: 2, step: 0.1, scale: 10, slider: true },
  { key: 'ai.max_tokens', value: 4096, defaultValue: 4096, valueType: 'number', label: 'Max Tokens', description: '单次最大生成 token 数', secret: false, min: 256, max: 128000, step: 256 },
  { key: 'ai.anthropic_model', value: 'claude-sonnet-4-20250514', defaultValue: 'claude-sonnet-4-20250514', valueType: 'string', label: 'Anthropic 模型', description: 'Claude 模型名称', secret: false, when: { field: 'ai.provider', values: ['anthropic'] } },
  { key: 'ai.anthropic_api_key', value: '', defaultValue: '', valueType: 'password', label: 'Anthropic API Key', description: 'Anthropic API 密钥', secret: true },
  { key: 'ai.anthropic_api_base', value: '', defaultValue: '', valueType: 'string', label: 'Anthropic API Base', description: '自定义 Anthropic API 地址', secret: false },
]

interface LLMConfigFormProps {
  values: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
}

export default function LLMConfigForm({ values, onChange }: LLMConfigFormProps) {
  const getVal = (key: string, fallback?: unknown) => {
    const v = values[key]
    if (v === null || v === undefined) return fallback
    if (typeof v === 'object') return fallback ?? ''
    return v
  }

  const renderControl = (item: SettingEntry) => {
    const val = getVal(item.key, item.defaultValue)

    switch (item.valueType) {
      case 'boolean':
        return <Switch checked={val as boolean} onChange={(v) => onChange(item.key, v)} size="small" />
      case 'select':
        return (
          <Select
            value={val as string}
            onChange={(v) => onChange(item.key, v)}
            size="small"
            style={{ minWidth: 160 }}
            options={item.options}
          />
        )
      case 'password':
        return (
          <form onSubmit={(e) => e.preventDefault()}>
            <Input.Password
              value={val as string}
              placeholder="sk-..."
              size="small"
              style={{ minWidth: 180 }}
              onChange={(e) => onChange(item.key, e.target.value)}
            />
          </form>
        )
      case 'string':
        return (
          <Input
            value={String(val ?? '')}
            size="small"
            style={{ minWidth: 180 }}
            placeholder={item.description}
            onChange={(e) => onChange(item.key, e.target.value)}
          />
        )
      case 'float':
      case 'number': {
        const numVal = typeof val === 'number' ? val : parseFloat(String(val ?? 0))
        if (item.slider) {
          return (
            <Space direction="vertical" style={{ width: 200 }} size={4}>
              <Slider
                min={item.min ?? 0}
                max={item.max ?? 100}
                step={item.step ?? 0.01}
                value={numVal * (item.scale ?? 1)}
                onChange={(v) => onChange(item.key, v / (item.scale ?? 1))}
                tooltip={{ formatter: (v) => v ? `${(v * (item.scale ?? 1)).toFixed(2)}${item.unit ?? ''}` : '' }}
              />
              <InputNumber
                value={numVal}
                min={item.min}
                max={item.max}
                step={item.step}
                style={{ width: '100%' }}
                size="small"
                formatter={(v) => `${v}${item.unit ?? ''}`}
                parser={(v) => parseFloat(v ?? '0') / (item.scale ?? 1)}
                onChange={(v) => onChange(item.key, v)}
              />
            </Space>
          )
        }
        return (
          <InputNumber
            value={numVal}
            min={item.min}
            max={item.max}
            step={item.step ?? 1}
            size="small"
            style={{ minWidth: 120 }}
            formatter={(v) => `${v}${item.unit ?? ''}`}
            parser={(v) => parseFloat(v ?? '0')}
            onChange={(v) => onChange(item.key, v)}
          />
        )
      }
      default:
        return <Input value={String(val)} size="small" onChange={(e) => onChange(item.key, e.target.value)} />
    }
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={10}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <Brain size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />
        <Text style={{ fontSize: 13, fontWeight: 600 }}>AI 模型</Text>
      </div>
      {AI_MODEL_ITEMS.filter((item) => isVisible(item, values)).map((item) => (
        <div
          key={item.key}
          style={{
            display: 'grid',
            gridTemplateColumns: '140px 1fr',
            gap: 12,
            alignItems: 'center',
            padding: '6px 12px',
            borderRadius: 6,
          }}
        >
          <div>
            <Text style={{ fontSize: 12, fontWeight: 500 }}>{item.label}</Text>
            {item.description && (
              <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 1 }}>{item.description}</div>
            )}
          </div>
          {renderControl(item)}
        </div>
      ))}
    </Space>
  )
}
