import client from './client'
import { Order, OrderSide, OrderType, AccountInfo, Position, TradeRecord } from '../types'

// ── Trading API ──────────────────────────────────────────────
// All endpoints call the real backend. No mock data.

export async function getAccount(): Promise<AccountInfo> {
  return client.get<AccountInfo>('/trading/account') as any
}

export async function getOrders(): Promise<Order[]> {
  return client.get<Order[]>('/trading/orders') as any
}

export async function placeOrder(req: {
  symbol: string
  side: OrderSide
  type: OrderType
  price: number
  quantity: number
}): Promise<Order> {
  return client.post<Order>('/trading/order', req) as any
}

export async function cancelOrder(orderId: string): Promise<Record<string, unknown>> {
  return client.delete(`/trading/order/${orderId}`) as any
}

export async function getPositions(): Promise<Position[]> {
  return client.get<Position[]>('/trading/positions') as any
}

export async function getTrades(): Promise<TradeRecord[]> {
  return client.get<TradeRecord[]>('/trading/trades') as any
}
