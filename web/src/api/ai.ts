import client from './client'

export const aiApi = {
  chat: (conversationId: string, message: string) =>
    client.post('/chat', { conversation_id: conversationId, message }) as Promise<{ reply: string }>,
  conversations: () => client.get('/chat/conversations') as Promise<string[]>,
  clear: (id: string) => client.delete(`/chat/${id}`) as Promise<void>,
}
