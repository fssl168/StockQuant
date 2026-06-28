'use client'
import { useState, useCallback, useRef, useEffect } from 'react'
import { useLayoutStore } from '@/stores/layoutStore'
import { useAuthStore } from '@/stores/authStore'
import { openMultiScreenLayout } from '@/utils/multiScreen'
import { useInfoFilter } from '@/hooks/useInfoFilter'
import { Monitor, DeviceTablet, XCircle, Sidebar, AppWindow, ArrowBendDownRight } from '@phosphor-icons/react'

export type ZoneKey = 'primary' | 'secondary' | 'tertiary'

interface Props {
  primaryContent: React.ReactNode
  secondaryContent: React.ReactNode
  tertiaryContent: React.ReactNode
}

const ZONE_KEYS: ZoneKey[] = ['primary', 'secondary', 'tertiary']

/**
 * InstitutionalLayout — 三区域 Grid 布局（单窗口模式）
 *
 * 核心能力:
 * 1. 拖拽分割线调整区域大小，比例持久化到 layoutStore（localStorage）
 * 2. 一键展开多屏模式（window.open）
 * 3. 信息降噪面板控制
 */
export default function InstitutionalLayout({ primaryContent, secondaryContent, tertiaryContent }: Props) {
  const zoneRatios = useLayoutStore((s) => s.zoneRatios)
  const setZoneRatio = useLayoutStore((s) => s.setZoneRatio)
  const resetZoneRatios = useLayoutStore((s) => s.resetZoneRatios)
  const institutionalEnabled = useLayoutStore((s) => s.institutionalEnabled)
  const { user } = useAuthStore()
  const { enabled: infoFilterEnabled } = useInfoFilter()

  const [expanded, setExpanded] = useState(false)
  const [draggingSplitter, setDraggingSplitter] = useState<ZoneKey | null>(null)

  // 拖拽状态（不触发 React 重渲染，只在 mouseup 时写入 store）
  const resizeState = useRef({
    active: false,
    zone: null as ZoneKey | null,
    startX: 0,
    startRatios: {} as Record<ZoneKey, number>,
  })

  // 处理拖拽开始
  const handleSplitterMouseDown = useCallback(
    (zone: ZoneKey) => (e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
      resizeState.current = {
        active: true,
        zone,
        startX: e.clientX,
        startRatios: { ...zoneRatios },
      }
      setDraggingSplitter(zone)
    },
    [zoneRatios]
  )

  // 全局鼠标移动（拖拽过程中）
  useEffect(() => {
    if (!resizeState.current.active || !draggingSplitter) return

    const handleMouseMove = (e: MouseEvent) => {
      const { active, zone: activeZone, startX, startRatios } = resizeState.current
      if (!active || !activeZone) return

      const container = document.querySelector('.institutional-grid-wrapper')
      if (!container) return

      const width = container.getBoundingClientRect().width
      if (width <= 0) return

      const dx = e.clientX - startX
      const deltaRatio = dx / width
      const minRatio = 0.15

      const idx = ZONE_KEYS.indexOf(activeZone)
      if (idx < 0 || idx >= ZONE_KEYS.length - 1) return

      const nextZone = ZONE_KEYS[idx + 1]
      const currentRatio = startRatios[activeZone]
      const nextRatio = startRatios[nextZone]

      let adj = deltaRatio
      // 最小比例约束
      if (currentRatio + adj < minRatio) adj = minRatio - currentRatio
      if (nextRatio - adj < minRatio) adj = nextRatio - minRatio

      const newCurrent = currentRatio + adj
      const nextNew = nextRatio - adj

      // 实时更新视觉反馈（通过直接修改 DOM style，避免 60fps 重渲染）
      const columns = container.querySelectorAll<HTMLElement>('.inst-zone')
      if (columns[idx] && columns[idx + 1]) {
        columns[idx].style.flex = `${newCurrent} 1 0%`
        columns[idx + 1].style.flex = `${nextNew} 1 0%`
      }
    }

    const handleMouseUp = () => {
      if (!resizeState.current.active) return

      // mouseup 时写入 store（持久化）
      const { zone: activeZone, startRatios } = resizeState.current
      if (activeZone) {
        // 重新读取当前 DOM 计算最终比例
        const container = document.querySelector('.institutional-grid-wrapper')
        if (container) {
          const width = container.getBoundingClientRect().width
          if (width > 0) {
            const idx = ZONE_KEYS.indexOf(activeZone)
            const columns = container.querySelectorAll<HTMLElement>('.inst-zone')
            if (columns[idx] && columns[idx + 1]) {
              const flexCurrent = parseFloat(columns[idx].style.flex) || startRatios[activeZone]
              const flexNext = parseFloat(columns[idx + 1].style.flex) || startRatios[ZONE_KEYS[idx + 1]]
              // 归一化为 0-1 比例
              const total = flexCurrent + flexNext
              if (total > 0) {
                setZoneRatio(activeZone, flexCurrent / total)
              }
            }
          }
        }
      }

      resizeState.current.active = false
      resizeState.current.zone = null
      setDraggingSplitter(null)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    // 拖拽时禁止文本选择
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
    }
  }, [draggingSplitter, setZoneRatio])

  const isTraderOrAdmin = user?.role === 'TRADER' || user?.role === 'ADMIN'

  const handleOpenMultiScreen = useCallback(() => {
    openMultiScreenLayout()
    setExpanded(true)
  }, [])

  const handleCloseMultiScreen = useCallback(() => {
    setExpanded(false)
  }, [])

  const handleResetLayout = useCallback(() => {
    resetZoneRatios()
  }, [resetZoneRatios])

  const zoneConfigs: Array<{
    key: ZoneKey
    label: string
    icon: React.ReactNode
    content: React.ReactNode
    hasSplitter: boolean
  }> = [
    { key: 'primary', label: '盯盘主屏', icon: <Monitor size={14} weight="fill" />, content: primaryContent, hasSplitter: true },
    { key: 'secondary', label: '大盘副屏', icon: <DeviceTablet size={14} weight="fill" />, content: secondaryContent, hasSplitter: true },
    { key: 'tertiary', label: '交易副屏', icon: <AppWindow size={14} weight="fill" />, content: tertiaryContent, hasSplitter: false },
  ]

  if (!institutionalEnabled) {
    return <>{primaryContent}</>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* 工具栏 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '4px 8px',
          borderBottom: '1px solid var(--color-border-default)',
          background: 'var(--color-bg-elevated)',
          minHeight: 32,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-mono)', letterSpacing: '0.04em' }}>
            机构模式
          </span>
          <span style={{
            fontSize: 10,
            padding: '1px 6px',
            borderRadius: 3,
            background: 'rgba(139,92,246,0.15)',
            color: '#a78bfa',
            fontFamily: 'var(--font-mono)',
          }}>
            {expanded ? '多屏' : '单窗口'}
          </span>
          {infoFilterEnabled && (
            <span style={{
              fontSize: 10,
              padding: '1px 6px',
              borderRadius: 3,
              background: 'rgba(239,68,68,0.15)',
              color: '#f87171',
              fontFamily: 'var(--font-mono)',
            }}>
              降噪中
            </span>
          )}
          {/* 区域比例指示 */}
          <span style={{
            fontSize: 10,
            color: 'var(--color-text-tertiary)',
            fontFamily: 'var(--font-mono)',
            opacity: 0.6,
          }}>
            {Math.round(zoneRatios.primary * 100)}% / {Math.round(zoneRatios.secondary * 100)}% / {Math.round(zoneRatios.tertiary * 100)}%
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {/* 重置按钮 */}
          {isTraderOrAdmin && (
            <button
              onClick={handleResetLayout}
              style={{
                fontSize: 10,
                color: 'var(--color-text-tertiary)',
                background: 'transparent',
                border: '1px solid var(--color-border-default)',
                borderRadius: 3,
                padding: '1px 6px',
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
                display: 'flex',
                alignItems: 'center',
                gap: 3,
                transition: 'color 150ms ease, border-color 150ms ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = 'var(--color-text-secondary)'
                e.currentTarget.style.borderColor = 'var(--color-text-secondary)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--color-text-tertiary)'
                e.currentTarget.style.borderColor = 'var(--color-border-default)'
              }}
              title="重置区域比例"
            >
              <ArrowBendDownRight size={10} weight="bold" />
              重置
            </button>
          )}

          {expanded ? (
            <button
              onClick={handleCloseMultiScreen}
              style={{
                fontSize: 11,
                color: 'var(--color-text-secondary)',
                background: 'transparent',
                border: '1px solid var(--color-border-default)',
                borderRadius: 4,
                padding: '2px 8px',
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                transition: 'color 150ms ease, border-color 150ms ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = 'var(--color-brand-primary)'
                e.currentTarget.style.borderColor = 'var(--color-brand-primary)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--color-text-secondary)'
                e.currentTarget.style.borderColor = 'var(--color-border-default)'
              }}
            >
              <XCircle size={12} weight="fill" />
              关闭多屏
            </button>
          ) : isTraderOrAdmin ? (
            <button
              onClick={handleOpenMultiScreen}
              style={{
                fontSize: 11,
                color: 'var(--color-text-secondary)',
                background: 'transparent',
                border: '1px solid var(--color-border-default)',
                borderRadius: 4,
                padding: '2px 8px',
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                transition: 'color 150ms ease, border-color 150ms ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = 'var(--color-brand-primary)'
                e.currentTarget.style.borderColor = 'var(--color-brand-primary)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--color-text-secondary)'
                e.currentTarget.style.borderColor = 'var(--color-border-default)'
              }}
            >
              <Sidebar size={12} weight="fill" />
              展开多屏
            </button>
          ) : null}
        </div>
      </div>

      {/* 三区域 Grid */}
      <div className="institutional-grid-wrapper" style={{
        display: 'flex',
        flex: 1,
        overflow: 'hidden',
        background: 'var(--color-border-default)',
      }}>
        {zoneConfigs.map((zone) => {
          const ratio = zoneRatios[zone.key]
          const isDraggingThis = draggingSplitter === zone.key
          const isDraggingNeighbor = zone.key === 'secondary' && draggingSplitter === 'primary'

          return (
            <div
              key={zone.key}
              className="inst-zone"
              style={{
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                background: 'var(--color-bg-base)',
                flex: `${ratio} 1 0%`,
                minWidth: 200,
              }}
            >
              {/* 区域标题 */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '4px 8px',
                  fontSize: 10,
                  color: isDraggingThis ? 'var(--color-brand-primary)' : 'var(--color-text-tertiary)',
                  fontFamily: 'var(--font-mono)',
                  letterSpacing: '0.04em',
                  borderBottom: '1px solid var(--color-border-default)',
                  background: isDraggingThis
                    ? 'rgba(59,130,246,0.08)'
                    : 'var(--color-bg-elevated)',
                  transition: 'color 150ms ease, background 150ms ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {zone.icon}
                  {zone.label}
                </div>
                <span style={{ opacity: 0.5 }}>
                  {Math.round(ratio * 100)}%
                </span>
              </div>

              {/* 内容区 */}
              <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
                {zone.content}
              </div>

              {/* 右侧拖拽分割线 */}
              {zone.hasSplitter && (
                <div
                  onMouseDown={handleSplitterMouseDown(zone.key)}
                  style={{
                    position: 'absolute',
                    right: 0,
                    top: 0,
                    bottom: 0,
                    width: (isDraggingThis || isDraggingNeighbor) ? 6 : 3,
                    cursor: 'col-resize',
                    background: (isDraggingThis || isDraggingNeighbor)
                      ? 'var(--color-brand-primary)'
                      : 'transparent',
                    transition: 'background 150ms ease, width 150ms ease',
                    zIndex: 10,
                  }}
                  onMouseEnter={(e) => {
                    if (!draggingSplitter) {
                      e.currentTarget.style.background = 'rgba(59,130,246,0.4)'
                      e.currentTarget.style.width = '5px'
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!draggingSplitter && !isDraggingThis && !isDraggingNeighbor) {
                      e.currentTarget.style.background = 'transparent'
                      e.currentTarget.style.width = '3px'
                    }
                  }}
                />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
