import { useEffect, useState } from 'react'
import { Table, Button, Input, Card, Typography, Space, Modal, Tooltip } from 'antd'
import { Plus, Code, Trash } from '@phosphor-icons/react'
import { useStrategyStore } from '@/stores/strategyStore'
import StrategyEditor from '@/components/Strategy/StrategyEditor'
import PreviewPanel from '@/components/Strategy/PreviewPanel'

const { Title, Text } = Typography

const DEFAULT_TEMPLATES = [
  { name: 'Dual MA Crossover', code: `from stockquant.strategy import BaseStrategy
from stockquant.indicators import EMA

class DualMACrossover(BaseStrategy):
    name = "Dual MA Crossover"
    parameters = {"fast": 5, "slow": 20, "position_size": 0.1}

    def on_start(self):
        self.ma_fast = EMA(self.data, period=self.parameters["fast"])
        self.ma_slow = EMA(self.data, period=self.parameters["slow"])

    def on_bar(self):
        if self.ma_fast[0] > self.ma_slow[0] and self.ma_fast[-1] <= self.ma_slow[-1]:
            self.order_market(self.data.close[0], 100)
        elif self.ma_fast[0] < self.ma_slow[0] and self.ma_fast[-1] >= self.ma_slow[-1]:
            self.close_all()` },
  { name: 'RSI Reversal', code: `from stockquant.strategy import BaseStrategy
from stockquant.indicators import RSI

class RSIReversal(BaseStrategy):
    name = "RSI Reversal"
    parameters = {"period": 14, "oversold": 30, "overbought": 70, "position_size": 0.2}

    def on_start(self):
        self.rsi = RSI(self.data, period=self.parameters["period"])

    def on_bar(self):
        if self.rsi[0] < self.parameters["oversold"]:
            self.order_market(self.data.close[0], 100)
        elif self.rsi[0] > self.parameters["overbought"]:
            self.close_all()` },
  { name: 'MACD Divergence', code: `from stockquant.strategy import BaseStrategy
from stockquant.indicators import MACD

class MACDDivergence(BaseStrategy):
    name = "MACD Divergence"
    parameters = {"fast": 12, "slow": 26, "signal": 9}

    def on_start(self):
        self.macd = MACD(self.data, fast=12, slow=26, signal=9)

    def on_bar(self):
        if self.macd.historical[-1] > 0 and self.macd.signal[-1] < 0:
            self.order_market(self.data.close[0], 100)
        elif self.macd.historical[-1] < 0:
            self.close_all()` },
]

