import { useState, useEffect, useCallback, useRef } from 'react'

export type NetworkLatencyColor = 'green' | 'yellow' | 'red' | 'offline'

export interface NetworkStatus {
  latency: number | null
  color: NetworkLatencyColor
  isOnline: boolean
  reconnectedCount: number
  lastChecked: Date | null
  rejoin: (since: string) => void
}

const CHECK_INTERVAL_MS = 5000
const GREEN_THRESHOLD = 50
const YELLOW_THRESHOLD = 200

export function useNetworkStatus() {
  const [latency, setLatency] = useState<number | null>(null)
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [reconnectedCount, setReconnectedCount] = useState(0)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)

  const rejoinCallbacks = useRef<((since: string) => void)[]>([])

  const rejoin = useCallback((since: string) => {
    rejoinCallbacks.current.forEach((cb) => cb(since))
    setReconnectedCount((c) => c + 1)
  }, [])

  const registerRejoinCallback = useCallback((cb: (since: string) => void) => {
    rejoinCallbacks.current.push(cb)
    return () => {
      rejoinCallbacks.current = rejoinCallbacks.current.filter((c) => c !== cb)
    }
  }, [])

  const checkLatency = useCallback(async () => {
    if (!navigator.onLine) {
      setLatency(null)
      return
    }
    const start = performance.now()
    try {
      await fetch('/api/health', { method: 'GET', cache: 'no-store' })
      const elapsed = performance.now() - start
      setLatency(Math.round(elapsed))
      setLastChecked(new Date())
    } catch {
      // fetch 失败不影响 latency 状态（可能是网络问题，不是后端问题）
      setLatency(null)
      setLastChecked(new Date())
    }
  }, [])

  useEffect(() => {
    checkLatency()
    const interval = setInterval(checkLatency, CHECK_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [checkLatency])

  // 监听在线/离线状态
  useEffect(() => {
    const onOnline = () => setIsOnline(true)
    const onOffline = () => setIsOnline(false)

    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  const color: NetworkLatencyColor = (() => {
    if (!isOnline) return 'offline'
    if (latency === null) return 'yellow'
    if (latency <= GREEN_THRESHOLD) return 'green'
    if (latency <= YELLOW_THRESHOLD) return 'yellow'
    return 'red'
  })()

  return {
    latency,
    color,
    isOnline,
    reconnectedCount,
    lastChecked,
    rejoin,
    registerRejoinCallback,
  }
}

/**
 * 颜色对应的 CSS 工具类名
 */
export function getLatencyColorClass(color: NetworkLatencyColor): string {
  switch (color) {
    case 'green':
      return 'text-emerald-400'
    case 'yellow':
      return 'text-amber-400'
    case 'red':
      return 'text-red-400'
    case 'offline':
      return 'text-zinc-500'
  }
}

/**
 * 延迟毫秒数转显示文本
 */
export function formatLatency(latency: number | null): string {
  if (latency === null) return '--'
  return `${latency}ms`
}
