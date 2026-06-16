import { Space, Switch, Select, Input, InputNumber, Slider, Typography } from 'antd'
import { Brain } from '@phosphor-icons/react'

const { Text } = Typography

interface SettingEntry {
  key: string
  value: unknown
  defaultValue: unknown
  value_type: string
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

const AI_MODEL_ITEMS: SettingEntry[] = [
  { key: 'ai_model.provider', value: 'openai', defaultValue: 'openai', value_type: 'select', label: 'LLM Provider', description: 'AI 模型提供商', secret: false, options: [{ value: 'openai', label: 'OpenAI' }, { value: 'anthropic', label: 'Anthropic' }, { value: 'deepseek', label: 'DeepSeek' }] },
  { key: 'ai_model.api_url', value: '', defaultValue: '', value_type: 'string', label: 'API URL', description: '模型接口地址', secret: false },
  { key: 'ai_model.api_key', value: '', defaultValue: '', value_type: 'password', label: 'API Key', description: '模型认证密钥', secret: true },
  { key: 'ai_model.model', value: 'gpt-4o', defaultValue: 'gpt-4o', value_type: 'select', label: '模型', description: '使用的具体模型', secret: false, options: [{ value: 'gpt-4o', label: 'GPT-4o' }, { value: 'gpt-4', label: 'GPT-4' }, { value: 'claude-3-opus', label: 'Claude 3 Opus' }] },
  { key: 'ai_model.temperature', value: 0.3, defaultValue: 0.3, value_type: 'float', label: 'Temperature', description: '生成随机性控制', secret: false, min: 0, max: 2, step: 0.1, scale: 10, slider: true },
  { key: 'ai_model.timeout_sec', value: 30, defaultValue: 30, value_type: 'number', label: '超时秒数', description: 'LLM 调用超时（秒）', secret: false, min: 5, max: 120, step: 5 },
]

interface LLMConfigFormProps {
  values: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
}

export default function LLMConfigForm({ values, onChange }: LLMConfigFormProps) {
  const renderControl = (item: SettingEntry) => {
    const val = values[item.key]

    switch (item.value_type) {
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
          <Input.Password
            value={val as string}
            placeholder="sk-..."
            size="small"
            style={{ minWidth: 180 }}
            onChange={(e) => onChange(item.key, e.target.value)}
          />
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
      {AI_MODEL_ITEMS.map((item) => (
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
