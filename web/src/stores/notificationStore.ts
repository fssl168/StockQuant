import { create } from 'zustand'
import client from '@/api/client'

export interface NotificationItem {
  id: string
  type: 'signal' | 'alert' | 'info'
  title: string
  message: string
  time: string
  read: boolean
}

interface NotificationState {
  notifications: NotificationItem[]
  add: (n: Omit<NotificationItem, 'id' | 'read'>) => void
  clear: () => void
  markRead: (id: string) => void
  deleteNotification: (id: string) => void
  fetchFromBackend: () => Promise<void>
}

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],
  add: (n) => {
    const notification = { ...n, id: crypto.randomUUID(), read: false }
    set((st) => ({ notifications: [notification, ...st.notifications] }))
  },
  clear: () => set({ notifications: [] }),
  markRead: (id: string) => {
    set((st) => ({
      notifications: st.notifications.map((n) => (n.id === id ? { ...n, read: true } : n)),
    }))
    client.put(`/notifications/${id}/read`).catch(() => {})
  },
  deleteNotification: (id: string) => {
    set((st) => ({
      notifications: st.notifications.filter((n) => n.id !== id),
    }))
    client.delete(`/notifications/${id}`).catch(() => {})
  },
  fetchFromBackend: async () => {
    try {
      const data = await client.get('/notifications') as any
      if (Array.isArray(data)) {
        set({ notifications: data })
      }
    } catch {
      // ignore, use empty array
    }
  },
}))

// 初始化时从后端加载通知（fire-and-forget，不阻塞渲染）
if (typeof window !== 'undefined') {
  setTimeout(() => {
    useNotificationStore.getState().fetchFromBackend().catch(() => {})
  }, 0)
}
