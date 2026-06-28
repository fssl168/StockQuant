import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import client from '@/api/client'
import type {
  ConditionalOrderStatus,
  ConditionalOrderCondition,
  ConditionalOrderAction,
  ConditionalOrder,
} from '@/types/alert'

// re-export 以保持现有引用兼容（`from '@/stores/conditionalOrderStore'`）
export type {
  ConditionalOrderStatus,
  ConditionalOrderCondition,
  ConditionalOrderAction,
  ConditionalOrder,
}

interface ConditionalOrderState {
  orders: ConditionalOrder[]
  loading: boolean
  fetchOrders: () => Promise<void>
  createOrder: (data: Omit<ConditionalOrder, 'id' | 'status' | 'createdAt' | 'updatedAt'>) => Promise<void>
  updateOrder: (id: string, data: Partial<Omit<ConditionalOrder, 'id' | 'createdAt' | 'updatedAt'>>) => Promise<void>
  cancelOrder: (id: string) => Promise<void>
  deleteOrder: (id: string) => Promise<void>
}

export const useConditionalOrderStore = create<ConditionalOrderState>()(
  persist(
    (set, get) => ({
      orders: [],
      loading: false,

      fetchOrders: async () => {
        set({ loading: true })
        try {
          const res = await client.get('/api/conditional-orders') as any
          set({ orders: Array.isArray(res) ? res : [], loading: false })
        } catch {
          set({ loading: false })
        }
      },

      createOrder: async (data) => {
        await client.post('/api/conditional-orders', data)
        await get().fetchOrders()
      },

      updateOrder: async (id, data) => {
        await client.put(`/api/conditional-orders/${id}`, data)
        await get().fetchOrders()
      },

      cancelOrder: async (id) => {
        await client.post(`/api/conditional-orders/${id}/cancel`)
        await get().fetchOrders()
      },

      deleteOrder: async (id) => {
        await client.delete(`/api/conditional-orders/${id}`)
        await get().fetchOrders()
      },
    }),
    {
      name: 'stockquant-conditional-orders',
      version: 1,
    }
  )
)
