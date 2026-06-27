import { Badge } from 'antd'

const ROLE_META: Record<string, { label: string; color: string }> = {
  ADMIN: { label: '管理员', color: '#ef4444' },
  TRADER: { label: '交易员', color: '#3b82f6' },
  VIEWER: { label: '观察者', color: '#6b7280' },
}

interface RoleBadgeProps {
  role: string
  size?: 'small' | 'default'
}

export function RoleBadge({ role, size = 'default' }: RoleBadgeProps) {
  const meta = ROLE_META[role?.toUpperCase()] || ROLE_META.VIEWER
  return (
    <Badge
      count={meta.label}
      style={{
        backgroundColor: `${meta.color}22`,
        borderColor: meta.color,
        borderWidth: 1,
        borderStyle: 'solid',
        borderRadius: 4,
        padding: size === 'small' ? '0 6px' : '2px 8px',
      }}
    />
  )
}
