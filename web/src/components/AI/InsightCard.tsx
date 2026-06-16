import { Card, Button, Typography } from 'antd'
import { Sparkle } from '@phosphor-icons/react'

const { Text } = Typography

interface InsightCardProps {
  insight: string | null
  loading?: boolean
  onGenerate?: () => void
}

export default function InsightCard({ insight, loading, onGenerate }: InsightCardProps) {
  return (
    <Card
      size="small"
      title={
        <span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Sparkle size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> AI 解读
        </span>
      }
      styles={{ body: { padding: '16px' } }}
    >
      {insight ? (
        <Text type="secondary" style={{ fontSize: 13, lineHeight: 1.7 }}>{insight}</Text>
      ) : (
        <div style={{ textAlign: 'center', padding: '8px 0' }}>
          <Button
            type="primary"
            size="small"
            icon={<Sparkle size={14} />}
            loading={loading}
            onClick={onGenerate}
          >
            生成 AI 解读
          </Button>
        </div>
      )}
    </Card>
  )
}
