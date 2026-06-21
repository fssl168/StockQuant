import client from './client'

export const aiApi = {
  chat: (conversationId: string, message: string) =>
    client.post('/api/ai/chat', { conversation_id: conversationId, message }) as Promise<{ reply: string }>,
  conversations: () => client.get('/api/ai/conversations') as Promise<string[]>,
  clear: (id: string) => client.delete(`/api/ai/conversation/${id}`) as Promise<void>,
  getConversations: () =>
    client.get('/api/ai/conversations') as Promise<{
      conversations: { id: string; title: string; created_at: string; message_count: number }[]
    }>,
  getConversation: (id: string) => client.get(`/api/ai/conversation/${id}`) as Promise<{
      conversation_id: string
      messages: { role: string; content: string; timestamp: string }[]
    }>,
  saveMessage: (conversationId: string, role: string, content: string) =>
    client.post(`/api/ai/conversation/${conversationId}/message`, { role, content }) as Promise<{
      saved: boolean
      id: number | null
    }>,
  deleteConversation: (id: string) =>
    client.delete(`/api/ai/conversation/${id}`) as Promise<{ cleared: boolean }>,
}

export async function* streamChat(
  conversationId: string,
  message: string,
  options?: { mode?: string },
): AsyncGenerator<string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch('/api/ai/chat', {
    method: 'POST',
    headers,
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

export interface StructuredInsight {
  summary: string
  overfitRisk: string | null
  alphaDecomposition: string | null
  suggestions: string[]
}

export async function analyzeBacktest(backtestId: string): Promise<{ insight: string | StructuredInsight }> {
  return await client.post(`/api/ai/analyze-backtest/${backtestId}`) as { insight: string | StructuredInsight }
}
