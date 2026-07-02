import { SettingsField } from './SettingsField';
import type { SettingEntry } from './types';
import { Wallet } from '@phosphor-icons/react';

interface TradingSettingsProps {
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

const TRADING_COST_ITEMS: Omit<SettingEntry, 'value' | 'onChange'>[] = [
  { key: 'system.commission_rate', defaultValue: 0.00025, valueType: 'float', label: '佣金费率', min: 0, max: 0.003, step: 0.00001, scale: 100000, slider: true },
  { key: 'system.min_commission', defaultValue: 5, valueType: 'number', label: '最低佣金', min: 0, max: 50, step: 0.5 },
  { key: 'system.stamp_tax_rate', defaultValue: 0.0005, valueType: 'float', label: '印花税率', min: 0, max: 0.01, step: 0.0001, scale: 10000, slider: true },
];

const EXECUTION_ITEMS: Omit<SettingEntry, 'value' | 'onChange'>[] = [
  { key: 'system.slippage', defaultValue: 0, valueType: 'float', label: '滑点', min: 0, max: 1, step: 0.01, scale: 100, slider: true },
  { key: 'system.lot_size', defaultValue: 100, valueType: 'number', label: '最小交易单位', min: 100, max: 1000, step: 100 },
  { key: 'system.price_limit_ratio', defaultValue: 0.1, valueType: 'float', label: '涨跌停比例', min: 0.05, max: 0.3, step: 0.01, scale: 100, slider: true },
];

export default function TradingSettings({ values, onChange }: TradingSettingsProps) {
  return (
    <div className="space-y-6">
      {renderSection('交易成本', (
        <Wallet size={16} weight="fill" style={{ color: 'var(--color-cyan)' }} />
      ), TRADING_COST_ITEMS, values, onChange)}
      {renderSection('执行参数', (
        <Wallet size={16} weight="fill" style={{ color: 'var(--color-cyan)' }} />
      ), EXECUTION_ITEMS, values, onChange)}
    </div>
  );
}
