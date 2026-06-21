import client from './client'
import { Order, OrderSide, OrderType, AccountInfo, Position, TradeRecord } from '../types'

// ── Trading API ──────────────────────────────────────────────
// All endpoints call the real backend. No mock data.

export async function getAccount(): Promise<AccountInfo> {
  return client.get<AccountInfo>('/api/trading/account') as any
}

export async function getOrders(): Promise<Order[]> {
  return client.get<Order[]>('/api/trading/orders') as any
}

export async function placeOrder(req: {
  symbol: string
  side: OrderSide
  type: OrderType
  price: number
  quantity: number
}): Promise<Order> {
  return client.post<Order>('/api/trading/order', req) as any
}

export async function cancelOrder(orderId: string): Promise<Record<string, unknown>> {
  return client.delete(`/api/trading/order/${orderId}`) as any
}

export async function getPositions(): Promise<Position[]> {
  return client.get<Position[]>('/api/trading/positions') as any
}

export async function getTrades(): Promise<TradeRecord[]> {
  return client.get<TradeRecord[]>('/api/trading/trades') as any
}
