import { Empty } from 'antd'
import { Sparkle } from '@phosphor-icons/react'

interface NotificationItem {
  type: string
  title: string
  message: string
  time: string
}

interface NotificationListProps {
  notifications: NotificationItem[]
  maxItems?: number
}

export default function NotificationList({ notifications, maxItems = 5 }: NotificationListProps) {
  if (notifications.length === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <span style={{ color: 'var(--color-text-tertiary)', fontSize: 12 }}>
            <Sparkle size={24} weight="duotone" style={{ color: '#3b82f6', marginBottom: 8, display: 'block' }} />
            暂无活跃信号
          </span>
        }
      />
    )
  }

  return (
    <div style={{ maxHeight: 220, overflow: 'auto' }}>
      {notifications.slice(0, maxItems).map((n, i) => (
        <div
          key={`${n.title}-${i}`}
          style={{
            padding: '10px 0',
            borderBottom: '1px solid var(--color-border-default)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: 12,
                fontWeight: 500,
                color: 'var(--color-text-secondary)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {n.title}
            </div>
            <div
              style={{
                fontSize: 11,
                color: 'var(--color-text-tertiary)',
                marginTop: 2,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {n.message}
            </div>
          </div>
          <span
            style={{
              fontSize: 10,
              color: 'var(--color-text-disabled)',
              fontFamily: 'var(--font-mono)',
              whiteSpace: 'nowrap',
              marginLeft: 12,
            }}
          >
            {n.time}
          </span>
        </div>
      ))}
    </div>
  )
}
