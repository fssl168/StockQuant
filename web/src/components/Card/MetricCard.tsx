import { Card, Statistic } from 'antd'
import type { ReactNode } from 'react'

interface MetricCardProps {
  title: string
  value: number | string
  suffix?: string
  prefix?: ReactNode
  precision?: number
  valueStyle?: React.CSSProperties
}

export default function MetricCard({ title, value, suffix, prefix, precision = 2, valueStyle }: MetricCardProps) {
  return (
    <Card size="small" style={{ background: 'var(--color-bg-elevated)', borderColor: 'var(--color-border-default)' }}>
      <Statistic
        title={title}
        value={value}
        suffix={suffix}
        prefix={prefix}
        precision={typeof value === 'number' ? precision : undefined}
        valueStyle={valueStyle}
      />
    </Card>
  )
}
