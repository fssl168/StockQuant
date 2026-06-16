import { useState } from 'react'
import { Card, Button, Tooltip } from 'antd'
import { Eye, FloppyDisk, Wrench } from '@phosphor-icons/react'
import Editor from '@monaco-editor/react'

interface StrategyEditorProps {
  code: string
  onChange: (value: string) => void
  onSave?: () => void
  onCheck?: () => void
  saving?: boolean
}

export default function StrategyEditor({ code, onChange, onSave, onCheck, saving }: StrategyEditorProps) {
  const [syntaxResult, setSyntaxResult] = useState<{ ok: boolean; msg: string } | null>(null)

  const handleSyntaxCheck = () => {
    const editorCode = code.trim()
    if (!editorCode) { setSyntaxResult({ ok: false, msg: '代码不能为空' }); return }
    const errors: string[] = []
    if (!editorCode.includes('class ')) errors.push('缺少策略类定义 (class)')
    if (!editorCode.includes('BaseStrategy')) errors.push('未继承 BaseStrategy')
    if (!editorCode.includes('def on_bar')) errors.push('缺少 on_bar 方法')
    if (!editorCode.includes('def on_start') && !editorCode.includes('def initialize')) errors.push('建议添加 on_start/initialize 方法')
    let depth = 0
    for (const ch of editorCode) { if (ch === '{' || ch === '[' || ch === '(') depth++; if (ch === '}' || ch === ']' || ch === ')') depth-- }
    if (depth !== 0) errors.push(`括号不匹配 (深度差: ${depth})`)
    const lines = editorCode.split('\n').filter((l) => l.trim())
    const indents = lines.map((l) => l.search(/\S/)).filter((n) => n >= 0)
    if (indents.length > 2 && indents.map((n) => n % 4).some((m) => m !== 0)) errors.push('缩进非 4 的倍数')
    if (errors.length === 0) {
      setSyntaxResult({ ok: true, msg: '语法检查通过 ✓ 类定义完整，方法齐全，括号匹配正确' })
    } else {
      setSyntaxResult({ ok: false, msg: `发现 ${errors.length} 个问题:\n• ${errors.join('\n• ')}` })
    }
    setTimeout(() => setSyntaxResult(null), 8000)
    onCheck?.()
  }

  return (
    <Card
      size="small"
      title={
        <span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Eye size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />
          策略编辑器
        </span>
      }
      style={{ flex: 7, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
      styles={{ body: { padding: 12, display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' } }}
    >
      {/* Editor toolbar row */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 10, alignItems: 'center', flexShrink: 0 }}>
        <div style={{ flex: 1 }} />
        <Tooltip title="保存策略">
          <Button type="primary" size="small" icon={<FloppyDisk size={14} />} onClick={onSave} loading={saving}>保存</Button>
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
          value={code}
          theme="vs-dark"
          onChange={(v) => onChange(v ?? '')}
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
    </Card>
  )
}
