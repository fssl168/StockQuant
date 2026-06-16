import { Table, Card, Tag } from 'antd'

interface DataLogTableProps {
  logs: Array<{
    key: string
    time: string
    symbol: string
    action: string
    status: string
    records: number
  }>
}

export default function DataLogTable({ logs }: DataLogTableProps) {
  return (
    <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>采集日志</span>} styles={{ body: { padding: '0' } }}>
      <Table
        dataSource={logs}
        columns={[
          { title: '时间', dataIndex: 'time', key: 'time', width: 160 },
          { title: '操作', dataIndex: 'action', key: 'action', width: 100, render: (s: string) => <span style={{ fontFamily: 'var(--font-mono)' }}>{s}</span> },
          { title: '标的', dataIndex: 'symbol', key: 'symbol', width: 120, render: (s: string) => <span style={{ fontFamily: 'var(--font-mono)' }}>{s}</span> },
          { title: '状态', dataIndex: 'status', key: 'status', width: 80, render: (s: string) => (
            <Tag color={s === 'success' ? 'green' : s === 'warning' ? 'orange' : 'red'}>
              {s === 'success' ? '成功' : s === 'warning' ? '警告' : '失败'}
            </Tag>
          )},
          { title: '记录数', dataIndex: 'records', key: 'records', width: 80, render: (v: number) => v.toLocaleString() },
        ]}
        rowKey="key"
        pagination={false}
        size="small"
      />
    </Card>
  )
}
