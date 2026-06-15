import { useEffect, useRef, useCallback, useState } from 'react'

interface UseSSEReturn {
  streaming: boolean
  text: string
  error: string | null
  start: (payload: Record<string, unknown>) => Promise<void>
  stop: () => void
}

export function useSSE(url: string, onMessage?: (chunk: string) => void): UseSSEReturn {
  const [streaming, setStreaming] = useState(false)
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const _start = useCallback(async (payload: Record<string, unknown>) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setStreaming(true)
    setText('')
    setError(null)

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let fullText = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        fullText += chunk
        setText(fullText)
        onMessage?.(chunk)
      }

      setStreaming(false)
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === 'AbortError') return
      setError(e instanceof Error ? e.message : 'SSE request failed')
      setStreaming(false)
    }
  }, [url, onMessage])

  const _stop = useCallback(() => {
    abortRef.current?.abort()
    setStreaming(false)
  }, [])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  return { streaming, text, error, start: _start, stop: _stop }
}
