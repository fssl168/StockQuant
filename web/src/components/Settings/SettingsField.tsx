import { useState } from 'react';
import type React from 'react';
import { EyeToggleIcon, Select } from '../common';

interface ValidationIssue {
  code: string;
  key: string;
  severity: 'error' | 'warning';
  message: string;
}

interface SettingEntry {
  key: string;
  value: unknown;
  defaultValue: unknown;
  valueType: 'string' | 'number' | 'boolean' | 'select' | 'password' | 'float';
  label: string;
  description?: string;
  secret?: boolean;
  min?: number;
  max?: number;
  step?: number;
  scale?: number;
  unit?: string;
  slider?: boolean;
  options?: { value: string; label: string }[];
  when?: { field: string; values: string[] };
}

interface SettingsFieldProps {
  item: SettingEntry;
  value: unknown;
  disabled?: boolean;
  onChange: (key: string, value: unknown) => void;
  issues?: ValidationIssue[];
}

function renderFieldControl(
  item: SettingEntry,
  rawValue: unknown,
  disabled: boolean,
  onChange: (nextValue: unknown) => void,
  isSecretVisible: boolean,
  onToggleSecretVisible: () => void,
  isPasswordEditable: boolean,
  onPasswordFocus: () => void,
) {
  const value = rawValue ?? item.defaultValue;
  const commonClass = 'input-terminal';

  if (item.valueType === 'boolean') {
    const checked = value as boolean;
    return (
      <label className="inline-flex cursor-pointer items-center gap-3">
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled || false}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="text-sm text-secondary">{checked ? '已启用' : '未启用'}</span>
      </label>
    );
  }

  if (item.valueType === 'select' && item.options?.length) {
    return (
      <Select
        value={String(value)}
        onChange={(v) => onChange(v)}
        options={item.options}
        disabled={disabled || false}
        placeholder="请选择"
        className="min-w-[160px]"
      />
    );
  }

  if (item.valueType === 'password') {
    return (
      <div className="flex items-center gap-2">
        <input
          type={isSecretVisible ? 'text' : 'password'}
          readOnly={!isPasswordEditable}
          onFocus={onPasswordFocus}
          className={`${commonClass} flex-1`}
          value={String(value ?? '')}
          disabled={disabled || false}
          onChange={(e) => onChange(e.target.value)}
        />
        <button
          type="button"
          className="btn-secondary !p-2"
          disabled={disabled || false}
          onClick={onToggleSecretVisible}
          title={isSecretVisible ? '隐藏' : '显示'}
          aria-label={isSecretVisible ? '隐藏密码' : '显示密码'}
        >
          <EyeToggleIcon visible={isSecretVisible} />
        </button>
      </div>
    );
  }

  if (item.valueType === 'float' && item.slider) {
    const numVal = typeof value === 'number' ? value : parseFloat(String(value ?? 0));
    const scaled = numVal * (item.scale ?? 1);
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%' }}>
        <input
          type="range"
          min={item.min ?? 0}
          max={(item.max ?? 100) * (item.scale ?? 1)}
          step={item.step ?? 0.01}
          value={scaled}
          disabled={disabled || false}
          onChange={(e) => onChange(parseFloat(e.target.value) / (item.scale ?? 1))}
          className="w-full accent-cyan"
          style={{
            height: 6,
            appearance: 'auto',
            cursor: 'pointer',
          }}
        />
        <input
          type="number"
          className={commonClass}
          value={numVal}
          disabled={disabled || false}
          min={item.min}
          max={item.max}
          step={item.step ?? 0.01}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          style={{ width: 160 }}
        />
      </div>
    );
  }

  if (item.valueType === 'number') {
    const numVal = typeof value === 'number' ? value : parseFloat(String(value ?? 0));
    return (
      <input
        type="number"
        className={commonClass}
        value={numVal}
        disabled={disabled || false}
        min={item.min}
        max={item.max}
        step={item.step ?? 1}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        style={{ width: 160 }}
      />
    );
  }

  // default: text or password-like string
  return (
    <input
      type="text"
      className={commonClass}
      value={String(value ?? '')}
      disabled={disabled || false}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

export const SettingsField: React.FC<SettingsFieldProps> = ({
  item,
  value,
  disabled = false,
  onChange,
  issues = [],
}) => {
  const hasError = issues.some((i) => i.severity === 'error');
  const [isSecretVisible, setIsSecretVisible] = useState(false);
  const [isPasswordEditable, setIsPasswordEditable] = useState(false);

  return (
    <div className={`rounded-xl border p-4 ${hasError ? 'border-red-500/35' : 'border-white/8'} bg-elevated/50`}>
      <div className="mb-2 flex items-center gap-2">
        <label className="text-sm font-semibold text-white" htmlFor={`setting-${item.key}`}>
          {item.label}
        </label>
        {item.secret ? (
          <span className="badge badge-purple text-[10px]">敏感</span>
        ) : null}
      </div>

      {item.description ? (
        <p className="mb-3 text-xs text-muted" title={item.description}>
          {item.description}
        </p>
      ) : null}

      <div id={`setting-${item.key}`}>
        {renderFieldControl(
          item,
          value,
          disabled,
          (nextValue) => onChange(item.key, nextValue),
          isSecretVisible,
          () => setIsSecretVisible((prev) => !prev),
          isPasswordEditable,
          () => setIsPasswordEditable(true),
        )}
      </div>

      {item.secret ? (
        <p className="mt-2 text-[11px] text-secondary">
          密钥默认隐藏，可点击眼睛图标查看明文。
        </p>
      ) : null}

      {issues.length ? (
        <div className="mt-2 space-y-1">
          {issues.map((issue, index) => (
            <p
              key={`${issue.code}-${issue.key}-${index}`}
              className={issue.severity === 'error' ? 'text-xs text-danger' : 'text-xs text-warning'}
            >
              {issue.message}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
};
