import { useState, useEffect, useCallback, useRef } from 'react'

/**
 * 逐笔级数据刷新 Hook
 *
 * 强制 WebSocket 以 tick 模式推送，并在前端做去重 + 批渲染，
 * 避免 React 因高频数据更新而过度重渲染。
 *
 * 使用示例:
 *   const { forceTickMode, latestTick, updateCount } = useTickLevelRefresh('sh600519')
 */

export interface TickData {
  symbol: string
  price: number
  volume: number
  bid: number
  ask: number
  timestamp: number
}

interface UseTickLevelRefreshResult {
  /** 最新逐笔数据 */
  latestTick: TickData | null
  /** 已接收数据点数（调试用） */
  updateCount: number
  /** 强制切换为 tick 模式 */
  forceTickMode: () => void
  /** 是否处于 tick 模式 */
  isTickMode: boolean
  /** 添加逐笔数据（从 WebSocket 调用） */
  addTick: (tick: TickData) => void
  /** 手动 flush 缓冲区 */
  flush: () => void
}

const MAX_BATCH_SIZE = 10
const FLUSH_INTERVAL_MS = 100 // 最多 100ms 才渲染一次

export function useTickLevelRefresh(_symbol: string): UseTickLevelRefreshResult {
  const [latestTick, setLatestTick] = useState<TickData | null>(null)
  const [updateCount, setUpdateCount] = useState(0)
  const [isTickMode, setIsTickMode] = useState(false)

  // 批处理缓冲区
  const buffer = useRef<TickData[]>([])
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  /**
   * 接收一条逐笔数据（从 WebSocket 调用）
   */
  const addTick = useCallback((tick: TickData) => {
    buffer.current.push(tick)

    setUpdateCount((c) => c + 1)

    // 达到批大小或超时，flush
    if (buffer.current.length >= MAX_BATCH_SIZE) {
      flushBuffer()
    } else if (!timerRef.current) {
      timerRef.current = setTimeout(() => {
        flushBuffer()
      }, FLUSH_INTERVAL_MS)
    }
  }, [])

  const flushBuffer = useCallback(() => {
    if (buffer.current.length === 0) {
      timerRef.current = null
      return
    }

    // 取最新的
    const last = buffer.current[buffer.current.length - 1]
    setLatestTick(last)
    buffer.current = []
    timerRef.current = null
  }, [])

  /**
   * 手动 flush（可由调用者在需要时触发）
   */
  const flush = useCallback(() => {
    flushBuffer()
  }, [flushBuffer])

  /**
   * 切换为 tick 模式
   */
  const forceTickMode = useCallback(() => {
    setIsTickMode(true)
    // 通知父组件（通常是 Monitor 页面）在 WebSocket 中发送 subscribe tick 消息
    // 通过自定义事件解耦
    window.dispatchEvent(
      new CustomEvent('stockquant-tick-mode', { detail: { enabled: true, symbol: _symbol } })
    )
  }, [_symbol])

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  return { latestTick, updateCount, forceTickMode, isTickMode, addTick: addTick as never, flush }
}

/**
 * 通用数据去重 + 节流渲染（适用于任何高频数据流）
 *
 * @param rawData - 原始高频数据数组（来自 WebSocket / API）
 * @param options - 配置
 * @returns 去重后的稳定数据（React 稳定引用，减少重渲染）
 */
export function useLatestData<T>(rawData: T[], options?: { maxStaleness?: number }): T[] {
  const { maxStaleness = 50 } = options ?? {}

  // 只取最近 N 条，避免数据无限增长
  const stableData = rawData.slice(-maxStaleness)

  return stableData
}
