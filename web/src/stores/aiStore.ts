import { create } from 'zustand'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

interface AIState {
  messages: Message[]
  conversationId: string
  addMessage: (role: 'user' | 'assistant', content: string) => void
  setConversationId: (id: string) => void
  clear: () => void
}

export const useAIStore = create<AIState>((set) => ({
  messages: [],
  conversationId: crypto.randomUUID(),
  addMessage: (role, content) =>
    set((st) => ({
      messages: [...st.messages, { role, content, timestamp: Date.now() }],
    })),
  setConversationId: (id) => set({ conversationId: id, messages: [] }),
  clear: () => set({ messages: [], conversationId: crypto.randomUUID() }),
}))
