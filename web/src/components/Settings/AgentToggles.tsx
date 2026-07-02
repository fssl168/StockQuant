import { SettingsField } from './SettingsField';
import type { SettingEntry } from './types';
import { Rocket } from '@phosphor-icons/react';

interface AgentTogglesProps {
  values: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}

function isVisible(item: Omit<SettingEntry, 'value' | 'onChange'>, allValues: Record<string, unknown>): boolean {
  if (!item.when) return true;
  return item.when.values.includes(String(allValues[item.when.field]));
}

const EVOLUTION_ITEMS: Omit<SettingEntry, 'value' | 'onChange'>[] = [
  { key: 'evolution.enabled', defaultValue: false, valueType: 'boolean', label: '启用进化', description: '开启 AI 策略自动进化', secret: false },
  { key: 'evolution.llm_provider', defaultValue: 'openai', valueType: 'select', label: '进化 LLM', description: '策略进化专用模型', secret: false, options: [{ value: 'openai', label: 'OpenAI' }, { value: 'anthropic', label: 'Anthropic' }, { value: 'custom', label: '自定义' }] },
  { key: 'evolution.llm_model', defaultValue: 'gpt-4o', valueType: 'string', label: '进化模型', description: '', secret: false, when: { field: 'evolution.llm_provider', values: ['openai', 'custom'] } },
  { key: 'evolution.anthropic_model', defaultValue: 'claude-3-opus', valueType: 'string', label: '进化模型', description: 'Claude 模型名称', secret: false, when: { field: 'evolution.llm_provider', values: ['anthropic'] } },
  { key: 'evolution.api_key', defaultValue: '', valueType: 'password', label: 'API Key', description: '进化 LLM API 密钥', secret: true },
  { key: 'evolution.api_base', defaultValue: '', valueType: 'string', label: 'API Base URL', description: '自定义 API 地址（留空用官方默认）', secret: false },
  { key: 'evolution.llm_temperature', defaultValue: 0.5, valueType: 'float', label: '进化温度', description: '生成温度 (0-2)', secret: false, min: 0, max: 2, step: 0.1, scale: 10, slider: true },
  { key: 'evolution.max_tokens', defaultValue: 4096, valueType: 'number', label: 'Max Tokens', description: '单次最大生成 token 数', secret: false, min: 256, max: 128000, step: 256 },
  { key: 'evolution.llm_retry', defaultValue: 3, valueType: 'number', label: '重试次数', description: '进化失败重试次数', secret: false, min: 0, max: 10, step: 1 },
];

export default function AgentToggles({ values, onChange }: AgentTogglesProps) {
  const getVal = (key: string, fallback?: unknown): unknown => {
    const v = values[key];
    if (v === null || v === undefined) return fallback;
    if (typeof v === 'object') return fallback ?? '';
    return v;
  };

  return (
    <div className="space-y-3">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <Rocket size={16} weight="fill" style={{ color: 'var(--color-cyan)' }} />
        <span style={{ fontSize: 13, fontWeight: 600 }}>策略进化</span>
      </div>
      {EVOLUTION_ITEMS.filter((item) => isVisible(item, values)).map((item) => (
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
