import client from './client'

export const aiApi = {
  chat: (conversationId: string, message: string) =>
    client.post('/chat', { conversation_id: conversationId, message }) as Promise<{ reply: string }>,
  conversations: () => client.get('/chat/conversations') as Promise<string[]>,
  clear: (id: string) => client.delete(`/chat/${id}`) as Promise<void>,
}

export async function* streamChat(conversationId: string, message: string): AsyncGenerator<string> {
  const res = await fetch('/api/ai/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, message }),
  })
  if (!res.ok || !res.body) throw new Error('Stream failed')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6)
        if (data === '[DONE]') return
        yield data
      } else if (line.trim() && !line.startsWith(':')) {
        yield line
      }
    }
  }
  if (buffer.trim()) yield buffer
}

export async function analyzeBacktest(backtestId: string): Promise<{ insight: string }> {
  const { data } = await client.post(`/ai/analyze-backtest/${backtestId}`)
  return data as { insight: string }
}
