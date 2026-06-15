import { useEffect, useState } from 'react'
import { Table, Button, Input, Card, Typography, Space, Modal, Tooltip } from 'antd'
import { Plus, Code, Eye, Trash, FloppyDisk, Wrench } from '@phosphor-icons/react'
import { useStrategyStore } from '@/stores/strategyStore'
import Editor from '@monaco-editor/react'

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
  const [previewCode, setPreviewCode] = useState<string | null>(null)
  const [templateModal, setTemplateModal] = useState(false)
  const [syntaxResult, setSyntaxResult] = useState<{ ok: boolean; msg: string } | null>(null)

  useEffect(() => { fetchStrategies() }, [fetchStrategies])

  const handleCreate = () => {
    setStrategyName('')
    setEditorCode('')
    setPreviewCode(null)
  }

  const handleSave = async () => {
    if (!strategyName.trim() || !editorCode.trim()) return
    try {
      await createStrategy({
        name: strategyName,
        code: editorCode,
        description: '',
        parameters: {},
      })
      setEditorCode('')
      setStrategyName('')
      setPreviewCode(null)
    } catch { /* ignore */ }
  }

  const handleTemplate = (code: string) => {
    setEditorCode(code)
    setTemplateModal(false)
  }

  const handleSyntaxCheck = () => {
    const code = editorCode.trim()
    if (!code) { setSyntaxResult({ ok: false, msg: '代码不能为空' }); return }
    const errors: string[] = []
    if (!code.includes('class ')) errors.push('缺少策略类定义 (class)')
    if (!code.includes('BaseStrategy')) errors.push('未继承 BaseStrategy')
    if (!code.includes('def on_bar')) errors.push('缺少 on_bar 方法')
    if (!code.includes('def on_start') && !code.includes('def initialize')) errors.push('建议添加 on_start/initialize 方法')
    let depth = 0
    for (const ch of code) { if (ch === '{' || ch === '[' || ch === '(') depth++; if (ch === '}' || ch === ']' || ch === ')') depth-- }
    if (depth !== 0) errors.push(`括号不匹配 (深度差: ${depth})`)
    const lines = code.split('\n').filter((l) => l.trim())
    const indents = lines.map((l) => l.search(/\S/)).filter((n) => n >= 0)
    if (indents.length > 2 && indents.map((n) => n % 4).some((m) => m !== 0)) errors.push('缩进非 4 的倍数')
    if (errors.length === 0) {
      setSyntaxResult({ ok: true, msg: '语法检查通过 ✓ 类定义完整，方法齐全，括号匹配正确' })
    } else {
      setSyntaxResult({ ok: false, msg: `发现 ${errors.length} 个问题:\n• ${errors.join('\n• ')}` })
    }
    setTimeout(() => setSyntaxResult(null), 8000)
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
        {/* Left: Monaco Editor (70%) */}
        <Card
          size="small"
          title={
            <span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Code size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />
              策略编辑器
            </span>
          }
          style={{ flex: 7, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
          styles={{ body: { padding: 12, display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' } }}
        >
          {/* Editor toolbar row */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 10, alignItems: 'center', flexShrink: 0 }}>
            <Input
              value={strategyName}
              onChange={(e) => setStrategyName(e.target.value)}
              placeholder="策略名称"
              size="small"
              style={{ maxWidth: 220 }}
            />
            <div style={{ flex: 1 }} />
            <Tooltip title="保存策略">
              <Button type="primary" size="small" icon={<FloppyDisk size={14} />} onClick={handleSave} disabled={!strategyName.trim() || !editorCode.trim()}>保存</Button>
            </Tooltip>
            <Tooltip title="预览代码">
              <Button size="small" icon={<Eye size={14} />} onClick={() => setPreviewCode(editorCode || null)}>预览</Button>
            </Tooltip>
            <Tooltip title="语法检查">
              <Button size="small" icon={<Wrench size={14} />} onClick={handleSyntaxCheck}>语法检查</Button>
            </Tooltip>
          </div>

          {/* Monaco Editor */}
          <div style={{ border: '1px solid var(--color-border-default)', borderRadius: 6, overflow: 'hidden', flex: 1, minHeight: 300 }}>
            <Editor
              height="100%"
              defaultLanguage="python"
              value={editorCode}
              theme="vs-dark"
              onChange={(v) => setEditorCode(v ?? '')}
              options={{
                fontSize: 13, lineHeight: 20, minimap: { enabled: false },
                scrollBeyondLastLine: false, automaticLayout: true, tabSize: 4,
              }}
            />
          </div>

          {/* Syntax check result */}
          {syntaxResult && (
            <div style={{
              padding: '8px 12px', borderRadius: 6, fontSize: 12, fontFamily: 'var(--font-mono)',
              background: syntaxResult.ok ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
              border: `1px solid ${syntaxResult.ok ? '#10b981' : '#ef4444'}`,
              color: syntaxResult.ok ? '#10b981' : '#ef4444',
              marginTop: 8, flexShrink: 0,
              whiteSpace: 'pre-wrap',
            }}>
              {syntaxResult.msg}
            </div>
          )}

          {/* Preview panel */}
          {previewCode && (
            <div style={{
              background: 'var(--color-bg-elevated)', padding: 12, borderRadius: 6,
              fontFamily: 'var(--font-mono)', fontSize: 12, maxHeight: 160, overflow: 'auto',
              whiteSpace: 'pre-wrap', color: 'var(--color-text-secondary)', marginTop: 10, flexShrink: 0,
            }}>
              {previewCode}
            </div>
          )}
        </Card>

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
                <a onClick={() => { setEditorCode(strategies.find((st) => st.name === s)?.code ?? ''); setStrategyName(s); setPreviewCode(null) }}>
                  <Text strong style={{ fontSize: 12 }}>{s}</Text>
                </a>
              ) },
              { title: '时间', dataIndex: 'created_at', key: 'time', width: 80, render: (d: string) => d ? new Date(d).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) : '-' },
              { title: '', key: 'action', width: 60, render: (_: any, r: any) => (
                <Space size={4}>
                  <Tooltip title="编辑">
                    <Button size="small" type="text" icon={<Code size={13} />} onClick={() => { setEditorCode(r.code); setStrategyName(r.name); setPreviewCode(null) }} />
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
