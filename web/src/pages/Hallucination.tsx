import { useEffect, useState } from 'react'
import { Table, Card, Typography, Tabs, Tag, Row, Col, Space, Select, Empty } from 'antd'
import { ShieldCheck } from '@phosphor-icons/react'

const { Text } = Typography

interface HallucinationRecord {
  id: string
  timestamp: string
  agent: string
  input_summary: string
  hallucination_type: string
  detection_method: string
  original_output: string
  corrected_output: string
  confidence: number
  user_feedback: string
}

interface AnalysisResult {
  type_distribution: Record<string, number>
  high_frequency_triggers: { word: string; count: number }[]
  agent_differences: Record<string, { count: number; top_types: Record<string, number>; avg_confidence: number }>
  time_trend: Record<string, number>
  total_count: number
}

type HType = 'fabricated_data' | 'unsupported_claim' | 'temporal_error' | 'source_confusion' | 'logical_fallacy' | 'omission'

const typeLabels: Record<HType, string> = {
  fabricated_data: '虚构数据',
  unsupported_claim: '无支撑断言',
  temporal_error: '时间错误',
  source_confusion: '来源混淆',
  logical_fallacy: '逻辑谬误',
  omission: '信息遗漏',
}

const typeColors: Record<HType, string> = {
  fabricated_data: 'red',
  unsupported_claim: 'orange',
  temporal_error: 'blue',
  source_confusion: 'purple',
  logical_fallacy: 'magenta',
  omission: 'cyan',
}

export default function HallucinationPage() {
  const [records, setRecords] = useState<HallucinationRecord[]>([])
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [agentTypeFilter, setAgentTypeFilter] = useState<string>('')
  const [typeFilter, setTypeFilter] = useState<string>('')
  const [loading, setLoading] = useState(false)

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [recs, analysisData] = await Promise.all([
        fetch(`/api/hallucination/records?agent=${agentTypeFilter}&hallucination_type=${typeFilter}`).then(r => r.json()).catch(() => []),
        fetch('/api/hallucination/analysis').then(r => r.json()).catch(() => null),
      ])
      setRecords(Array.isArray(recs) ? recs : [])
      setAnalysis(analysisData)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAll() }, [agentTypeFilter, typeFilter])

  const recordColumns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 160,
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: 'Agent',
      dataIndex: 'agent',
      key: 'agent',
      width: 100,
    },
    {
      title: '类型',
      dataIndex: 'hallucination_type',
      key: 'hallucination_type',
      width: 120,
      render: (t: HType) => <Tag color={typeColors[t]}>{typeLabels[t] || t}</Tag>,
    },
    {
      title: '输入摘要',
      dataIndex: 'input_summary',
      key: 'input_summary',
      ellipsis: true,
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 80,
      render: (v: number) => <Text style={{ color: v < 0.5 ? 'red' : 'green' }}>{v.toFixed(2)}</Text>,
    },
  ]

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ShieldCheck size={20} weight="fill" />
          <Text strong style={{ fontSize: 16 }}>反幻觉管理</Text>
        </div>
        <Space>
          <Select placeholder="Agent" allowClear style={{ width: 120 }} value={agentTypeFilter} onChange={setAgentTypeFilter} />
          <Select placeholder="类型" allowClear style={{ width: 140 }} value={typeFilter} onChange={setTypeFilter} options={Object.entries(typeLabels).map(([k, v]) => ({ value: k, label: v }))} />
        </Space>
      </div>

      <Tabs defaultActiveKey="records" items={[
        {
          key: 'records',
          label: '幻觉记录',
          children: (
            <Card size="small">
              <Table
                dataSource={records}
                columns={recordColumns}
                rowKey={(r) => r.id}
                size="small"
                loading={loading}
                scroll={{ x: 800 }}
              />
            </Card>
          ),
        },
        {
          key: 'analysis',
          label: '模式分析',
          children: analysis ? (
            <Row gutter={16}>
              <Col span={12}>
                <Card title="类型分布" size="small">
                  {Object.entries(analysis.type_distribution).map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                      <Tag color={typeColors[k as HType] || 'default'}>{typeLabels[k as HType] || k}</Tag>
                      <Text strong>{v}</Text>
                    </div>
                  ))}
                </Card>
              </Col>
              <Col span={12}>
                <Card title="高频触发词" size="small">
                  {analysis.high_frequency_triggers.slice(0, 10).map((t, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text>{t.word}</Text>
                      <Text type="secondary">{t.count}次</Text>
                    </div>
                  ))}
                </Card>
              </Col>
              <Col span={24}>
                <Card title="Agent 差异" size="small">
                  <Table
                    dataSource={Object.entries(analysis.agent_differences).map(([name, data]) => ({ name, ...data }))}
                    columns={[
                      { title: 'Agent', dataIndex: 'name', key: 'name' },
                      { title: '频次', dataIndex: 'count', key: 'count', width: 60 },
                      { title: '平均置信度', dataIndex: 'avg_confidence', key: 'avg_confidence', width: 100, render: (v: number) => v.toFixed(2) },
                      { title: '主要类型', dataIndex: 'top_types', key: 'top_types', render: (v: Record<string, number>) => Object.keys(v).map(k => <Tag key={k}>{k}</Tag>) },
                    ]}
                    rowKey={(r) => r.name}
                    size="small"
                    pagination={false}
                  />
                </Card>
              </Col>
            </Row>
          ) : (
            <Empty description="暂无分析数据" />
          ),
        },
        {
          key: 'suggestions',
          label: '优化建议',
          children: (
            <Card size="small">
              <Typography>
                <Typography.Title level={5}>使用说明</Typography.Title>
                <Typography.Paragraph>
                  建议持续监控幻觉记录，当某类幻觉频次≥3 时自动生成优化建议。
                </Typography.Paragraph>
              </Typography>
            </Card>
          ),
        },
      ]} />
    </div>
  )
}
