import { useCallback, useEffect, useRef, useState } from 'react'
import { Table, Button, Input, Card, Row, Col, Typography, Tag, Space, Switch, InputNumber, Modal, message } from 'antd'
import { Plus, Play, Stop, Trash, Sparkle, ChartBar } from '@phosphor-icons/react'
import { useMarketStore } from '@/stores/marketStore'
import { monitorApi } from '@/api/monitor'
import { dataApi } from '@/api/data'
import client from '@/api/client'
import { useNotificationStore } from '@/stores/notificationStore'
import { useWebSocket } from '@/hooks/useWebSocket'
import StockTicker from '@/components/Monitor/StockTicker'
import RealtimeKline from '@/components/Chart/RealtimeKline'
import SentimentPanel from '@/components/Monitor/SentimentPanel'
import SignalCard from '@/components/AI/SignalCard'

const { Title, Text, Paragraph } = Typography

interface Anomaly {
  symbol: string
  type: string
  description: string
  time: string
}

export default function Monitor() {
  const [running, setRunning] = useState(false)
  const symbols = useMarketStore((s) => s.symbols)
  const addSymbol = useMarketStore((s) => s.addSymbol)
  const removeSymbol = useMarketStore((s) => s.removeSymbol)
  const [newSymbol, setNewSymbol] = useState('')
  const notifications = useNotificationStore((s) => s.notifications)
  const [livePrices, setLivePrices] = useState<Record<string, { price: number; change: number }>>({})
  const priceTimer = useRef<ReturnType<typeof setInterval> | null>(null)
  const [alertRules, setAlertRules] = useState({
    priceChangeEnabled: true,
    priceChangeThreshold: 3,
    volumeEnabled: false,
    volumeMultiplier: 3,
  })

  // Task 2.5: 收盘总结
  const [closingSummary, setClosingSummary] = useState('')
  const [summaryLoading, setSummaryLoading] = useState(false)

  // Task 2.6: 异动检测
  const [anomalies, setAnomalies] = useState<Anomaly[]>([])
  const [scanLoading, setScanLoading] = useState(false)

  // Task 5: 盘前简报
  const [briefText, setBriefText] = useState('')
  const [briefLoading, setBriefLoading] = useState(false)

  // K线图弹窗
  const [klineSymbol, setKlineSymbol] = useState<string | null>(null)
  const [klineData, setKlineData] = useState<any[]>([])
  const [klineLoading, setKlineLoading] = useState(false)

  // Sentiment: selected symbol from watchlist
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)

  // F025: 决策模式
  const [decisionMode, setDecisionMode] = useState<string>('semi_auto')

  // F026: 动态风控
  const [riskControl, setRiskControl] = useState<{
    environment: 'calm' | 'volatile' | 'extreme'
    maxPositionPct: number
    maxDailyLossPct: number
    maxDrawdownPct: number
  }>({ environment: 'calm', maxPositionPct: 0.8, maxDailyLossPct: 0.03, maxDrawdownPct: 0.1 })

  // F026: 加载动态风控数据
  useEffect(() => {
    client.get('/api/monitor/risk-control')
      .then((res: any) => {
        const data = res.data ?? res
        if (data.environment) {
          setRiskControl({
            environment: data.environment,
            maxPositionPct: data.maxPositionPct ?? 0.8,
            maxDailyLossPct: data.maxDailyLossPct ?? 0.03,
            maxDrawdownPct: data.maxDrawdownPct ?? 0.1,
          })
        }
      })
      .catch((e: any) => console.warn('[Monitor] 获取风控参数失败:', e?.message))
  }, [])

  const { messages: wsMessages, connected: wsConnected } = useWebSocket(
    running ? '/ws/monitor' : null
  )
  // 处理 WS 消息 — Task 2.4: 实时行情 + alert通知 + 异动检测集成
  useEffect(() => {
    if (wsMessages.length === 0) return
    const latest = wsMessages[wsMessages.length - 1]
    if (latest.type === 'quote') {
      // Task 2.4: 使用真实行情数据更新 livePrices
      const newPrices: Record<string, { price: number; change: number }> = {}
      for (const [sym, quote] of Object.entries(latest.data as Record<string, { price: number; change: number }>)) {
        newPrices[sym] = quote
      }
      setLivePrices(newPrices)
    } else if (latest.type === 'alert') {
      const data = latest.data as { title?: string; message?: string; symbol?: string; type?: string; description?: string }
      // Task 2.4: 添加到通知 store
      useNotificationStore.getState().add({
        type: 'signal',
        title: data.title ?? 'AI 信号',
        message: data.message ?? '',
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      })
      // Task 2.6: 如果 alert 包含异动信息，添加到 anomalies 表格
      if (data.symbol && data.type) {
        const newAnomaly: Anomaly = {
          symbol: data.symbol,
          type: data.type,
          description: data.description ?? data.message ?? '',
          time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        }
        setAnomalies((prev) => [newAnomaly, ...prev])
      }
    }
  }, [wsMessages])

  // 自选股同步 — Task 7: 从后端加载 watchlist
  useEffect(() => {
    monitorApi.getWatchlist()
      .then((wl: string[]) => {
        if (wl.length > 0) {
          useMarketStore.getState().addWatchlist(wl)
        }
      })
      .catch((e: any) => console.warn('[Monitor] 获取自选股失败:', e?.message))
  }, [])

  // 加载监控状态
  useEffect(() => {
    monitorApi.status()
      .then((r: any) => setRunning(r.running ?? false))
      .catch((e: any) => console.warn('[Monitor] 获取监控状态失败:', e?.message))
  }, [])

  // Task 5: 加载盘前简报
  useEffect(() => {
    setBriefLoading(true)
    monitorApi.brief()
      .then((res: string) => setBriefText(res))
      .catch(() => setBriefText('暂无盘前简报'))
      .finally(() => setBriefLoading(false))
  }, [])

  // WS 未连接时不模拟行情数据，仅显示提示
  // 实时行情完全依赖 WebSocket /ws/monitor 推送
  useEffect(() => {
    if (!running || wsConnected) {
      if (priceTimer.current) { clearInterval(priceTimer.current); priceTimer.current = null }
    }
    return () => { if (priceTimer.current) { clearInterval(priceTimer.current); priceTimer.current = null } }
  }, [running, wsConnected])

  const handleStart = async () => {
    try {
      await monitorApi.start(symbols)
      setRunning(true)
    } catch (e: any) { console.warn('[Monitor] 启动监控失败:', e?.message) }
  }

  const handleStop = async () => {
    try { await monitorApi.stop() } catch (e: any) { console.warn('[Monitor] 停止监控失败:', e?.message) }
    setRunning(false)
  }

  const handleAdd = () => {
    if (newSymbol.trim()) {
      const newSym = newSymbol.trim()
      addSymbol(newSym)
      monitorApi.updateWatchlist([...symbols, newSym]).catch((e: any) => console.warn('[Monitor] 更新自选股失败:', e?.message))
      setNewSymbol('')
    }
  }

  const handleRemove = (symbol: string) => {
    removeSymbol(symbol)
    monitorApi.removeFromWatchlist([symbol]).catch((e: any) => console.warn('[Monitor] 删除自选股失败:', e?.message))
  }

  // Task 2.5: 获取收盘总结
  const handleFetchSummary = useCallback(async () => {
    setSummaryLoading(true)
    try {
      const res = await monitorApi.summary() as any
      setClosingSummary(res ?? '暂无总结数据')
    } catch {
      setClosingSummary('获取收盘总结失败，请稍后重试')
    } finally {
      setSummaryLoading(false)
    }
  }, [])

  // Task 2.6: 扫描异动
  const handleScanAnomalies = useCallback(async () => {
    if (symbols.length === 0) return
    setScanLoading(true)
    try {
      const results = await Promise.allSettled(
        symbols.map((sym) => monitorApi.scan(sym))
      )
      const newAnomalies: Anomaly[] = []
      results.forEach((r) => {
        if (r.status === 'fulfilled') {
          const data = r.value as any
          // 后端返回的是数组，兼容 { anomalies: [...] } 格式
          const anomalies = Array.isArray(data) ? data : (data.anomalies ?? [])
          for (const a of anomalies) {
            if (typeof a === 'object' && a !== null) {
              const newAnomaly: Anomaly = {
                symbol: (a as any).symbol ?? '',
                type: (a as any).type ?? '',
                description: (a as any).description ?? (a as any).message ?? '',
                time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
              }
              newAnomalies.push(newAnomaly)
            }
          }
        }
      })
      setAnomalies((prev) => [...newAnomalies, ...prev])
    } catch (e: any) {
      console.warn('[Monitor] 扫描异动失败:', e?.message)
    } finally {
      setScanLoading(false)
    }
  }, [symbols])

  // Signal confirm
  const handleConfirmSignal = async (signalId: string) => {
    try {
      await client.put(`/api/monitor/signal/${signalId}/confirm`)
      message.success('信号已确认')
      // Remove confirmed signal from notifications
      useNotificationStore.getState().deleteNotification(signalId)
    } catch {
      message.error('确认失败')
    }
  }

  // K线图弹窗
  const handleShowKline = async (symbol: string) => {
    setKlineSymbol(symbol)
    setKlineLoading(true)
    setKlineData([])
    try {
      const end = new Date().toISOString().slice(0, 10)
      const start = new Date(Date.now() - 90 * 86400000).toISOString().slice(0, 10)
      const result = await dataApi.fetchKline(symbol, 'alphafeed', start, end)
      const rawData = result?.data ?? result
      setKlineData(Array.isArray(rawData) ? rawData : [])
    } catch {
      setKlineData([])
    } finally {
      setKlineLoading(false)
    }
  }

  const monitorColumns = [
    { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 120, render: (s: string) => (
      <Text style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{s}</Text>
    )},
    { title: '价格', key: 'price', width: 110, render: (_: unknown, r: { symbol: string }) => {
      const lp = livePrices[r.symbol]
      return lp ? (
        <Text style={{ fontFamily: 'var(--font-mono)', fontWeight: 500, color: lp.change >= 0 ? 'var(--color-success)' : 'var(--color-danger)' }}>
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
      <Space size={4}>
        <Button size="small" icon={<ChartBar size={14} />} onClick={() => handleShowKline(r.symbol)}>K线</Button>
        <Button danger size="small" icon={<Trash size={14} />} onClick={() => handleRemove(r.symbol)} />
      </Space>
    )},
  ]

  // Task 2.6: 异动检测表格列
  const anomalyColumns = [
    { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 120, render: (s: string) => (
      <Text style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{s}</Text>
    )},
    { title: '类型', dataIndex: 'type', key: 'type', width: 120, render: (t: string) => {
      const colorMap: Record<string, string> = {
        '放量突破': 'green',
        '涨停': 'red',
        '跌停': 'volcano',
        '异动成交量': 'orange',
      }
      return <Tag color={colorMap[t] ?? 'blue'}>{t}</Tag>
    }},
    { title: '描述', dataIndex: 'description', key: 'description' },
    { title: '时间', dataIndex: 'time', key: 'time', width: 100, render: (t: string) => (
      <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{t}</Text>
    )},
  ]

  return (
    <div style={{ maxWidth: 1200 }}>
      <Title level={4} style={{ marginBottom: 4, fontWeight: 600 }}>实时盯盘</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 20, fontSize: 12 }}>
        自选股管理与实时信号扫描
      </Text>

      {/* Real-time ticker strip */}
      {running && symbols.length > 0 && (
        <div style={{ display: 'flex', gap: 8, overflowX: 'auto', marginBottom: 16, paddingBottom: 4 }}>
          {symbols.map((sym) => {
            const lp = livePrices[sym]
            return (
              <StockTicker
                key={sym}
                symbol={sym}
                name={sym.includes('600519') ? '贵州茅台' : sym.includes('000858') ? '五粮液' : sym.includes('601318') ? '中国平安' : sym}
                price={lp?.price ?? 0}
                change={lp?.change ?? 0}
              />
            )
          })}
        </div>
      )}

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
              onRow={(record) => ({
                onClick: () => setSelectedSymbol(record.symbol),
                style: { cursor: 'pointer', background: record.symbol === selectedSymbol ? 'var(--color-brand-subtle)' : 'transparent' }
              })}
            />
          </Card>

          {/* Task 2.6: 异动检测 */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>异动检测</span>} style={{ marginTop: 12 }}>
            <Button
              type="primary"
              size="small"
              loading={scanLoading}
              onClick={handleScanAnomalies}
              style={{ marginBottom: 12 }}
            >
              扫描异动
            </Button>
            <Table
              dataSource={anomalies.map((a, i) => ({ ...a, key: `${a.symbol}-${a.time}-${i}` }))}
              columns={anomalyColumns}
              pagination={false}
              size="small"
              locale={{ emptyText: '暂无异动数据' }}
            />
          </Card>

          {/* Recent signals */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Sparkle size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> 最近信号
          </span>} styles={{ body: { padding: 0 } }} style={{ marginTop: 12 }}>
            {notifications.length === 0 && (
              <div style={{ padding: 24, textAlign: 'center', color: 'var(--color-text-tertiary)', fontSize: 12 }}>暂无信号推送</div>
            )}
            {notifications.slice(0, 5).map((n) => {
              const signalType: 'BUY' | 'SELL' | 'NEUTRAL' =
                n.title.includes('买入') ? 'BUY' : n.title.includes('卖出') ? 'SELL' : 'NEUTRAL'
              return (
                <SignalCard
                  key={n.id}
                  type={signalType}
                  title={n.title}
                  message={n.message}
                  time={n.time}
                  confidence={undefined}
                  reasoning={undefined}
                  signalId={n.id}
                  onConfirm={handleConfirmSignal}
                />
              )
            })}
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
                border: `2px solid ${running ? 'var(--color-success)' : 'var(--color-danger)'}`,
              }}>
                <div style={{
                  width: 20, height: 20, borderRadius: '50%',
                  background: running ? 'var(--color-success)' : 'var(--color-danger)',
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

          {/* F025: 决策模式切换 */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>决策模式</span>} style={{ marginTop: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }} size={6}>
              <Button.Group style={{ width: '100%' }}>
                <Button
                  type={decisionMode === 'auto' ? 'primary' : 'default'}
                  onClick={() => setDecisionMode('auto')}
                  block
                  style={{ fontWeight: decisionMode === 'auto' ? 700 : 400 }}
                >
                  🤖 全自动
                </Button>
                <Button
                  type={decisionMode === 'semi_auto' ? 'primary' : 'default'}
                  onClick={() => setDecisionMode('semi_auto')}
                  block
                  style={{ fontWeight: decisionMode === 'semi_auto' ? 700 : 400 }}
                >
                  ⚙️ 半自动
                </Button>
                <Button
                  type={decisionMode === 'read_only' ? 'primary' : 'default'}
                  onClick={() => setDecisionMode('read_only')}
                  block
                  style={{ fontWeight: decisionMode === 'read_only' ? 700 : 400 }}
                >
                  👁 只读
                </Button>
              </Button.Group>
              <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
                {decisionMode === 'auto' ? 'AI 自动执行交易信号' :
                 decisionMode === 'semi_auto' ? 'AI 建议，人工确认执行' :
                 'AI 仅提供建议，不执行交易'}
              </Text>
            </Space>
          </Card>

          {/* F026: 动态风控 */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>动态风控</span>} style={{ marginTop: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }} size={10}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text style={{ fontSize: 12 }}>市场环境</Text>
                <Tag color={riskControl.environment === 'calm' ? 'green' : riskControl.environment === 'volatile' ? 'orange' : 'red'}>
                  {riskControl.environment === 'calm' ? '平稳' : riskControl.environment === 'volatile' ? '波动' : '极端'}
                </Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text style={{ fontSize: 12 }}>风险等级</Text>
                <Tag color={riskControl.environment === 'calm' ? 'green' : riskControl.environment === 'volatile' ? 'orange' : 'red'}>
                  {riskControl.environment === 'calm' ? '低风险' : riskControl.environment === 'volatile' ? '中风险' : '高风险'}
                </Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text style={{ fontSize: 12 }}>最大持仓比例</Text>
                <Text style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>{(riskControl.maxPositionPct * 100).toFixed(0)}%</Text>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text style={{ fontSize: 12 }}>最大日损失</Text>
                <Text style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>{(riskControl.maxDailyLossPct * 100).toFixed(1)}%</Text>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text style={{ fontSize: 12 }}>最大回撤</Text>
                <Text style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>{(riskControl.maxDrawdownPct * 100).toFixed(1)}%</Text>
              </div>
            </Space>
          </Card>

          {/* Quick brief */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>盘前简报</span>} style={{ marginBottom: 12 }}>
            {briefLoading ? (
              <div style={{ textAlign: 'center', padding: 20 }}>加载中...</div>
            ) : (
              <Text style={{ fontSize: 12, color: 'var(--color-text-secondary)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                {briefText || '暂无盘前简报'}
              </Text>
            )}
          </Card>

          {/* Task 2.5: 收盘总结 */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>收盘总结</span>} styles={{ body: { padding: '12px' } }} style={{ marginTop: 12 }}>
            <Button
              type="primary"
              size="small"
              loading={summaryLoading}
              onClick={handleFetchSummary}
              style={{ marginBottom: closingSummary ? 12 : 0 }}
            >
              获取收盘总结
            </Button>
            {closingSummary && (
              <Paragraph style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--color-text-secondary)', marginBottom: 0 }}>
                {closingSummary}
              </Paragraph>
            )}
          </Card>

          {/* Alert rules */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>告警规则</span>} style={{ marginTop: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }} size={10}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text style={{ fontSize: 12 }}>涨跌幅超限提醒</Text>
                <Switch size="small" checked={alertRules.priceChangeEnabled} onChange={(v) => setAlertRules(prev => ({ ...prev, priceChangeEnabled: v }))} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <Text style={{ fontSize: 12 }}>阈值</Text>
                <InputNumber size="small" min={0.1} max={10} step={0.1} value={alertRules.priceChangeThreshold} onChange={(v) => setAlertRules(prev => ({ ...prev, priceChangeThreshold: v ?? 3 }))} suffix="%" style={{ width: 80 }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text style={{ fontSize: 12 }}>成交量异常检测</Text>
                <Switch size="small" checked={alertRules.volumeEnabled} onChange={(v) => setAlertRules(prev => ({ ...prev, volumeEnabled: v }))} />
              </div>
            </Space>
          </Card>

          {/* Sentiment monitoring */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>情绪监控</span>} style={{ marginTop: 12 }}>
            <SentimentPanel symbol={selectedSymbol} height={250} />
          </Card>
        </Col>
      </Row>

      <Modal
        title={`${klineSymbol} K线图`}
        open={!!klineSymbol}
        onCancel={() => setKlineSymbol(null)}
        footer={null}
        width={800}
        destroyOnClose
      >
        {klineLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>加载中...</div>
        ) : klineData.length > 0 ? (
          <RealtimeKline symbol={klineSymbol!} data={klineData} height={400} />
        ) : (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--color-text-tertiary)' }}>暂无K线数据</div>
        )}
      </Modal>

      <style>{`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }`}</style>
    </div>
  )
}
