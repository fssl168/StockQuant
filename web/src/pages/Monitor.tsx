import { useEffect, useState } from 'react'
import { Table, Button, Tag, Input, Card, Row, Col, Alert } from 'antd'
import { PlusOutlined, PlayCircleOutlined, StopOutlined } from '@ant-design/icons'
import { useMarketStore } from '@/stores/marketStore'
import { monitorApi } from '@/api/monitor'
import { useNotificationStore } from '@/stores/notificationStore'
import ReactECharts from 'echarts-for-react'

export default function Monitor() {
  const [running, setRunning] = useState(false)
  const symbols = useMarketStore((s) => s.symbols)
  const addSymbol = useMarketStore((s) => s.addSymbol)
  const addNotification = useNotificationStore((s) => s.add)
  const [newSymbol, setNewSymbol] = useState('')

  useEffect(() => {
    monitorApi.status().then((r) => setRunning((r as { running: boolean }).running)).catch(() => {})
  }, [])

  const handleStart = async () => {
    try {
      await monitorApi.start(symbols)
      setRunning(true)
      addNotification({ type: 'info', title: '盯盘已启动', message: `监控 ${symbols.length} 只股票`, time: new Date().toLocaleTimeString() })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '启动失败'
      console.error(msg)
    }
  }

  const handleStop = async () => {
    try {
      await monitorApi.stop()
      setRunning(false)
    } catch {
      // ignore
    }
  }

  const handleAdd = () => {
    if (newSymbol.trim()) {
      addSymbol(newSymbol.trim())
      setNewSymbol('')
    }
  }

  const columns = [
    { title: '代码', dataIndex: 'symbol', key: 'symbol' },
    { title: '最新价', key: 'price', render: () => '—' },
    { title: '涨跌幅', key: 'change', render: () => <Tag>—</Tag> },
    { title: '状态', key: 'status', render: () => <Tag color={running ? 'green' : 'default'}>{running ? '监控中' : '已停止'}</Tag> },
  ]

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Card title="自选股">
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <Input value={newSymbol} onChange={(e) => setNewSymbol(e.target.value)} placeholder="输入股票代码" style={{ maxWidth: 200 }} />
              <Button icon={<PlusOutlined />} onClick={handleAdd}>添加</Button>
            </div>
            <Table dataSource={symbols.map((s) => ({ key: s, symbol: s }))} rowKey="symbol" pagination={false}
              columns={[
                { title: '代码', dataIndex: 'symbol', key: 'symbol' },
                { title: '操作', key: 'action', render: (_, r) => <Button danger size="small" onClick={() => useMarketStore.getState().removeSymbol(r.key)}>删除</Button> },
              ]}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="行情监控">
            <Table dataSource={symbols.map((s) => ({ symbol: s }))} rowKey="symbol" pagination={false} columns={columns} />
            <div style={{ marginTop: 12 }}>
              {!running ? (
                <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleStart}>启动监控</Button>
              ) : (
                <Button danger icon={<StopOutlined />} onClick={handleStop}>停止监控</Button>
              )}
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="信号推送" style={{ marginTop: 16 }}>
        <Alert message="信号推送功能连接 MonitorAgent 后实时显示" type="info" showIcon />
      </Card>
    </div>
  )
}
