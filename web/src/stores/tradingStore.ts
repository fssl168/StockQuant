import { create } from 'zustand'
import type { BrokerMode, Order, AccountInfo, Position, TradeRecord, OrderSide, OrderType } from '../types'
import * as tradingApi from '../api/trading'

interface TradingState {
  brokerMode: BrokerMode
  account: AccountInfo | null
  orders: Order[]
  positions: Position[]
  trades: TradeRecord[]
  loading: boolean
  placingOrder: boolean

  setBrokerMode: (m: BrokerMode) => void
  refreshAll: () => Promise<void>
  placeOrder: (req: { symbol: string; side: OrderSide; type: OrderType; price: number; quantity: number }) => Promise<void>
  cancelOrder: (id: string) => Promise<void>
}

export const useTradingStore = create<TradingState>((set, get) => ({
  brokerMode: 'paper',
  account: null,
  orders: [],
  positions: [],
  trades: [],
  loading: false,
  placingOrder: false,

  setBrokerMode: (m) => set({ brokerMode: m }),

  refreshAll: async () => {
    set({ loading: true })
    try {
      const [account, orders, positions, trades] = await Promise.all([
        tradingApi.getAccount(),
        tradingApi.getOrders(),
        tradingApi.getPositions(),
        tradingApi.getTrades(),
      ])
      set({ account, orders, positions, trades, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  placeOrder: async (req) => {
    const state = get()
    if (state.placingOrder) return
    set({ placingOrder: true })
    try {
      const newOrder = await tradingApi.placeOrder(req)
      set((s) => ({ orders: [newOrder, ...s.orders], placingOrder: false }))
      // Refresh account & positions after order
      const [account, positions] = await Promise.all([
        tradingApi.getAccount(),
        tradingApi.getPositions(),
      ])
      set({ account, positions })
    } catch {
      set({ placingOrder: false })
    }
  },

  cancelOrder: async (orderId) => {
    await tradingApi.cancelOrder(orderId)
    set((s) => ({
      orders: s.orders.map((o) =>
        o.id === orderId ? { ...o, status: 'CANCELLED' as const, updatedAt: new Date().toISOString() } : o,
      ),
    }))
  },
}))
