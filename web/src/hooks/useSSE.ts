import { useEffect, useRef, useCallback, useState } from "react"

export interface SSEEvent {
  type: "token" | "error" | "done"
  content?: string
}

interface UseSSEReturn {
  streaming: boolean
  text: string
  error: string | null
  events: SSEEvent[]
  start: (payload: Record<string, unknown>) => Promise<void>
  stop: () => void
}

export function useSSE(url: string, onEvent?: (event: SSEEvent) => void): UseSSEReturn {
  const [streaming, setStreaming] = useState(false)
  const [text, setText] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [events, setEvents] = useState<SSEEvent[]>([])
  const abortRef = useRef<AbortController | null>(null)

  const _start = useCallback(async (payload: Record<string, unknown>) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setStreaming(true)
    setText("")
    setError(null)
    setEvents([])

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body?.getReader()
      if (!reader) throw new Error("No response body")

      const decoder = new TextDecoder()
      let buffer = ""
      let fullText = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() ?? ""

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const jsonStr = line.slice(6)
            try {
              const event = JSON.parse(jsonStr) as SSEEvent
              if (event.type === "token") {
                fullText += event.content ?? ""
                setText(fullText)
              } else if (event.type === "error") {
                setError(event.content ?? "Unknown error")
              }
              setEvents((prev) => [...prev, event])
              onEvent?.(event)
            } catch {
              // skip unparseable SSE data
            }
          }
        }
      }

      setStreaming(false)
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") return
      setError(e instanceof Error ? e.message : "SSE request failed")
      setStreaming(false)
    }
  }, [url, onEvent])

  const _stop = useCallback(() => {
    abortRef.current?.abort()
    setStreaming(false)
  }, [])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  return { streaming, text, error, events, start: _start, stop: _stop }
}
