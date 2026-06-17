import { useEffect, useRef, useCallback, useState } from 'react'

export interface WSMessage {
  type: string
  task_id?: string
  data: unknown
  timestamp: string
}

interface UseWebSocketOptions {
  /** When true, suppress all console.warn on connection failures */
  silent?: boolean
}

interface UseWebSocketReturn {
  connected: boolean
  status: 'connecting' | 'connected' | 'disconnected'
  messages: WSMessage[]
  lastMessage: WSMessage | null
  send: (data: unknown) => void
  close: () => void
}

export function useWebSocket(url: string | null, options?: UseWebSocketOptions): UseWebSocketReturn {
  const silent = options?.silent ?? false
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected')
  const [messages, setMessages] = useState<WSMessage[]>([])
  const lastMessageRef = useRef<WSMessage | null>(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 3
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        setStatus('connected')
        reconnectAttempts.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data)
          lastMessageRef.current = msg
          setMessages((prev) => [...prev, msg].slice(-100))
        } catch { /* ignore parse errors */ }
      }

      ws.onclose = () => {
        setConnected(false)
        lastMessageRef.current = null
        setMessages([])
        reconnectAttempts.current += 1
        if (url && reconnectAttempts.current <= maxReconnectAttempts) {
          // 指数退避: 1s → 2s → 4s
          const delay = Math.pow(2, reconnectAttempts.current - 1) * 1000
          if (!silent) console.warn(`WebSocket disconnected, retrying in ${delay}ms (attempt ${reconnectAttempts.current}/${maxReconnectAttempts})`)
          reconnectTimerRef.current = setTimeout(connect, delay)
        } else if (!silent) {
          console.warn(`WebSocket max reconnect attempts (${maxReconnectAttempts}) reached, giving up`)
          setStatus('disconnected')
        }
      }

      ws.onerror = () => {
        if (!silent) console.warn('WebSocket connection error')
        ws.close()
      }
    } catch { /* ignore */ }
  }, [url])

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  const close = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
    }
    wsRef.current?.close()
    wsRef.current = null
    setConnected(false)
    setStatus('disconnected')
  }, [])

  useEffect(() => {
    connect()
    return () => {
      close()
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
    }
  }, [connect, close])

  return { connected, status, messages, lastMessage: lastMessageRef.current, send, close }
}