export default function Strategy() {
  const { strategies, loading, fetchStrategies, createStrategy, deleteStrategy } = useStrategyStore()
  const [editorCode, setEditorCode] = useState('')
  const [strategyName, setStrategyName] = useState('')
  const [currentStrategyId, setCurrentStrategyId] = useState<string | null>(null)
  const [previewCode, setPreviewCode] = useState<string | null>(null)
  const [templateModal, setTemplateModal] = useState(false)

  useEffect(() => { fetchStrategies() }, [fetchStrategies])

  const handleCreate = () => {
    setStrategyName('')
    setEditorCode('')
    setCurrentStrategyId(null)
    setPreviewCode(null)
  }

  const handleSave = async () => {
    if (!strategyName.trim() || !editorCode.trim()) return
    try {
      if (currentStrategyId) {
        const { updateStrategy } = useStrategyStore.getState()
        await updateStrategy(currentStrategyId, { name: strategyName, code: editorCode })
      } else {
        await createStrategy({
          name: strategyName,
          code: editorCode,
          description: '',
          parameters: {},
        })
      }
      setEditorCode('')
      setStrategyName('')
      setCurrentStrategyId(null)
      setPreviewCode(null)
    } catch { /* ignore */ }
  }

  const handleTemplate = (code: string) => {
    setEditorCode(code)
    setTemplateModal(false)
  }

  return (
    <div style={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
        <div>
          <Title level={4} style={{ margin: 0, fontWeight: 600, fontSize: 16 }}>策略管理</Title>
          <Text type="secondary" style={{ fontSize: 12 }}>编写、编辑和管理交易策略</Text>
        </div>
        <Space>
          <Button icon={<Plus size={16} />} onClick={handleCreate}>新建策略</Button>
          <Button icon={<Code size={16} />} onClick={() => setTemplateModal(true)}>模板库</Button>
        </Space>
      </div>

      {/* Main content: left editor (70%) + right list (30%) */}
      <div style={{ display: 'flex', gap: 12, flex: 1, minHeight: 0 }}>
        {/* Left: Strategy Editor (70%) */}
        <div style={{ flex: 7, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Strategy name input row */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center', flexShrink: 0 }}>
            <Input
              value={strategyName}
              onChange={(e) => setStrategyName(e.target.value)}
              placeholder="策略名称"
              size="small"
              style={{ maxWidth: 220 }}
            />
            <div style={{ flex: 1 }} />
            <Tooltip title="预览代码">
              <Button size="small" onClick={() => setPreviewCode(editorCode || null)}>预览</Button>
            </Tooltip>
          </div>

          <StrategyEditor
            code={editorCode}
            onChange={setEditorCode}
            onSave={handleSave}
            saving={false}
          />

          <PreviewPanel code={previewCode} />
        </div>

        {/* Right: Strategy List (30%) */}
        <Card
          size="small"
          title={
            <span style={{ fontSize: 12, fontWeight: 600 }}>
              策略列表 ({strategies.length})
            </span>
          }
          style={{ flex: 3, minWidth: 280, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
          styles={{ body: { padding: '0', display: 'flex', flexDirection: 'column', flex: 1, overflow: 'auto' } }}
        >
          <Table
            dataSource={strategies}
            rowKey="id"
            pagination={false}
            size="small"
            loading={loading}
            columns={[
              { title: '名称', dataIndex: 'name', key: 'name', width: 100, ellipsis: true, render: (s: string) => (
                <a onClick={() => { setEditorCode(strategies.find((st) => st.name === s)?.code ?? ''); setStrategyName(s); setCurrentStrategyId(strategies.find((st) => st.name === s)?.id ?? null); setPreviewCode(null) }}>
                  <Text strong style={{ fontSize: 12 }}>{s}</Text>
                </a>
              ) },
              { title: '时间', dataIndex: 'created_at', key: 'time', width: 80, render: (d: string) => d ? new Date(d).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) : '-' },
              { title: '', key: 'action', width: 60, render: (_: any, r: any) => (
                <Space size={4}>
                  <Tooltip title="编辑">
                    <Button size="small" type="text" icon={<Code size={13} />} onClick={() => { setEditorCode(r.code); setStrategyName(r.name); setCurrentStrategyId(r.id); setPreviewCode(null) }} />
                  </Tooltip>
                  <Tooltip title="删除">
                    <Button size="small" type="text" danger icon={<Trash size={13} />} onClick={() => deleteStrategy(r.id)} />
                  </Tooltip>
                </Space>
              )},
            ]}
          />
        </Card>
      </div>

      {/* Template modal */}
      <Modal title="策略模板库" open={templateModal} onCancel={() => setTemplateModal(false)} footer={null} width={560}>
        <Space direction="vertical" style={{ width: '100%' }} size={8}>
          {DEFAULT_TEMPLATES.map((t) => (
            <Card
              key={t.name}
              size="small"
              hoverable
              styles={{ body: { padding: '10px 14px' } }}
              onClick={() => handleTemplate(t.code)}
              style={{ cursor: 'pointer', border: '1px solid var(--color-border-default)' }}
            >
              <Space style={{ justifyContent: 'space-between' }}>
                <Text strong style={{ fontSize: 13 }}>{t.name}</Text>
                <Button size="small" icon={<Code size={14} />}>加载</Button>
              </Space>
            </Card>
          ))}
        </Space>
      </Modal>
    </div>
  )
}
