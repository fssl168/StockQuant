import { useEffect, useRef, useCallback, useState } from 'react'

export interface WSMessage {
  type: string
  taskId?: string
  data: unknown
  timestamp: string
}

interface UseWebSocketOptions {
  /** When true, suppress all console.warn on connection failures */
  silent?: boolean
  /** Called on reconnect with the timestamp of the last received message */
  onReconnect?: (lastTimestamp: string) => void
  /** 轮询降级时的 HTTP GET 端点（不传则使用 ws URL 转换） */
  pollingUrl?: string
  /** 轮询间隔，默认 5s */
  pollingInterval?: number
}

export type WSStatus = 'connecting' | 'connected' | 'disconnected' | 'polling'

interface UseWebSocketReturn {
  connected: boolean
  status: WSStatus
  messages: WSMessage[]
  lastMessage: WSMessage | null
  send: (data: unknown) => void
  close: () => void
}

export function useWebSocket(url: string | null, options?: UseWebSocketOptions): UseWebSocketReturn {
  const silent = options?.silent ?? false
  const pollingIntervalMs = options?.pollingInterval ?? 5000
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const [status, setStatus] = useState<WSStatus>('disconnected')
  const [messages, setMessages] = useState<WSMessage[]>([])
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null)
  const lastMessageRef = useRef<WSMessage | null>(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 3
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const onReconnectRef = useRef(options?.onReconnect)

  // Keep onReconnect ref up-to-date
  useEffect(() => { onReconnectRef.current = options?.onReconnect }, [options?.onReconnect])

  const stopPollingFallback = useCallback(() => {
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current)
      pollingTimerRef.current = null
    }
  }, [])

  const startPollingFallback = useCallback(() => {
    if (!url) return
    stopPollingFallback()
    // 构造 HTTP URL：ws:// → http://, wss:// → https://；移除查询参数后重新附加 token
    let httpUrl = options?.pollingUrl
    if (!httpUrl) {
      if (url.startsWith('/')) {
        // 相对路径：使用与 ws 相同的 host
        httpUrl = `${window.location.origin}${url}`
      } else {
        httpUrl = url.replace(/^ws/, 'http').replace(/\?.*$/, '')
      }
    }
    // 附加 JWT token
    try {
      const token = localStorage.getItem('auth_token')
      if (token) {
        httpUrl += (httpUrl.includes('?') ? '&' : '?') + `token=${encodeURIComponent(token)}`
      }
    } catch { /* ignore */ }

    if (!silent) console.warn(`WebSocket fallback to polling: ${httpUrl} (every ${pollingIntervalMs}ms)`)
    setStatus('polling')

    pollingTimerRef.current = setInterval(async () => {
      try {
        const res = await fetch(httpUrl!, {
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) return
        const msg = (await res.json()) as WSMessage
        lastMessageRef.current = msg
        setLastMessage(msg)
        setMessages((prev) => [...prev, msg].slice(-100))
      } catch {
        // 静默忽略：后端可能未实现 HTTP 等价端点
      }
    }, pollingIntervalMs)
  }, [url, options?.pollingUrl, pollingIntervalMs, silent, stopPollingFallback])

  const connect = useCallback(() => {
    if (!url) return
    setStatus('connecting')
    try {
      // 将相对路径转换为完整的 ws:// URL
      let wsUrl = url
      if (url.startsWith('/')) {
        const envUrl = import.meta.env.VITE_WS_URL
        if (envUrl) {
          wsUrl = `${envUrl}${url}`
        } else {
          const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
          wsUrl = `${proto}//${window.location.host}${url}`
        }
      }
      // 附加 JWT token 以通过后端 WS 端点的 token 校验（后端 ?token= 查询参数）
      try {
        const token = localStorage.getItem('auth_token')
        if (token) {
          wsUrl += (wsUrl.includes('?') ? '&' : '?') + `token=${encodeURIComponent(token)}`
        }
      } catch { /* ignore localStorage access errors */ }
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        setStatus('connected')
        reconnectAttempts.current = 0
        // 恢复 WS 后停止轮询
        stopPollingFallback()
      }

      ws.onmessage = (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data)
          lastMessageRef.current = msg
          setLastMessage(msg)  // 触发 React 重渲染
          setMessages((prev) => [...prev, msg].slice(-100))
        } catch { /* ignore parse errors */ }
      }

      ws.onclose = () => {
        setConnected(false)
        // 不清空 messages / lastMessage，保留历史以便调用方继续使用
        reconnectAttempts.current += 1
        if (url && reconnectAttempts.current <= maxReconnectAttempts) {
          const delay = Math.pow(2, reconnectAttempts.current - 1) * 1000
          if (!silent) console.warn(`WebSocket disconnected, retrying in ${delay}ms (attempt ${reconnectAttempts.current}/${maxReconnectAttempts})`)
          reconnectTimerRef.current = setTimeout(() => {
            // Before reconnecting, notify listeners so they can rejoin
            if (onReconnectRef.current) {
              onReconnectRef.current(lastMessageRef.current?.timestamp ?? new Date().toISOString())
            }
            connect()
          }, delay)
        } else {
          if (!silent) console.warn(`WebSocket max reconnect attempts (${maxReconnectAttempts}) reached, falling back to polling`)
          setStatus('disconnected')
          // 触发降级到轮询
          startPollingFallback()
        }
      }

      ws.onerror = () => {
        if (!silent) console.warn('WebSocket connection error')
        ws.close()
      }
    } catch { /* ignore */ }
  }, [url, silent, startPollingFallback, stopPollingFallback])

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    } else if (status === 'polling') {
      // 轮询模式下 send 通过 HTTP POST 发送（若后端支持）
      // 当前不实现，仅静默忽略
      void data
    }
  }, [status])

  const close = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
    }
    stopPollingFallback()
    wsRef.current?.close()
    wsRef.current = null
    setConnected(false)
    setStatus('disconnected')
  }, [stopPollingFallback])

  useEffect(() => {
    connect()
    return () => {
      close()
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
    }
  }, [connect, close])

  return { connected, status, messages, lastMessage, send, close }
}
