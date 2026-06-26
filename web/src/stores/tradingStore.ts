import { create } from 'zustand'
import type { BrokerMode, Order, AccountInfo, Position, TradeRecord, OrderSide, OrderType, OrderStatus } from '../types'
import * as tradingApi from '../api/trading'
import { message } from 'antd'

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
      set({ account, orders: orders ?? [], positions: positions ?? [], trades: trades ?? [], loading: false })
    } catch (err) {
      console.warn('[tradingStore] refreshAll skipped (paper trading, no live data):', err)
      set({ orders: [], positions: [], trades: [], loading: false })
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
    } catch (err) {
      console.error('[tradingStore] placeOrder failed:', err)
      message.error('下单失败，请重试')
      set({ placingOrder: false })
    }
  },

  cancelOrder: async (orderId) => {
    try {
      await tradingApi.cancelOrder(orderId)
    } catch (err) {
      console.error('[tradingStore] cancelOrder failed:', err)
      message.error('撤单失败')
      return
    }
    set((s) => ({
      orders: s.orders.map((o) =>
        o.id === orderId ? { ...o, status: 'ORDER_CANCELLED' as OrderStatus, updatedAt: new Date().toISOString() } : o,
      ),
    }))
  },
}))
