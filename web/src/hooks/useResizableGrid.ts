import { useRef, useCallback, useEffect, useState } from 'react'

export interface UseResizableGridOptions {
  minRatio?: number
  onChange?: (ratios: Record<string, number>) => void
}

export function useResizableGrid(options: UseResizableGridOptions = {}) {
  const { minRatio = 0.15, onChange } = options

  const ref = useRef<HTMLDivElement>(null)
  const resizing = useRef(false)
  const prevX = useRef(0)
  const totalWidth = useRef(0)

  const [ratios, setRatios] = useState<Record<string, number>>({
    primary: 0.45,
    secondary: 0.25,
    tertiary: 0.3,
  })
  const [splitter, setSplitter] = useState<string | null>(null)

  // 初始化: 根据 children 数量自动计算比例
  useEffect(() => {
    if (!ref.current) return
    const rect = ref.current.getBoundingClientRect()
    totalWidth.current = rect.width
    setRatios({
      primary: 0.45,
      secondary: 0.25,
      tertiary: 0.3,
    })
  }, [])

  const handleMouseDown = useCallback(
    (zoneKey: string) => (e: React.MouseEvent) => {
      e.preventDefault()
      resizing.current = true
      prevX.current = e.clientX
      setSplitter(zoneKey)
    },
    []
  )

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!resizing.current || !ref.current || !splitter) return

      const rect = ref.current.getBoundingClientRect()
      const dx = e.clientX - prevX.current
      const deltaRatio = dx / rect.width

      setRatios((prev) => {
        const keys = Object.keys(prev)
        const idx = keys.indexOf(splitter)
        if (idx < 0 || idx >= keys.length - 1) return prev

        const currentRatio = prev[splitter]
        const nextKey = keys[idx + 1]
        const nextRatio = prev[nextKey]

        let newCurrent = currentRatio
        let nextNew = nextRatio
        let adj = deltaRatio

        // 确保最小比例
        if (currentRatio + adj < minRatio) {
          adj = minRatio - currentRatio
        }
        if (nextRatio - adj < minRatio) {
          adj = nextRatio - minRatio
        }

        newCurrent = currentRatio + adj
        nextNew = nextRatio - adj

        const newRatios = { ...prev, [splitter]: newCurrent, [nextKey]: nextNew }
        onChange?.(newRatios)
        return newRatios
      })

      prevX.current = e.clientX
    }

    const handleMouseUp = () => {
      resizing.current = false
      setSplitter(null)
    }

    if (resizing.current) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
      return () => {
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [splitter, minRatio, onChange])

  return { ref, ratios, splitter, handleMouseDown }
}
