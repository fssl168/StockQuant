interface PreviewPanelProps {
  code: string | null
}

export default function PreviewPanel({ code }: PreviewPanelProps) {
  if (!code) return null

  return (
    <div style={{
      background: 'var(--color-bg-elevated)', padding: 12, borderRadius: 6,
      fontFamily: 'var(--font-mono)', fontSize: 12, maxHeight: 160, overflow: 'auto',
      whiteSpace: 'pre-wrap', color: 'var(--color-text-secondary)', marginTop: 10, flexShrink: 0,
    }}>
      {code}
    </div>
  )
}
