/**
 * useChartPreload — 监测容器可见性，用于图表预加载/暂停
 *
 * 用 IntersectionObserver 实现，进入视口时触发 onVisible，离开触发 onHide。
 * 支持 preloadDistance（rootMargin 提前预加载）。
 *
 * 使用示例:
 *   const { ref, isVisible } = useChartPreload({
 *     preloadDistance: 200,
 *     onVisible: () => console.log('chart visible, start fetching'),
 *     onHide: () => console.log('chart hidden, stop subscription'),
 *   })
 *   return <div ref={ref}><Chart /></div>
 */
import { useEffect, useRef, useState } from 'react'

export interface UseChartPreloadOptions {
  /** 提前多少像素预加载（rootMargin bottom），默认 200 */
  preloadDistance?: number
  /** 进入视口回调 */
  onVisible?: () => void
  /** 离开视口回调 */
  onHide?: () => void
  /** 是否启用，默认 true。false 时不挂 observer */
  enabled?: boolean
}

export interface UseChartPreloadReturn {
  /** 绑定到容器节点的 ref */
  ref: React.RefObject<HTMLDivElement>
  /** 容器当前是否可见 */
  isVisible: boolean
}

export function useChartPreload(options?: UseChartPreloadOptions): UseChartPreloadReturn {
  const preloadDistance = options?.preloadDistance ?? 200
  const enabled = options?.enabled ?? true

  const ref = useRef<HTMLDivElement>(null)
  const [isVisible, setIsVisible] = useState(false)

  // 用 ref 保存最新回调，避免 observer 频繁重建
  const onVisibleRef = useRef(options?.onVisible)
  const onHideRef = useRef(options?.onHide)
  useEffect(() => { onVisibleRef.current = options?.onVisible }, [options?.onVisible])
  useEffect(() => { onHideRef.current = options?.onHide }, [options?.onHide])

  useEffect(() => {
    if (!enabled) return
    const el = ref.current
    if (!el) return

    // 不支持 IntersectionObserver 时降级为始终可见
    if (typeof IntersectionObserver === 'undefined') {
      setIsVisible(true)
      onVisibleRef.current?.()
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const visible = entry.isIntersecting
          setIsVisible((prev) => {
            if (visible && !prev) {
              onVisibleRef.current?.()
            } else if (!visible && prev) {
              onHideRef.current?.()
            }
            return visible
          })
        }
      },
      {
        root: null,
        rootMargin: `0px 0px ${preloadDistance}px 0px`,
        threshold: 0,
      }
    )

    observer.observe(el)
    return () => {
      observer.disconnect()
    }
  }, [enabled, preloadDistance])

  return { ref, isVisible }
}
