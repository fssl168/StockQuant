import { Switch, Select, Input, InputNumber, Slider, Space, Typography } from 'antd'
import { Rocket } from '@phosphor-icons/react'

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

const EVOLUTION_ITEMS: SettingEntry[] = [
  { key: 'evolution.enabled', value: false, defaultValue: false, valueType: 'boolean', label: '启用进化', description: '开启 AI 策略自动进化', secret: false },
  { key: 'evolution.llm_provider', value: 'openai', defaultValue: 'openai', valueType: 'select', label: '进化 LLM', description: '策略进化专用模型', secret: false, options: [{ value: 'openai', label: 'OpenAI' }, { value: 'anthropic', label: 'Anthropic' }, { value: 'custom', label: '自定义' }] },
  { key: 'evolution.llm_model', value: 'gpt-4o', defaultValue: 'gpt-4o', valueType: 'string', label: '进化模型', description: '', secret: false, when: { field: 'evolution.llm_provider', values: ['openai', 'custom'] } },
  { key: 'evolution.anthropic_model', value: 'claude-3-opus', defaultValue: 'claude-3-opus', valueType: 'string', label: '进化模型', description: 'Claude 模型名称', secret: false, when: { field: 'evolution.llm_provider', values: ['anthropic'] } },
  { key: 'evolution.api_key', value: '', defaultValue: '', valueType: 'password', label: 'API Key', description: '进化 LLM API 密钥', secret: true },
  { key: 'evolution.api_base', value: '', defaultValue: '', valueType: 'string', label: 'API Base URL', description: '自定义 API 地址（留空用官方默认）', secret: false },
  { key: 'evolution.llm_temperature', value: 0.5, defaultValue: 0.5, valueType: 'float', label: '进化温度', description: '生成温度 (0-2)', secret: false, min: 0, max: 2, step: 0.1, scale: 10, slider: true },
  { key: 'evolution.max_tokens', value: 4096, defaultValue: 4096, valueType: 'number', label: 'Max Tokens', description: '单次最大生成 token 数', secret: false, min: 256, max: 128000, step: 256 },
  { key: 'evolution.llm_retry', value: 3, defaultValue: 3, valueType: 'number', label: '重试次数', description: '进化失败重试次数', secret: false, min: 0, max: 10, step: 1 },
]

interface AgentTogglesProps {
  values: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
}

export default function AgentToggles({ values, onChange }: AgentTogglesProps) {
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
            onChange={(v) => onChange(item.key, v)}
          />
        )
      }
      case 'password':
        return (
          <form onSubmit={(e) => e.preventDefault()}>
            <Input.Password
              value={String(val ?? '')}
              size="small"
              style={{ minWidth: 180 }}
              placeholder="sk-..."
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
    }
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={10}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <Rocket size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />
        <Text style={{ fontSize: 13, fontWeight: 600 }}>策略进化</Text>
      </div>
      {EVOLUTION_ITEMS.filter((item) => isVisible(item, values)).map((item) => (
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
