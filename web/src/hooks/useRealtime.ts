# -*- coding: utf-8 -*-
"""WebSocket 集成 React Query - 实现实时数据刷新"""

import { useEffect, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useWebSocket } from './useWebSocket'
import type { WSMessage } from '@/types'

interface UseRealtimeOptions {
  /** 订阅的消息类型 */
  messageTypes?: string[]
  /** 是否自动连接 */
  autoConnect?: boolean
  /** 心跳间隔(毫秒) */
  heartbeatInterval?: number
}

/**
 * WebSocket 实时数据 hook
 * 
 * 自动将 WebSocket 推送的消息同步到 React Query 缓存
 * 支持的刷新规则：
 * - progress: 任务进度更新 → 刷新 backtest-tasks
 * - metrics: 回测指标更新 → 刷新 backtest-result
 * - trade: 交易成交 → 刷新 orders, positions
 * - alert: 告警通知 → 刷新 notifications
 * - quote: 行情报价 → 刷新 quotes
 */
export function useRealtime(options: UseRealtimeOptions = {}) {
  const { 
    messageTypes = ['progress', 'metrics', 'trade', 'alert', 'quote'],
    autoConnect = true,
    heartbeatInterval = 30000 
  } = options

  const queryClient = useQueryClient()
  const wsRef = useRef<{ send: (msg: string) => void } | null>(null)

  // 根据消息类型刷新对应的 Query 缓存
  const invalidateByMessage = useCallback((message: WSMessage) => {
    switch (message.type) {
      case 'progress':
        // 任务进度更新，刷新任务列表
        if (message.task_id) {
          queryClient.invalidateQueries({ queryKey: ['backtest-tasks'] })
          queryClient.invalidateQueries({ queryKey: ['backtest-result', message.task_id] })
        }
        break

      case 'metrics':
        // 回测指标更新
        if (message.task_id) {
          queryClient.invalidateQueries({ queryKey: ['backtest-result', message.task_id] })
        }
        break

      case 'trade':
        // 交易成交，刷新订单和持仓
        queryClient.invalidateQueries({ queryKey: ['orders'] })
        queryClient.invalidateQueries({ queryKey: ['positions'] })
        queryClient.invalidateQueries({ queryKey: ['trades'] })
        break

      case 'alert':
        // 告警通知，刷新通知列表
        queryClient.invalidateQueries({ queryKey: ['notifications'] })
        queryClient.invalidateQueries({ queryKey: ['monitor-alerts'] })
        break

      case 'quote':
        // 行情报价，刷新相关行情数据
        if (message.symbol) {
          queryClient.invalidateQueries({ queryKey: ['quote', message.symbol] })
          queryClient.invalidateQueries({ queryKey: ['kline', message.symbol] })
        }
        break

      case 'order_update':
        // 订单状态更新
        queryClient.invalidateQueries({ queryKey: ['orders'] })
        break

      case 'position_update':
        // 持仓更新
        queryClient.invalidateQueries({ queryKey: ['positions'] })
        break

      default:
        break
    }
  }, [queryClient])

  // WebSocket 配置
  const wsConfig = {
    url: getWebSocketUrl(),
    onMessage: (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data) as WSMessage
        if (messageTypes.includes(message.type)) {
          invalidateByMessage(message)
        }
      } catch (err) {
        console.error('[useRealtime] Failed to parse message:', err)
      }
    },
    onOpen: () => {
      console.log('[useRealtime] WebSocket connected')
      // 订阅指定类型的消息
      wsRef.current?.send(JSON.stringify({
        type: 'subscribe',
        channels: messageTypes,
      }))
    },
    onError: (error: Event) => {
      console.error('[useRealtime] WebSocket error:', error)
    },
    heartbeatInterval,
  }

  // 使用现有的 useWebSocket hook
  const { sendMessage, ...wsState } = useWebSocket(wsConfig)
  wsRef.current = { send: sendMessage }

  // 订阅消息
  const subscribe = useCallback((types: string[]) => {
    sendMessage(JSON.stringify({
      type: 'subscribe',
      channels: types,
    }))
  }, [sendMessage])

  // 取消订阅
  const unsubscribe = useCallback((types: string[]) => {
    sendMessage(JSON.stringify({
      type: 'unsubscribe',
      channels: types,
    }))
  }, [sendMessage])

  return {
    ...wsState,
    subscribe,
    unsubscribe,
    invalidateByMessage,
  }
}

// 获取 WebSocket URL
function getWebSocketUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = import.meta.env.VITE_WS_URL || window.location.host
  return `${protocol}//${host}/ws`
}

export default useRealtime
