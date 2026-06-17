import { Typography, Tag, Collapse, Button } from 'antd'
import { TrendUp, TrendDown, Minus, CheckCircle, CaretRight } from '@phosphor-icons/react'

const { Text, Paragraph } = Typography

const SIGNAL_STYLES: Record<string, { borderColor: string; accentColor: string; bgColor: string; tagColor: string; icon: React.ReactNode }> = {
  BUY: {
    borderColor: '#52c41a',
    accentColor: '#52c41a',
    bgColor: 'rgba(82, 196, 26, 0.06)',
    tagColor: 'green',
    icon: <TrendUp size={14} weight="fill" style={{ color: '#52c41a' }} />,
  },
  SELL: {
    borderColor: '#ff4d4f',
    accentColor: '#ff4d4f',
    bgColor: 'rgba(255, 77, 79, 0.06)',
    tagColor: 'red',
    icon: <TrendDown size={14} weight="fill" style={{ color: '#ff4d4f' }} />,
  },
  NEUTRAL: {
    borderColor: '#d9d9d9',
    accentColor: '#8c8c8c',
    bgColor: 'rgba(140, 140, 140, 0.04)',
    tagColor: 'default',
    icon: <Minus size={14} weight="fill" style={{ color: '#8c8c8c' }} />,
  },
}

interface SignalCardProps {
  type: string
  title: string
  message: string
  time: string
  confidence?: number
  reasoning?: string
  signalId?: string
  onConfirm?: (signalId: string) => void
}

export default function SignalCard({ type, title, message, time, confidence, reasoning, signalId, onConfirm }: SignalCardProps) {
  const style = SIGNAL_STYLES[type] ?? SIGNAL_STYLES.NEUTRAL
  const showConfirm = (type === 'BUY' || type === 'SELL') && onConfirm && signalId

  return (
    <div
      style={{
        padding: '10px 14px',
        borderLeft: `3px solid ${style.borderColor}`,
        borderBottom: '1px solid var(--color-bg-surface)',
        background: style.bgColor,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        borderRadius: 4,
        gap: 10,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {style.icon}
          <Text style={{ fontSize: 12, fontWeight: 500 }}>{title}</Text>
          <Tag color={style.tagColor} style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px', margin: 0 }}>
            {type}
          </Tag>
        </div>
        <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 3 }}>{message}</div>
        {confidence != null && (
          <div style={{ fontSize: 10, color: style.accentColor, marginTop: 2 }}>
            置信度 {(confidence * 100).toFixed(0)}%
          </div>
        )}
        {reasoning && (
          <Collapse
            size="small"
            ghost
            bordered={false}
            items={[
              {
                key: 'reasoning',
                label: (
                  <span style={{ fontSize: 11, color: 'var(--color-text-secondary)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <CaretRight size={10} /> 分析逻辑
                  </span>
                ),
                children: (
                  <Paragraph style={{ fontSize: 11, lineHeight: 1.7, color: 'var(--color-text-secondary)', marginBottom: 0, marginInlineStart: 14 }}>
                    {reasoning}
                  </Paragraph>
                ),
              },
            ]}
            style={{ marginTop: 6 }}
          />
        )}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, flexShrink: 0 }}>
        {showConfirm && (
          <Button
            type="primary"
            size="small"
            icon={<CheckCircle size={12} />}
            onClick={() => onConfirm(signalId!)}
            style={{ fontSize: 11, height: 24 }}
          >
            确认
          </Button>
        )}
        <span
          style={{
            fontSize: 10,
            color: 'var(--color-text-disabled)',
            fontFamily: 'var(--font-mono)',
            whiteSpace: 'nowrap',
          }}
        >
          {time}
        </span>
      </div>
    </div>
  )
}
