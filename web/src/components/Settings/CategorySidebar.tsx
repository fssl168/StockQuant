interface CategoryItem {
  key: string
  title: string
  icon: React.ReactNode
  description: string
  fieldCount: number
}

interface CategorySidebarProps {
  categories: CategoryItem[]
  activeKey: string
  onSelect: (key: string) => void
}

/**
 * Left sidebar category navigation (daily_stock_analysis style)
 */
export const CategorySidebar: React.FC<CategorySidebarProps> = ({
  categories,
  activeKey,
  onSelect,
}) => {
  return (
    <aside className="rounded-2xl border border-white/8 bg-card/60 p-3 backdrop-blur-sm">
      <p className="mb-2 text-xs uppercase tracking-wide text-muted">配置分类</p>
      <div className="space-y-2">
        {categories.map((cat) => {
          const isActive = cat.key === activeKey
          return (
            <button
              key={cat.key}
              onClick={() => onSelect(cat.key)}
              style={{
                width: '100%',
                textAlign: 'left',
                padding: '10px 12px',
                borderRadius: 8,
                border: `1px solid ${isActive ? 'var(--color-cyan)' : 'var(--border-dim)'}`,
                background: isActive ? 'rgba(0, 212, 255, 0.1)' : 'transparent',
                color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                cursor: 'pointer',
                transition: 'all 150ms ease',
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.borderColor = 'var(--border-default)'
                  e.currentTarget.style.color = 'var(--text-primary)'
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.borderColor = 'var(--border-dim)'
                  e.currentTarget.style.color = 'var(--text-secondary)'
                }
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 13, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {cat.icon}
                  {cat.title}
                </span>
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                  {cat.fieldCount}
                </span>
              </div>
              {cat.description && (
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  {cat.description}
                </span>
              )}
            </button>
          )
        })}
      </div>
    </aside>
  )
}
