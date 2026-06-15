import { create } from 'zustand'

export interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export interface Conversation {
  id: string
  title: string
  createdAt: number
  messageCount: number
}

interface AIState {
  messages: Message[]
  conversations: Conversation[]
  activeConversationId: string
  addMessage: (role: 'user' | 'assistant', content: string) => void
  setConversationId: (id: string) => void
  clear: () => void
  createConversation: () => void
  switchConversation: (id: string) => void
}

export const useAIStore = create<AIState>((set, get) => ({
  messages: [],
  conversations: [],
  activeConversationId: crypto.randomUUID(),
  addMessage: (role, content) =>
    set((st) => ({
      messages: [...st.messages, { role, content, timestamp: Date.now() }],
      conversations: st.conversations.map((c) =>
        c.id === st.activeConversationId ? { ...c, messageCount: c.messageCount + 1, title: c.title || (role === 'user' ? content.slice(0, 20) : c.title) } : c
      ),
    })),
  setConversationId: (id) => set({ activeConversationId: id, messages: [] }),
  clear: () => {
    const state = get()
    if (!state.conversations.find((c) => c.id === state.activeConversationId)) {
      set({
        conversations: [
          ...state.conversations,
          {
            id: state.activeConversationId,
            title: state.messages[0]?.content?.slice(0, 20) ?? '新对话',
            createdAt: Date.now(),
            messageCount: state.messages.length,
          },
        ],
      })
    }
    const newId = crypto.randomUUID()
    set({ activeConversationId: newId, messages: [], conversations: [...get().conversations] })
  },
  createConversation: () => {
    const state = get()
    // Save current conversation if it has messages
    if (state.messages.length > 0 && !state.conversations.find((c) => c.id === state.activeConversationId)) {
      set({
        conversations: [
          ...state.conversations,
          {
            id: state.activeConversationId,
            title: state.messages[0]?.content?.slice(0, 20) ?? '新对话',
            createdAt: Date.now(),
            messageCount: state.messages.length,
          },
        ],
      })
    }
    const newId = crypto.randomUUID()
    set({ activeConversationId: newId, messages: [] })
  },
  switchConversation: (id) => {
    const state = get()
    // Save current conversation before switching
    if (state.messages.length > 0 && !state.conversations.find((c) => c.id === state.activeConversationId)) {
      set({
        conversations: [
          ...state.conversations,
          {
            id: state.activeConversationId,
            title: state.messages[0]?.content?.slice(0, 20) ?? '新对话',
            createdAt: Date.now(),
            messageCount: state.messages.length,
          },
        ],
      })
    }
    set({ activeConversationId: id, messages: [], conversations: state.conversations })
    // Note: messages are cleared on switch; in a real app they'd be loaded from history
  },
}))
