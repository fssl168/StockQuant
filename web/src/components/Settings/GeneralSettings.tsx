import { SettingsField } from './SettingsField';
import type { SettingEntry } from './types';
import { Database, Monitor, Cloud } from '@phosphor-icons/react';

interface GeneralSettingsProps {
  values: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}

function isVisible(item: Omit<SettingEntry, 'value' | 'onChange'>, allValues: Record<string, unknown>): boolean {
  if (!item.when) return true;
  return item.when.values.includes(String(allValues[item.when.field]));
}

function getVal(values: Record<string, unknown>, key: string, fallback?: unknown): unknown {
  const v = values[key];
  if (v === null || v === undefined) return fallback;
  if (typeof v === 'object') return fallback ?? '';
  return v;
}

function renderSection(
  title: string,
  icon: React.ReactNode,
  items: Omit<SettingEntry, 'value' | 'onChange'>[],
  values: Record<string, unknown>,
  onChange: (key: string, value: unknown) => void,
) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        {icon}
        <span style={{ fontSize: 13, fontWeight: 600 }}>{title}</span>
      </div>
      <div className="space-y-3">
        {items.filter((item) => isVisible(item, values)).map((item) => (
          <SettingsField
            key={item.key}
            item={{ ...item, value: getVal(values, item.key, item.defaultValue) } as SettingEntry}
            value={getVal(values, item.key, item.defaultValue)}
            disabled={false}
            onChange={onChange}
          />
        ))}
      </div>
    </div>
  );
}

const DATABASE_ITEMS: Omit<SettingEntry, 'value' | 'onChange'>[] = [
  { key: 'database.url', defaultValue: '', valueType: 'password', label: '数据库URL', description: '连接字符串', secret: true },
  { key: 'database.pool_size', defaultValue: 10, valueType: 'number', label: '连接池大小', min: 1, max: 100, step: 1 },
  { key: 'database.max_overflow', defaultValue: 20, valueType: 'number', label: '最大溢出', min: 0, max: 100, step: 1 },
  { key: 'database.pool_timeout', defaultValue: 30, valueType: 'number', label: '超时时间', min: 1, max: 300, step: 1 },
  { key: 'database.echo', defaultValue: false, valueType: 'boolean', label: 'SQL 日志' },
];

const SYSTEM_ITEMS: Omit<SettingEntry, 'value' | 'onChange'>[] = [
  { key: 'trading.mode', defaultValue: 'simulator', valueType: 'select', label: '交易模式', options: [{ value: 'backtest', label: '回测模式' }, { value: 'simulator', label: '模拟实盘' }, { value: 'live', label: '实盘' }] },
  { key: 'system.log_level', defaultValue: 'INFO', valueType: 'select', label: '日志级别', options: [{ value: 'DEBUG', label: 'DEBUG' }, { value: 'INFO', label: 'INFO' }, { value: 'WARNING', label: 'WARNING' }, { value: 'ERROR', label: 'ERROR' }] },
  { key: 'system.web_port', defaultValue: 8000, valueType: 'number', label: 'Web 端口', min: 1, max: 65535, step: 1 },
  { key: 'system.initial_capital', defaultValue: 1000000, valueType: 'number', label: '初始资金', min: 10000, max: 1_000_000_000, step: 100000 },
];

const DATA_SOURCE_ITEMS: Omit<SettingEntry, 'value' | 'onChange'>[] = [
  { key: 'data_provider.source', defaultValue: 'alphafeed', valueType: 'select', label: '默认数据源', options: [{ value: 'alphafeed', label: 'AlphaFeed (推荐)' }, { value: 'baostock', label: 'BaoStock' }, { value: 'akshare', label: 'AkShare' }, { value: 'csv', label: 'CSV' }] },
  { key: 'data_provider.alphafeed_key', defaultValue: '', valueType: 'password', label: 'AlphaFeed Key', description: '', secret: true, when: { field: 'data_provider.source', values: ['alphafeed'] } },
  { key: 'data_provider.api_key', defaultValue: '', valueType: 'password', label: 'API Key', description: '', secret: true, when: { field: 'data_provider.source', values: ['akshare'] } },
  { key: 'baostock.enabled', defaultValue: true, valueType: 'boolean', label: '启用 BaoStock', when: { field: 'data_provider.source', values: ['baostock'] } },
];

export default function GeneralSettings({ values, onChange }: GeneralSettingsProps) {
  return (
    <div className="space-y-6">
      {renderSection('数据库设置', (
        <Database size={16} weight="fill" style={{ color: 'var(--color-cyan)' }} />
      ), DATABASE_ITEMS, values, onChange)}
      {renderSection('系统控制', (
        <Monitor size={16} weight="fill" style={{ color: 'var(--color-cyan)' }} />
      ), SYSTEM_ITEMS, values, onChange)}
      {renderSection('数据源', (
        <Cloud size={16} weight="fill" style={{ color: 'var(--color-cyan)' }} />
      ), DATA_SOURCE_ITEMS, values, onChange)}
    </div>
  );
}
