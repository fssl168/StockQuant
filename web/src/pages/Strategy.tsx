import { useEffect, useState } from 'react'
import { Table, Button, Input, Card, Typography, Space, Modal } from 'antd'
import { Plus, Code, Eye, Trash, FloppyDisk } from '@phosphor-icons/react'
import { useStrategyStore } from '@/stores/strategyStore'
import Editor from '@monaco-editor/react'

const { Title, Text } = Typography

const DEFAULT_TEMPLATES = [
  { name: 'Dual MA Crossover', code: `from stockquant.strategy import BaseStrategy\nfrom stockquant.indicators import EMA\n\nclass DualMACrossover(BaseStrategy):\n    name = "Dual MA Crossover"\n    parameters = {"fast": 5, "slow": 20, "position_size": 0.1}\n\n    def on_start(self):\n        self.ma_fast = EMA(self.data, period=self.parameters["fast"])\n        self.ma_slow = EMA(self.data, period=self.parameters["slow"])\n\n    def on_bar(self):\n        if self.ma_fast[0] > self.ma_slow[0] and self.ma_fast[-1] <= self.ma_slow[-1]:\n            self.order_market(self.data.close[0], 100)\n        elif self.ma_fast[0] < self.ma_slow[0] and self.ma_fast[-1] >= self.ma_slow[-1]:\n            self.close_all()` },
  { name: 'RSI Reversal', code: `from stockquant.strategy import BaseStrategy\nfrom stockquant.indicators import RSI\n\nclass RSIReversal(BaseStrategy):\n    name = "RSI Reversal"\n    parameters = {"period": 14, "oversold": 30, "overbought": 70, "position_size": 0.2}\n\n    def on_start(self):\n        self.rsi = RSI(self.data, period=self.parameters["period"])\n\n    def on_bar(self):\n        if self.rsi[0] < self.parameters["oversold"]:\n            self.order_market(self.data.close[0], 100)\n        elif self.rsi[0] > self.parameters["overbought"]:\n            self.close_all()` },
  { name: 'MACD Divergence', code: `from stockquant.strategy import BaseStrategy\nfrom stockquant.indicators import MACD\n\nclass MACDDivergence(BaseStrategy):\n    name = "MACD Divergence"\n    parameters = {"fast": 12, "slow": 26, "signal": 9}\n\n    def on_start(self):\n        self.macd = MACD(self.data, fast=12, slow=26, signal=9)\n\n    def on_bar(self):\n        if self.macd.historical[-1] > 0 and self.macd.signal[-1] < 0:\n            self.order_market(self.data.close[0], 100)\n        elif self.macd.historical[-1] < 0:\n            self.close_all()` },
]

export default function Strategy() {
  const { strategies, loading, fetchStrategies, createStrategy, deleteStrategy } = useStrategyStore()
  const [editMode, setEditMode] = useState(false)
  const [editorCode, setEditorCode] = useState('')
  const [strategyName, setStrategyName] = useState('')
  const [previewCode, setPreviewCode] = useState('')
  const [templateModal, setTemplateModal] = useState(false)

  useEffect(() => { fetchStrategies() }, [fetchStrategies])

  const handleCreate = () => {
    setEditMode(true)
    setStrategyName('')
    setEditorCode('')
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
      setEditMode(false)
      setEditorCode('')
      setStrategyName('')
    } catch { /* ignore */ }
  }

  const handleTemplate = (code: string) => {
    setEditorCode(code)
    setTemplateModal(false)
  }

  return (
    <div style={{ maxWidth: 1400 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: 20 }}>
        <div>
          <Title level={4} style={{ margin: 0, fontWeight: 600, fontSize: 16 }}>策略管理</Title>
          <Text type="secondary" style={{ fontSize: 12 }}>编写、编辑和管理交易策略</Text>
        </div>
        <Space>
          <Button icon={<Plus size={16} />} onClick={handleCreate}>新建</Button>
          <Button icon={<Code size={16} />} onClick={() => setTemplateModal(true)}>从模板</Button>
        </Space>
      </div>

      {/* Editor */}
      {editMode && (
        <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>策略编辑器</span>} styles={{ body: { padding: 16 } }} style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: '100%' }} size={8}>
            <Input
              value={strategyName}
              onChange={(e) => setStrategyName(e.target.value)}
              placeholder="策略名称"
              size="large"
              style={{ maxWidth: 300 }}
            />
            <div style={{ border: '1px solid var(--surface-border)', borderRadius: 6, overflow: 'hidden' }}>
              <Editor
                height={350}
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
            <Space>
              <Button type="primary" icon={<FloppyDisk size={16} />} onClick={handleSave}>保存</Button>
              <Button icon={<Eye size={16} />} onClick={() => setPreviewCode(editorCode)}>预览</Button>
              <Button onClick={() => setEditMode(false)}>取消</Button>
            </Space>
            {previewCode && (
              <div style={{ background: '#111', padding: 12, borderRadius: 6, fontFamily: 'var(--font-mono)', fontSize: 12, maxHeight: 200, overflow: 'auto', whiteSpace: 'pre-wrap', color: '#ccc' }}>
                {previewCode}
              </div>
            )}
          </Space>
        </Card>
      )}

      {/* Strategy table */}
      <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>策略列表</span>} styles={{ body: { padding: '0' } }}>
        <Table
          dataSource={strategies}
          rowKey="id"
          pagination={false}
          size="small"
          loading={loading}
          columns={[
            { title: '名称', dataIndex: 'name', key: 'name', width: 200, render: (s: string) => <Text strong>{s}</Text> },
            { title: '代码预览', key: 'code', render: (_: any, r: any) => (
              <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#666' }}>
                {(r.code ?? '').slice(0, 60)}...
              </Text>
            )},
            { title: '创建时间', dataIndex: 'created_at', key: 'time', width: 150, render: (d: string) => d ? new Date(d).toLocaleDateString() : '-' },
            { title: '操作', key: 'action', width: 100, render: (_: any, r: any) => (
              <Space>
                <Button size="small" onClick={() => { setEditMode(true); setEditorCode(r.code); setStrategyName(r.name) }}>编辑</Button>
                <Button danger size="small" icon={<Trash size={14} />} onClick={() => deleteStrategy(r.id)}>删除</Button>
              </Space>
            )},
          ]}
          scroll={{ x: 600 }}
        />
      </Card>

      {/* Template modal */}
      <Modal title="策略模板库" open={templateModal} onCancel={() => setTemplateModal(false)} footer={null} width={600}>
        <Space direction="vertical" style={{ width: '100%' }} size={8}>
          {DEFAULT_TEMPLATES.map((t) => (
            <Card
              key={t.name}
              size="small"
              hoverable
              styles={{ body: { padding: '10px 14px' } }}
              onClick={() => handleTemplate(t.code)}
              style={{ cursor: 'pointer', border: '1px solid var(--surface-border)' }}
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
