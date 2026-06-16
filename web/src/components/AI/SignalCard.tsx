import { Typography } from 'antd'

const { Text } = Typography

interface SignalCardProps {
  type: string
  title: string
  message: string
  time: string
  confidence?: number
}

export default function SignalCard({ title, message, time, confidence }: SignalCardProps) {
  return (
    <div
      style={{
        padding: '10px 14px',
        borderBottom: '1px solid var(--color-bg-surface)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <Text style={{ fontSize: 12, fontWeight: 500 }}>{title}</Text>
        <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 1 }}>{message}</div>
        {confidence != null && (
          <div style={{ fontSize: 10, color: 'var(--color-brand-primary)', marginTop: 2 }}>
            置信度 {(confidence * 100).toFixed(0)}%
          </div>
        )}
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
        {time}
      </span>
    </div>
  )
}
