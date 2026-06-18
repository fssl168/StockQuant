import { create } from 'zustand'
import { aiApi } from '@/api/ai'

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
  isLoaded: boolean
  addMessage: (role: 'user' | 'assistant', content: string) => void
  createConversation: () => void
  switchConversation: (id: string) => Promise<void>
  init: () => Promise<void>
  clear: () => void
}

export const useAIStore = create<AIState>((set, get) => ({
  messages: [],
  conversations: [],
  activeConversationId: '',
  isLoaded: false,

  /** 初始化：先从 localStorage 快速恢复，再从后端同步 */
  init: async () => {
    // 1. 尝试从 localStorage 快速恢复
    try {
      const saved = localStorage.getItem('ai_state')
      if (saved) {
        const { conversations, activeConversationId } = JSON.parse(saved)
        if (Array.isArray(conversations) && conversations.length > 0 && activeConversationId) {
          set({ conversations, activeConversationId })
        }
      }
    } catch { /* ignore */ }

    // 2. 从后端同步会话列表
    let activeId = ''
    try {
      const data = await aiApi.getConversations()
      const convs: Conversation[] = (data.conversations || []).map((c: any) => {
        const createdAt = c.created_at ? new Date(c.created_at).getTime() : Date.now()
        return {
          id: c.id,
          title: c.title || '新对话',
          createdAt: isNaN(createdAt) ? Date.now() : createdAt,
          messageCount: c.message_count ?? 0,
        }
      })
      const state = get()
      activeId = state.activeConversationId || convs[0]?.id || ''
      set({ conversations: convs, activeConversationId: activeId || crypto.randomUUID(), isLoaded: true })
    } catch {
      const state = get()
      activeId = state.activeConversationId || ''
      set({ isLoaded: true, activeConversationId: activeId || crypto.randomUUID() })
    }

    // 3. 加载消息（无论成功失败都确保 activeConversationId 已设置）
    const finalId = get().activeConversationId
    if (finalId) {
      try {
        const msgData = await aiApi.getConversation(finalId)
        const msgs: Message[] = (msgData.messages || []).map((m: any) => {
          const ts = m.timestamp ? new Date(m.timestamp).getTime() : Date.now()
          return {
            role: m.role as 'user' | 'assistant',
            content: m.content,
            timestamp: isNaN(ts) ? Date.now() : ts,
          }
        })
        set({ messages: msgs })
      } catch { /* ignore */ }
    }
  },

  addMessage: (role, content) => {
    set((st) => {
      const newMessages = [...st.messages, { role, content, timestamp: Date.now() }]
      const convs = st.conversations.map((c) =>
        c.id === st.activeConversationId
          ? {
              ...c,
              messageCount: c.messageCount + 1,
              title: c.title || (role === 'user' ? content.slice(0, 20) : c.title),
            }
          : c
      )
      try {
        localStorage.setItem(
          'ai_state',
          JSON.stringify({ conversations: convs, activeConversationId: st.activeConversationId })
        )
      } catch { /* ignore */ }
      return { messages: newMessages, conversations: convs }
    })
    // 异步持久化到数据库（fire-and-forget，不阻塞 UI）
    const { activeConversationId } = get()
    if (activeConversationId) {
      aiApi.saveMessage(activeConversationId, role, content).catch(() => {
        /* ignore — 流式 API 已在后端保存，无需重复 */
      })
    }
  },

  createConversation: () => {
    const state = get()
    const newId = crypto.randomUUID()
    set({ activeConversationId: newId, messages: [], conversations: [...state.conversations] })
    try {
      localStorage.setItem(
        'ai_state',
        JSON.stringify({ conversations: state.conversations, activeConversationId: newId })
      )
    } catch { /* ignore */ }
  },

  switchConversation: async (id) => {
    const state = get()
    // 如果当前会话有消息但没有标题，用第一条消息作为标题
    const updatedConvs = state.conversations.map((c) =>
      c.id === state.activeConversationId && c.messageCount > 0 && !c.title
        ? { ...c, title: state.messages[0]?.content?.slice(0, 20) || '新对话' }
        : c
    )
    set({ activeConversationId: id, messages: [], conversations: updatedConvs })
    try {
      localStorage.setItem(
        'ai_state',
        JSON.stringify({ conversations: updatedConvs, activeConversationId: id })
      )
    } catch { /* ignore */ }

    // 从后端加载目标会话消息
    try {
      const msgData = await aiApi.getConversation(id)
      const msgs: Message[] = (msgData.messages || []).map((m: any) => {
        const ts = m.timestamp ? new Date(m.timestamp).getTime() : Date.now()
        return {
          role: m.role as 'user' | 'assistant',
          content: m.content,
          timestamp: isNaN(ts) ? Date.now() : ts,
        }
      })
      set({ messages: msgs })
    } catch { /* ignore */ }
  },

  clear: () => {
    const state = get()
    if (!state.activeConversationId) return

    // 乐观地将当前会话的 messageCount 归零（更新列表显示）
    const newId = crypto.randomUUID()
    const newConvs = [
      ...state.conversations.filter((c) => c.id !== state.activeConversationId),
      { id: newId, title: '新对话', createdAt: Date.now(), messageCount: 0 },
    ]

    set((_) => ({
      conversations: newConvs,
      activeConversationId: newId,
      messages: [],
    }))

    // 后端删除旧会话消息（fire-and-forget）
    aiApi.deleteConversation(state.activeConversationId).catch(() => { /* ignore */ })

    try {
      localStorage.setItem(
        'ai_state',
        JSON.stringify({ conversations: newConvs, activeConversationId: newId })
      )
    } catch { /* ignore */ }
  },
}))
