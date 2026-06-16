import type { DataSourceConfig } from '@/types'
import { Table, Button, Card, Space, Tag } from 'antd'
import { Download } from '@phosphor-icons/react'

interface DataSourceFormProps {
  sources: DataSourceConfig[]
  onToggle?: (provider: string, enabled: boolean) => void
}

export default function DataSourceForm({ sources, onToggle: _onToggle }: DataSourceFormProps) {
  const columns = [
    { title: '数据源', dataIndex: 'provider', key: 'provider', width: 120, render: (p: string) => <strong>{p}</strong> },
    { title: '状态', key: 'status', width: 80, render: () => <Tag color="green">活跃</Tag> },
    { title: '最后更新', key: 'last', width: 160, render: () => '2026-06-15 15:00' },
    { title: '记录数', key: 'records', width: 100, render: () => '1,234,567' },
    { title: '操作', key: 'action', width: 120, render: () => (
      <Space>
        <Button size="small" icon={<Download size={14} />}>下载</Button>
      </Space>
    )},
  ]

  const fallbackSources: DataSourceConfig[] = [
    { provider: 'BaoStock', enabled: true },
    { provider: 'AkShare', enabled: true },
    { provider: 'CSV 本地', enabled: true },
  ]

  return (
    <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>数据源配置</span>} styles={{ body: { padding: '0' } }} style={{ marginBottom: 12 }}>
      <Table
        dataSource={sources.length > 0 ? sources : fallbackSources}
        columns={columns}
        rowKey="provider"
        pagination={false}
        size="small"
      />
    </Card>
  )
}
