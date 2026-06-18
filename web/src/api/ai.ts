import client from './client'

export const aiApi = {
  chat: (conversationId: string, message: string) =>
    client.post('/chat', { conversation_id: conversationId, message }) as Promise<{ reply: string }>,
  conversations: () => client.get('/chat/conversations') as Promise<string[]>,
  clear: (id: string) => client.delete(`/chat/${id}`) as Promise<void>,
  getConversations: () =>
    client.get('/ai/conversations') as Promise<{
      conversations: { id: string; title: string; created_at: string; message_count: number }[]
    }>,
  getConversation: (id: string) =>
    client.get(`/ai/conversation/${id}`) as Promise<{
      conversation_id: string
      messages: { role: string; content: string; timestamp: string }[]
    }>,
  saveMessage: (conversationId: string, role: string, content: string) =>
    client.post(`/ai/conversation/${conversationId}/message`, { role, content }) as Promise<{
      saved: boolean
      id: number | null
    }>,
  deleteConversation: (id: string) =>
    client.delete(`/ai/conversation/${id}`) as Promise<{ cleared: boolean }>,
}

export async function* streamChat(
  conversationId: string,
  message: string,
  options?: { mode?: string },
): AsyncGenerator<string> {
  const res = await fetch('/api/ai/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      conversation_id: conversationId,
      message,
      mode: options?.mode,
    }),
  })
  if (!res.ok || !res.body) throw new Error('Stream failed')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const chunk = decoder.decode(value, { stream: true })
    yield chunk
  }
}

export async function analyzeBacktest(backtestId: string): Promise<{ insight: string }> {
  return await client.post(`/ai/analyze-backtest/${backtestId}`) as { insight: string }
}
