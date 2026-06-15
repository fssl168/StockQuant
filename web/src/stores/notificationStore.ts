import { create } from 'zustand'

export interface NotificationItem {
  id: string
  type: 'signal' | 'alert' | 'info'
  title: string
  message: string
  time: string
}

interface NotificationState {
  notifications: NotificationItem[]
  add: (n: Omit<NotificationItem, 'id'>) => void
  clear: () => void
}

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [
    { id: '1', type: 'signal', title: '放量突破', message: 'sh600519 放量突破 1720', time: '09:45' },
    { id: '2', type: 'alert', title: 'MACD 死叉', message: 'sz000858 MACD 死叉，注意风险', time: '10:20' },
  ],
  add: (n) => set((st) => ({ notifications: [{ ...n, id: crypto.randomUUID() }, ...st.notifications] })),
  clear: () => set({ notifications: [] }),
}))
