import { Card, Row, Col } from 'antd'
import { Database } from '@phosphor-icons/react'

interface CacheStatsProps {
  sizeMb: number
  hitRate: number
  symbolCount: number
  lastUpdate: string
}

export default function CacheStats({ sizeMb, hitRate, symbolCount, lastUpdate }: CacheStatsProps) {
  const items = [
    { label: '缓存大小', value: `${sizeMb.toFixed(1)} MB`, icon: <Database size={16} /> },
    { label: '命中率', value: `${(hitRate * 100).toFixed(0)}%`, icon: <Database size={16} /> },
    { label: '标的数', value: symbolCount, icon: <Database size={16} /> },
    { label: '最后更新', value: lastUpdate, icon: <Database size={16} /> },
  ]

  return (
    <Row gutter={[12, 12]}>
      {items.map((s) => (
        <Col xs={24} sm={12} md={6} key={s.label}>
          <Card size="small" styles={{ body: { padding: '10px 14px' } }}>
            <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</div>
            <div style={{ fontSize: 15, fontWeight: 600, fontFamily: 'var(--font-mono)', marginTop: 2, color: 'var(--color-text-primary)' }}>
              {s.value}
            </div>
          </Card>
        </Col>
      ))}
    </Row>
  )
}
