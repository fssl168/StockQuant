import { Card, Button, Typography, Divider, Tag, List } from 'antd'
import { Sparkle, Warning, Lightbulb, Atom } from '@phosphor-icons/react'

const { Text, Paragraph } = Typography

export interface StructuredInsight {
  summary: string
  overfitRisk: string | null
  alphaDecomposition: string | null
  suggestions: string[]
}

interface InsightCardProps {
  insight: string | StructuredInsight | null
  loading?: boolean
  onGenerate?: () => void
}

/** 判断 insight 是否为结构化对象 */
function isStructured(v: unknown): v is StructuredInsight {
  return typeof v === 'object' && v !== null && 'summary' in (v as StructuredInsight)
}

export default function InsightCard({ insight, loading, onGenerate }: InsightCardProps) {
  // 结构化渲染
  if (isStructured(insight)) {
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
        {/* 策略概述 */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4, fontWeight: 600 }}>
            策略概述
          </div>
          <Paragraph style={{ fontSize: 13, lineHeight: 1.7, margin: 0, color: 'var(--color-text-secondary)' }}>
            {insight.summary}
          </Paragraph>
        </div>

        {/* 过拟合风险 */}
        {insight.overfitRisk && (
          <>
            <Divider style={{ margin: '10px 0' }} />
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
                <Warning size={12} style={{ color: '#f59e0b' }} /> 过拟合风险
              </div>
              <Paragraph style={{ fontSize: 13, lineHeight: 1.7, margin: 0, color: insight.overfitRisk.includes('低') ? '#10b981' : '#f59e0b' }}>
                {insight.overfitRisk}
              </Paragraph>
            </div>
          </>
        )}

        {/* Alpha 来源分解 */}
        {insight.alphaDecomposition && (
          <>
            <Divider style={{ margin: '10px 0' }} />
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
                <Atom size={12} style={{ color: 'var(--color-brand-primary)' }} /> Alpha 来源分解
              </div>
              <Paragraph style={{ fontSize: 13, lineHeight: 1.7, margin: 0, color: 'var(--color-text-secondary)' }}>
                {insight.alphaDecomposition}
              </Paragraph>
            </div>
          </>
        )}

        {/* 改进建议 */}
        {insight.suggestions && insight.suggestions.length > 0 && (
          <>
            <Divider style={{ margin: '10px 0' }} />
            <div>
              <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
                <Lightbulb size={12} style={{ color: '#10b981' }} /> 改进建议
              </div>
              <List
                size="small"
                split={false}
                dataSource={insight.suggestions}
                renderItem={(item, idx) => (
                  <List.Item style={{ padding: '4px 0', border: 'none' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      <Tag color="blue" style={{ margin: 0, fontSize: 10, lineHeight: '16px', minWidth: 22, textAlign: 'center' }}>
                        {idx + 1}
                      </Tag>
                      <Text style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--color-text-secondary)' }}>{item}</Text>
                    </div>
                  </List.Item>
                )}
              />
            </div>
          </>
        )}
      </Card>
    )
  }

  // 兼容旧版纯文本格式
  if (typeof insight === 'string' && insight) {
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
        <Text type="secondary" style={{ fontSize: 13, lineHeight: 1.7 }}>{insight}</Text>
      </Card>
    )
  }

  // 空状态
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
    </Card>
  )
}
