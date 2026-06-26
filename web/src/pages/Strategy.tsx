import { useEffect, useState } from 'react'
import { Table, Button, Input, Card, Typography, Space, Modal, Tooltip, message, Select, InputNumber, Popconfirm } from 'antd'
import { Plus, Code, Trash, Sparkle } from '@phosphor-icons/react'
import client from '@/api/client'
import { useStrategyStore } from '@/stores/strategyStore'
import StrategyEditor from '@/components/Strategy/StrategyEditor'
import PreviewPanel from '@/components/Strategy/PreviewPanel'

const { Title, Text, Paragraph } = Typography

const SIZER_OPTIONS = [
  { value: 'fixed_fraction', label: '固定比例' },
  { value: 'kelly', label: 'Kelly公式' },
  { value: 'atr', label: 'ATR仓位' },
  { value: 'volatility_target', label: '波动率目标' },
  { value: 'equal_weight', label: '等权重' },
] as const

type SizerType = typeof SIZER_OPTIONS[number]['value']

interface SizerConfig {
  type: SizerType
  fraction_pct: number
  atr_period: number
  atr_risk_coeff: number
  vol_target: number
}

const DEFAULT_SIZER_CONFIG: SizerConfig = {
  type: 'fixed_fraction',
  fraction_pct: 0.02,
  atr_period: 14,
  atr_risk_coeff: 0.02,
  vol_target: 0.15,
}

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
  { name: 'Bollinger Bounce', code: `from stockquant.strategy import BaseStrategy
from stockquant.indicators import BBANDS

class BollingerBounceStrategy(BaseStrategy):
    name = "Bollinger Bounce"
    parameters = {"period": 20, "std_dev": 2.0, "position_size": 0.1}

    def on_start(self):
        self.bb = BBANDS(self.data, period=self.parameters["period"], std_dev=self.parameters["std_dev"])

    def on_bar(self):
        if self.data.close[0] <= self.bb.lower[0]:
            self.order_market(self.data.close[0], 100)
        elif self.data.close[0] >= self.bb.upper[0]:
            self.close_all()` },
  { name: 'Dual Thrust', code: `from stockquant.strategy import BaseStrategy

class DualThrustStrategy(BaseStrategy):
    name = "Dual Thrust"
    parameters = {"lookback": 5, "k1": 0.5, "k2": 0.5, "position_size": 0.1}

    def on_start(self):
        self.range = 0

    def on_bar(self):
        if self.range == 0:
            history = self.data.history[-self.parameters["lookback"]:]
            self.range = max(h.high for h in history) - min(h.low for h in history)
        if self.data.close[0] > self.parameters["k1"] * self.range:
            self.order_market(self.data.close[0], 100)
        elif self.data.close[0] < self.parameters["k2"] * self.range:
            self.close_all()` },
  { name: 'Mean Reversion', code: `from stockquant.strategy import BaseStrategy
from stockquant.indicators import SMA, STDDEV

class MeanReversionStrategy(BaseStrategy):
    name = "Mean Reversion"
    parameters = {"period": 20, "deviation": 2.0, "position_size": 0.1}

    def on_start(self):
        self.sma = SMA(self.data, period=self.parameters["period"])
        self.stddev = STDDEV(self.data, period=self.parameters["period"])

    def on_bar(self):
        upper = self.sma[0] + self.parameters["deviation"] * self.stddev[0]
        lower = self.sma[0] - self.parameters["deviation"] * self.stddev[0]
        if self.data.close[0] < lower:
            self.order_market(self.data.close[0], 100)
        elif self.data.close[0] > upper:
            self.close_all()` },
  { name: 'Momentum', code: `from stockquant.strategy import BaseStrategy
from stockquant.indicators import RSI

class MomentumStrategy(BaseStrategy):
    name = "Momentum"
    parameters = {"rsi_period": 14, "oversold": 30, "overbought": 70, "position_size": 0.1}

    def on_start(self):
        self.rsi = RSI(self.data, period=self.parameters["rsi_period"])

    def on_bar(self):
        if self.rsi[0] < self.parameters["oversold"]:
            self.order_market(self.data.close[0], 100)
        elif self.rsi[0] > self.parameters["overbought"]:
            self.close_all()` },
]

