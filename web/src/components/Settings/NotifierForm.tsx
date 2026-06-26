import { Switch, Input, Typography } from 'antd'
import { Bell } from '@phosphor-icons/react'

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

const NOTIFICATION_ITEMS: SettingEntry[] = [
  { key: 'notification.dingtalk_webhook', value: '', defaultValue: '', valueType: 'password', label: 'DingTalk Webhook', description: '', secret: true },
  { key: 'notification.wechat_webhook', value: '', defaultValue: '', valueType: 'password', label: '企业微信 Webhook', description: '', secret: true },
  { key: 'notification.telegram_bot_token', value: '', defaultValue: '', valueType: 'password', label: 'Telegram Bot Token', description: '', secret: true },
  { key: 'notification.feishu_webhook', value: '', defaultValue: '', valueType: 'password', label: '飞书 Webhook URL', description: '', secret: true },
  { key: 'notification.discord_webhook', value: '', defaultValue: '', valueType: 'password', label: 'Discord Webhook URL', description: '', secret: true },
  { key: 'notification.pushplus_token', value: '', defaultValue: '', valueType: 'password', label: 'PushPlus Token', description: '', secret: true },
  { key: 'notification.serverchan_key', value: '', defaultValue: '', valueType: 'password', label: 'Server酱 SendKey', description: '', secret: true },
  { key: 'notification.custom_webhook_url', value: '', defaultValue: '', valueType: 'password', label: '自定义 Webhook URL', description: '', secret: true },
  { key: 'notification.email_enabled', value: false, defaultValue: false, valueType: 'boolean', label: '邮件通知', description: '启用邮件推送', secret: false },
]

interface NotifierFormProps {
  values: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
}

export default function NotifierForm({ values, onChange }: NotifierFormProps) {
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
      default:
        return <Input value={String(val)} size="small" onChange={(e) => onChange(item.key, e.target.value)} />
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <Bell size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />
        <Text style={{ fontSize: 13, fontWeight: 600 }}>通知推送</Text>
      </div>
      {NOTIFICATION_ITEMS.map((item) => (
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
    </div>
  )
}
