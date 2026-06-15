import client from './client'

export const aiApi = {
  chat: (conversationId: string, message: string) =>
    client.post('/chat', { conversation_id: conversationId, message }) as Promise<{ reply: string }>,
  conversations: () => client.get('/chat/conversations') as Promise<string[]>,
  clear: (id: string) => client.delete(`/chat/${id}`) as Promise<void>,
}

export async function streamChat(conversationId: string, message: string): Promise<string> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, message }),
  })
  if (!res.ok || !res.body) throw new Error('Stream failed')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let fullText = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const chunk = decoder.decode(value, { stream: true })
    fullText += chunk
  }
  return fullText
}
