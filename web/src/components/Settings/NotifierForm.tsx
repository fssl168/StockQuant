import { Switch, Input, Typography } from 'antd'
import { Bell } from '@phosphor-icons/react'

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

const NOTIFICATION_ITEMS: SettingEntry[] = [
  { key: 'notification.dingtalk_webhook', value: '', defaultValue: '', value_type: 'password', label: 'DingTalk Webhook', description: '', secret: true },
  { key: 'notification.wechat_webhook', value: '', defaultValue: '', value_type: 'password', label: '企业微信 Webhook', description: '', secret: true },
  { key: 'notification.telegram_bot_token', value: '', defaultValue: '', value_type: 'password', label: 'Telegram Bot Token', description: '', secret: true },
  { key: 'notification.email_enabled', value: false, defaultValue: false, value_type: 'boolean', label: '邮件通知', description: '启用邮件推送', secret: false },
]

interface NotifierFormProps {
  values: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
}

export default function NotifierForm({ values, onChange }: NotifierFormProps) {
  const renderControl = (item: SettingEntry) => {
    const val = values[item.key]

    switch (item.value_type) {
      case 'boolean':
        return <Switch checked={val as boolean} onChange={(v) => onChange(item.key, v)} size="small" />
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