export default function Strategy() {
  const { strategies, loading, fetchStrategies, createStrategy, deleteStrategy } = useStrategyStore()
  const [editorCode, setEditorCode] = useState('')
  const [strategyName, setStrategyName] = useState('')
  const [currentStrategyId, setCurrentStrategyId] = useState<string | null>(null)
  const [previewCode, setPreviewCode] = useState<string | null>(null)
  const [templateModal, setTemplateModal] = useState(false)
  const [aiModal, setAiModal] = useState(false)
  const [aiDescription, setAiDescription] = useState('')
  const [aiGenerating, setAiGenerating] = useState(false)
  const [sizerConfig, setSizerConfig] = useState<SizerConfig>({ ...DEFAULT_SIZER_CONFIG })

  useEffect(() => { fetchStrategies() }, [fetchStrategies])

  const handleCreate = () => {
    setStrategyName('')
    setEditorCode('')
    setCurrentStrategyId(null)
    setPreviewCode(null)
    setSizerConfig({ ...DEFAULT_SIZER_CONFIG })
  }

  const handleSave = async () => {
    if (!strategyName.trim() || !editorCode.trim()) return
    const sizerParams: Record<string, unknown> = { type: sizerConfig.type }
    if (sizerConfig.type === 'fixed_fraction') {
      sizerParams.fraction_pct = sizerConfig.fraction_pct
    } else if (sizerConfig.type === 'atr') {
      sizerParams.atr_period = sizerConfig.atr_period
      sizerParams.atr_risk_coeff = sizerConfig.atr_risk_coeff
    } else if (sizerConfig.type === 'volatility_target') {
      sizerParams.vol_target = sizerConfig.vol_target
    }
    try {
      if (currentStrategyId) {
        const { updateStrategy } = useStrategyStore.getState()
        await updateStrategy(currentStrategyId, { name: strategyName, code: editorCode })
      } else {
        await createStrategy({
          name: strategyName,
          code: editorCode,
          description: '',
          parameters: { position_sizer: sizerParams },
        })
      }
      setEditorCode('')
      setStrategyName('')
      setCurrentStrategyId(null)
      setPreviewCode(null)
      setSizerConfig({ ...DEFAULT_SIZER_CONFIG })
    } catch (e: any) {
      console.warn('[Strategy] 保存策略失败:', e?.message)
      message.error('保存策略失败')
    }
  }

  const handleTemplate = (code: string) => {
    setEditorCode(code)
    setTemplateModal(false)
  }

  const handleAiGenerate = async () => {
    if (!aiDescription.trim()) return
    setAiGenerating(true)
    try {
      const res = await client.post('/api/ai/strategy/generate', { description: aiDescription })
      const body = (res as any).data ?? res
      if (body.code) {
        setEditorCode(body.code)
        setStrategyName(body.name ?? 'AI 生成策略')
        setAiModal(false)
        setAiDescription('')
        message.success('策略生成成功')
      } else {
        message.error(body.message || body.error || 'AI 未返回有效策略代码，请尝试更详细的描述')
      }
    } catch (err: any) {
      const errMsg = err?.message || 'AI 策略生成失败，请检查 LLM 配置后重试'
      message.error(errMsg)
    } finally {
      setAiGenerating(false)
    }
  }

  const handleEdit = async (r: any) => {
    const strategyId = r.id ?? r['id']
    // DB 中已有策略的 code 可能为 null，必须通过 API 获取详情
    try {
      const { strategyApi } = await import('@/api/strategy')
      const detail = await strategyApi.get(strategyId)
      setEditorCode(detail.code ?? '')
      setStrategyName(detail.name ?? r.name ?? r['name'] ?? '')
      setCurrentStrategyId(detail.id ?? strategyId ?? null)
      setPreviewCode(null)
    } catch {
      // API 失败则使用缓存数据
      setEditorCode(r.code ?? r['code'] ?? '')
      setStrategyName(r.name ?? r['name'] ?? '')
      setCurrentStrategyId(strategyId ?? null)
      setPreviewCode(null)
    }
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
          <Button type="primary" icon={<Sparkle size={16} />} onClick={() => setAiModal(true)}>AI 生成策略</Button>
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

          {/* 仓位管理 section */}
          <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>仓位管理</span>} style={{ marginBottom: 8, flexShrink: 0 }} styles={{ body: { padding: '8px 12px' } }}>
            <Space direction="vertical" style={{ width: '100%' }} size={8}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Text style={{ fontSize: 12, minWidth: 60 }}>仓位模型</Text>
                <Select
                  value={sizerConfig.type}
                  onChange={(v) => setSizerConfig((prev) => ({ ...prev, type: v as SizerType }))}
                  options={SIZER_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
                  size="small"
                  style={{ minWidth: 140 }}
                />
              </div>
              {sizerConfig.type === 'fixed_fraction' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Text style={{ fontSize: 12, minWidth: 60 }}>百分比</Text>
                  <InputNumber
                    size="small"
                    min={0.01}
                    max={1.0}
                    step={0.01}
                    value={sizerConfig.fraction_pct}
                    onChange={(v) => setSizerConfig((prev) => ({ ...prev, fraction_pct: v ?? 0.02 }))}
                    style={{ width: 100 }}
                  />
                </div>
              )}
              {sizerConfig.type === 'atr' && (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Text style={{ fontSize: 12, minWidth: 60 }}>ATR周期</Text>
                    <InputNumber
                      size="small"
                      min={1}
                      max={100}
                      value={sizerConfig.atr_period}
                      onChange={(v) => setSizerConfig((prev) => ({ ...prev, atr_period: v ?? 14 }))}
                      style={{ width: 100 }}
                    />
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Text style={{ fontSize: 12, minWidth: 60 }}>风险系数</Text>
                    <InputNumber
                      size="small"
                      min={0.01}
                      max={0.1}
                      step={0.01}
                      value={sizerConfig.atr_risk_coeff}
                      onChange={(v) => setSizerConfig((prev) => ({ ...prev, atr_risk_coeff: v ?? 0.02 }))}
                      style={{ width: 100 }}
                    />
                  </div>
                </>
              )}
              {sizerConfig.type === 'volatility_target' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Text style={{ fontSize: 12, minWidth: 60 }}>目标波动率</Text>
                  <InputNumber
                    size="small"
                    min={0.05}
                    max={0.5}
                    step={0.01}
                    value={sizerConfig.vol_target}
                    onChange={(v) => setSizerConfig((prev) => ({ ...prev, vol_target: v ?? 0.15 }))}
                    style={{ width: 100 }}
                  />
                </div>
              )}
              {(sizerConfig.type === 'kelly' || sizerConfig.type === 'equal_weight') && (
                <Text type="secondary" style={{ fontSize: 11 }}>此模型无需额外参数</Text>
              )}
            </Space>
          </Card>

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
                <a onClick={() => { setEditorCode(strategies.find((st) => st.name === s || st?.name === s)?.code ?? ''); setStrategyName(s); setCurrentStrategyId(strategies.find((st) => st.name === s || st?.name === s)?.id ?? null); setPreviewCode(null) }}>
                  <Text strong style={{ fontSize: 12 }}>{s}</Text>
                </a>
              ) },
              {
                title: '时间',
                key: 'time',
                width: 80,
                render: (_: any, r: any) => {
                  const dateStr = r.createdAt
                  if (!dateStr) return '-'
                  try { return new Date(dateStr).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) } catch { return '-' }
                },
              },
              {
                title: '',
                key: 'action',
                width: 60,
                render: (_: any, r: any) => (
                  <Space size={4}>
                    <Tooltip title="编辑">
                      <Button size="small" type="text" icon={<Code size={13} />} onClick={() => handleEdit(r)} />
                    </Tooltip>
                    <Tooltip title="删除">
                      <Popconfirm title="确定删除此策略？" onConfirm={() => deleteStrategy(r.id ?? r['id'])}>
                        <Button size="small" type="text" danger icon={<Trash size={13} />} />
                      </Popconfirm>
                    </Tooltip>
                  </Space>
                ),
              },
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

      {/* AI Generate Strategy modal */}
      <Modal
        title={<span><Sparkle size={16} style={{ marginRight: 6, verticalAlign: 'middle', color: 'var(--color-brand-primary)' }} />AI 生成策略</span>}
        open={aiModal}
        onCancel={() => { setAiModal(false); setAiDescription('') }}
        footer={null}
        width={520}
      >
        <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 12 }}>
          用自然语言描述你的策略，AI 将为你生成策略代码
        </Paragraph>
        <Input.TextArea
          value={aiDescription}
          onChange={(e) => setAiDescription(e.target.value)}
          placeholder='例如: "写一个基于RSI的超买超卖策略，RSI低于30买入，高于70卖出"'
          rows={4}
          style={{ marginBottom: 12 }}
          disabled={aiGenerating}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button onClick={() => { setAiModal(false); setAiDescription('') }}>取消</Button>
          <Button type="primary" icon={<Sparkle size={16} />} loading={aiGenerating} onClick={handleAiGenerate}>
            生成
          </Button>
        </div>
      </Modal>
    </div>
  )
}
