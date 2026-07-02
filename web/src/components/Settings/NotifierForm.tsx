import { Bell } from '@phosphor-icons/react';
import { SettingsField } from './SettingsField';
import type { SettingEntry } from './types';

interface NotifierFormProps {
  values: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}

const NOTIFICATION_ITEMS: Omit<SettingEntry, 'value' | 'onChange'>[] = [
  { key: 'notification.dingtalk_webhook', defaultValue: '', valueType: 'password', label: 'DingTalk Webhook', description: '', secret: true },
  { key: 'notification.wechat_webhook', defaultValue: '', valueType: 'password', label: '企业微信 Webhook', description: '', secret: true },
  { key: 'notification.telegram_bot_token', defaultValue: '', valueType: 'password', label: 'Telegram Bot Token', description: '', secret: true },
  { key: 'notification.feishu_webhook', defaultValue: '', valueType: 'password', label: '飞书 Webhook URL', description: '', secret: true },
  { key: 'notification.discord_webhook', defaultValue: '', valueType: 'password', label: 'Discord Webhook URL', description: '', secret: true },
  { key: 'notification.pushplus_token', defaultValue: '', valueType: 'password', label: 'PushPlus Token', description: '', secret: true },
  { key: 'notification.serverchan_key', defaultValue: '', valueType: 'password', label: 'Server酱 SendKey', description: '', secret: true },
  { key: 'notification.custom_webhook_url', defaultValue: '', valueType: 'password', label: '自定义 Webhook URL', description: '', secret: true },
  { key: 'notification.email_enabled', defaultValue: false, valueType: 'boolean', label: '邮件通知', description: '启用邮件推送', secret: false },
];

export default function NotifierForm({ values, onChange }: NotifierFormProps) {
  const getVal = (key: string, fallback?: unknown): unknown => {
    const v = values[key];
    if (v === null || v === undefined) return fallback;
    if (typeof v === 'object') return fallback ?? '';
    return v;
  };

  return (
    <div className="space-y-3">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <Bell size={16} weight="fill" style={{ color: 'var(--color-cyan)' }} />
        <span style={{ fontSize: 13, fontWeight: 600 }}>通知推送</span>
      </div>
      {NOTIFICATION_ITEMS.map((item) => (
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
