import { useLayoutStore } from '@/stores/layoutStore'
import { useInfoFilter } from '@/hooks/useInfoFilter'
import { FunnelSimple, XCircle } from '@phosphor-icons/react'

/**
 * 信息降噪控制面板
 * 用于 Settings 页面中显示
 */
export default function InfoFilterToggle() {
  const { hidePanels } = useInfoFilter()
  const { setHidePanel } = useLayoutStore()

  const corePanels: Array<{ key: import('@/stores/layoutStore').ScreenComponent; label: string }> = [
    { key: 'depth', label: '盘口深度' },
    { key: 'tick', label: '逐笔成交' },
    { key: 'volume_ratio', label: '分时量比' },
    { key: 'watchlist', label: '自选股列表' },
    { key: 'kline', label: 'K 线图' },
  ]

  const optionalPanels: Array<{ key: import('@/stores/layoutStore').ScreenComponent; label: string }> = [
    { key: 'sentiment', label: '情绪面板' },
    { key: 'indices', label: '指数列表' },
    { key: 'heatmap', label: '板块热力图' },
    { key: 'alerts', label: '预警列表' },
    { key: 'order_panel', label: '下单面板' },
    { key: 'position_panel', label: '持仓面板' },
  ]

  return (
    <div
      style={{
        padding: 16,
        border: '1px solid var(--color-border-default)',
        borderRadius: 8,
        background: 'var(--color-bg-elevated)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FunnelSimple size={16} weight="fill" style={{ color: 'var(--color-text-secondary)' }} />
          <span style={{ fontSize: 13, color: 'var(--color-text-secondary)', fontWeight: 500 }}>
            信息降噪
          </span>
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', marginBottom: 6, letterSpacing: '0.04em' }}>
          核心数据
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {corePanels.map((p) => (
            <span
              key={p.key}
              style={{
                fontSize: 10,
                padding: '2px 6px',
                borderRadius: 3,
                background: 'rgba(139,92,246,0.12)',
                color: '#a78bfa',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {p.label}
            </span>
          ))}
        </div>
      </div>

      <div>
        <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', marginBottom: 6, letterSpacing: '0.04em' }}>
          可选面板（点击切换）
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {optionalPanels.map((p) => {
            const hidden = hidePanels.includes(p.key)
            return (
              <button
                key={p.key}
                onClick={() => setHidePanel(p.key as never, !hidden)}
                style={{
                  fontSize: 10,
                  padding: '2px 6px',
                  borderRadius: 3,
                  border: '1px solid',
                  borderColor: hidden ? 'var(--color-border-default)' : 'var(--color-brand-primary)',
                  background: hidden ? 'transparent' : 'rgba(139,92,246,0.1)',
                  color: hidden ? 'var(--color-text-tertiary)' : 'var(--color-brand-primary)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 3,
                  fontFamily: 'var(--font-mono)',
                  transition: 'all 150ms ease',
                }}
              >
                {hidden && <XCircle size={10} weight="fill" />}
                {p.label}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
