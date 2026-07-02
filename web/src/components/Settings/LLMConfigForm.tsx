import { Brain } from '@phosphor-icons/react';
import { SettingsField } from './SettingsField';
import type { SettingEntry } from './types';

interface LLMConfigFormProps {
  values: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}

const AI_MODEL_ITEMS: Omit<SettingEntry, 'value' | 'onChange'>[] = [
  { key: 'ai.provider', defaultValue: 'openai', valueType: 'select', label: 'AI 模型供应商', description: '选择 AI 模型供应商', secret: false, options: [{ value: 'openai', label: 'OpenAI' }, { value: 'anthropic', label: 'Anthropic' }, { value: 'custom', label: '自定义' }] },
  { key: 'ai.model', defaultValue: 'gpt-4o', valueType: 'string', label: '主模型名称', description: 'OpenAI / 兼容 API 模型名称', secret: false, when: { field: 'ai.provider', values: ['openai', 'custom'] } },
  { key: 'ai.api_key', defaultValue: '', valueType: 'password', label: 'API Key', description: 'OpenAI / 兼容 API 密钥', secret: true },
  { key: 'ai.api_base', defaultValue: '', valueType: 'string', label: 'API Base URL', description: '自定义 API 地址（留空用官方默认）', secret: false },
  { key: 'ai.temperature', defaultValue: 0.7, valueType: 'float', label: 'Temperature', description: '生成温度 (0-2)', secret: false, min: 0, max: 2, step: 0.1, scale: 10, slider: true },
  { key: 'ai.max_tokens', defaultValue: 4096, valueType: 'number', label: 'Max Tokens', description: '单次最大生成 token 数', secret: false, min: 256, max: 128000, step: 256 },
  { key: 'ai.anthropic_model', defaultValue: 'claude-sonnet-4-20250514', valueType: 'string', label: 'Anthropic 模型', description: 'Claude 模型名称', secret: false, when: { field: 'ai.provider', values: ['anthropic'] } },
  { key: 'ai.anthropic_api_key', defaultValue: '', valueType: 'password', label: 'Anthropic API Key', description: 'Anthropic API 密钥', secret: true },
  { key: 'ai.anthropic_api_base', defaultValue: '', valueType: 'string', label: 'Anthropic API Base', description: '自定义 Anthropic API 地址', secret: false },
];

function isVisible(item: Omit<SettingEntry, 'value' | 'onChange'>, allValues: Record<string, unknown>): boolean {
  if (!item.when) return true;
  return item.when.values.includes(String(allValues[item.when.field]));
}

export default function LLMConfigForm({ values, onChange }: LLMConfigFormProps) {
  const getVal = (key: string, fallback?: unknown): unknown => {
    const v = values[key];
    if (v === null || v === undefined) return fallback;
    if (typeof v === 'object') return fallback ?? '';
    return v;
  };

  return (
    <div className="space-y-3">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <Brain size={16} weight="fill" style={{ color: 'var(--color-cyan)' }} />
        <span style={{ fontSize: 13, fontWeight: 600 }}>AI 模型</span>
      </div>
      {AI_MODEL_ITEMS.filter((item) => isVisible(item, values)).map((item) => (
        <SettingsField
          key={item.key}
          item={{ ...item, value: getVal(item.key, item.defaultValue) } as SettingEntry}
          value={getVal(item.key, item.defaultValue)}
          disabled={false}
          onChange={onChange}
        />
      ))}
    </div>
  );
}
