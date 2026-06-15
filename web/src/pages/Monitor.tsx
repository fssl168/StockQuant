import { useEffect, useRef, useState } from 'react'
import { Table, Button, Input, Card, Row, Col, Typography, Tag, Space, Switch, InputNumber } from 'antd'
import { Plus, Play, Stop, Trash, Sparkle } from '@phosphor-icons/react'
import { useMarketStore } from '@/stores/marketStore'
import { monitorApi } from '@/api/monitor'
import { useNotificationStore } from '@/stores/notificationStore'

const { Title, Text } = Typography

export default function Monitor() {
  const [running, setRunning] = useState(false)
  const symbols = useMarketStore((s) => s.symbols)
  const addSymbol = useMarketStore((s) => s.addSymbol)
  const removeSymbol = useMarketStore((s) => s.removeSymbol)
  const [newSymbol, setNewSymbol] = useState('')
  const notifications = useNotificationStore((s) => s.notifications)
  const [livePrices, setLivePrices] = useState<Record<string, { price: number; change: number }>>({})
  const priceTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    monitorApi.status()
      .then((r: any) => setRunning(r.running ?? false))
      .catch(() => {})
  }, [])

  // Mock real-time prices when scanning
  useEffect(() => {
    if (running) {
      const basePrices: Record<string, number> = {}
      symbols.forEach((s) => {
        basePrices[s] = s.includes('600519') ? 1720 : s.includes('000858') ? 148 : s.includes('601318') ? 47 : 30
      })
      setLivePrices(Object.fromEntries(Object.entries(basePrices).map(([k, v]) => [k, { price: v, change: 0 }])))

      priceTimer.current = setInterval(() => {
        setLivePrices((prev) => {
          const next = { ...prev }
          Object.keys(next).forEach((sym) => {
            const prevPrice = next[sym].price
            const changePercent = (Math.random() - 0.48) * 2
            const newPrice = prevPrice * (1 + changePercent / 100)
            next[sym] = { price: Number(newPrice.toFixed(2)), change: Number(changePercent.toFixed(2)) }
          })
          return next
        })

        // Random signal generation
        if (Math.random() < 0.15 && symbols.length > 0) {
          const sym = symbols[Math.floor(Math.random() * symbols.length)]
          const current = livePrices[sym]
          if (current) {
            useNotificationStore.getState().add({
              type: 'signal',
              title: `${sym} 价格异动`,
              message: `${sym} 当前价 ${current.price.toFixed(2)}，涨幅 ${current.change >= 0 ? '+' : ''}${current.change.toFixed(2)}%`,
              time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            })
          }
        }
      }, 3000)
    } else {
      if (priceTimer.current) { clearInterval(priceTimer.current); priceTimer.current = null }
    }
    return () => { if (priceTimer.current) { clearInterval(priceTimer.current); priceTimer.current = null } }
  }, [running, symbols])

  const handleStart = async () => {
    try {
      await monitorApi.start(symbols)
      setRunning(true)
    } catch { /* ignore */ }
  }

  const handleStop = async () => {
    try { await monitorApi.stop() } catch { /* ignore */ }
    setRunning(false)
  }

  const handleAdd = () => {
    if (newSymbol.trim()) { addSymbol(newSymbol.trim()); setNewSymbol('') }
  }

  const monitorColumns = [
    { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 120, render: (s: string) => (
      <Text style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{s}</Text>
    )},
    { title: '价格', key: 'price', width: 110, render: (_: unknown, r: { symbol: string }) => {
      const lp = livePrices[r.symbol]
      return lp ? (
        <Text style={{ fontFamily: 'var(--font-mono)', fontWeight: 500, color: lp.change >= 0 ? '#10b981' : '#ef4444' }}>
          {lp.price.toFixed(2)}
        </Text>
      ) : <Text type="secondary">-</Text>
    }},
    { title: '涨跌%', key: 'change', width: 100, render: (_: unknown, r: { symbol: string }) => {
      const lp = livePrices[r.symbol]
      return lp ? (
        <Tag color={lp.change >= 0 ? 'green' : 'red'} style={{ fontFamily: 'var(--font-mono)' }}>
          {lp.change >= 0 ? '+' : ''}{lp.change.toFixed(2)}%
        </Tag>
      ) : <Tag>-</Tag>
    }},
    { title: '状态', key: 'status', width: 100, render: () => (
      <Tag color={running ? 'green' : 'default'}>{running ? '扫描中' : '已停止'}</Tag>
    )},
    { title: '操作', key: 'action', render: (_: any, r: any) => (
      <Button danger size="small" icon={<Trash size={14} />} onClick={() => removeSymbol(r.symbol)} />
    )},
  ]

  return (
    <div style={{ maxWidth: 1200 }}>
      <Title level={4} style={{ marginBottom: 4, fontWeight: 600 }}>实时盯盘</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 20, fontSize: 12 }}>
        自选股管理与实时信号扫描
      </Text>

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={16}>
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>自选股列表</span>}>
            <Space style={{ marginBottom: 12 }} size={8}>
              <Input
                value={newSymbol}
                onChange={(e) => setNewSymbol(e.target.value)}
                onPressEnter={handleAdd}
                placeholder="输入股票代码 (e.g. sh600519)"
                style={{ maxWidth: 200 }}
              />
              <Button icon={<Plus size={16} />} onClick={handleAdd}>添加</Button>
            </Space>
            <Table
              dataSource={symbols.map((s) => ({ key: s, symbol: s }))}
              rowKey="symbol"
              columns={monitorColumns}
              pagination={false}
              size="small"
            />
          </Card>

          {/* Recent signals */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Sparkle size={14} weight="fill" style={{ color: 'var(--color-info)' }} /> 最近信号
          </span>} styles={{ body: { padding: '0' } }} style={{ marginTop: 12 }}>
            {notifications.length === 0 && (
              <div style={{ padding: 24, textAlign: 'center', color: 'var(--color-text-tertiary)', fontSize: 12 }}>暂无信号推送</div>
            )}
            {notifications.slice(0, 5).map((n) => (
              <div key={n.id} style={{
                padding: '10px 14px',
                borderBottom: '1px solid var(--color-bg-surface)',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <div>
                  <Text style={{ fontSize: 12, fontWeight: 500 }}>{n.title}</Text>
                  <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 1 }}>{n.message}</div>
                </div>
                <span style={{ fontSize: 10, color: 'var(--color-text-disabled)', fontFamily: 'var(--font-mono)' }}>{n.time}</span>
              </div>
            ))}
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>扫描控制</span>}>
            <div style={{ textAlign: 'center', padding: 24 }}>
              <div style={{
                width: 56, height: 56, borderRadius: '50%',
                background: running ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                margin: '0 auto 12px',
                border: `2px solid ${running ? '#10b981' : '#ef4444'}`,
              }}>
                <div style={{
                  width: 20, height: 20, borderRadius: '50%',
                  background: running ? '#10b981' : '#ef4444',
                  animation: running ? 'pulse 2s infinite' : 'none',
                }} />
              </div>
              <Text style={{ fontSize: 13, display: 'block', marginBottom: 12 }}>
                {running ? '扫描运行中' : '扫描已停止'}
              </Text>
              <Space direction="vertical" style={{ width: '100%' }} size={8}>
                {!running ? (
                  <Button type="primary" icon={<Play size={16} weight="fill" />} block onClick={handleStart}>
                    开始扫描
                  </Button>
                ) : (
                  <Button danger icon={<Stop size={16} weight="fill" />} block onClick={handleStop}>
                    停止扫描
                  </Button>
                )}
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {symbols.length} 只标的
                </Text>
              </Space>
            </div>
          </Card>

          {/* Quick brief */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>盘前简报</span>} styles={{ body: { padding: '12px' } }} style={{ marginTop: 12 }}>
            <Text type="secondary" style={{ fontSize: 12, lineHeight: 1.6 }}>
              今日关注: 白酒板块持续走强，茅台放量突破 1720 阻力位。关注板块轮动向。
            </Text>
          </Card>

          {/* Alert rules */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>告警规则</span>} style={{ marginTop: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }} size={10}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text style={{ fontSize: 12 }}>涨跌幅超限提醒</Text>
                <Switch size="small" defaultChecked />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <Text style={{ fontSize: 12 }}>阈值</Text>
                <InputNumber size="small" min={0.1} max={10} step={0.1} defaultValue={3} suffix="%" style={{ width: 80 }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text style={{ fontSize: 12 }}>成交量异常检测</Text>
                <Switch size="small" />
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      <style>{`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }`}</style>
    </div>
  )
}
