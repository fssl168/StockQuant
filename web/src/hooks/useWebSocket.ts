import { useEffect, useRef, useCallback, useState } from 'react'

export interface WSMessage {
  type: string
  task_id?: string
  data: unknown
  timestamp: string
}

interface UseWebSocketReturn {
  connected: boolean
  messages: WSMessage[]
  lastMessage: WSMessage | null
  send: (data: unknown) => void
  close: () => void
}

export function useWebSocket(url: string | null): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const [messages, setMessages] = useState<WSMessage[]>([])
  const lastMessageRef = useRef<WSMessage | null>(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 5
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (!url) return
    try {
      // 将相对路径转换为完整的 ws:// URL
      let wsUrl = url
      if (url.startsWith('/')) {
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        wsUrl = `${proto}//${window.location.host}${url}`
      }
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
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
        if (url && reconnectAttempts.current < maxReconnectAttempts) {
          reconnectTimerRef.current = setTimeout(connect, 1000 * reconnectAttempts.current)
        }
      }

      ws.onerror = () => {
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

  return { connected, messages, lastMessage: lastMessageRef.current, send, close }
}
