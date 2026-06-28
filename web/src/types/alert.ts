export { type AlertRule } from '@/stores/alertStore'

export type AlertType = 'price' | 'depth_change' | 'index_correlation' | 'sector_correlation'
export type NotifyChannel = 'dingtalk' | 'email' | 'telegram' | 'sound' | 'browser'

export type ConditionalOrderStatus = 'active' | 'triggered' | 'expired' | 'cancelled'

export interface ConditionalOrderCondition {
  id: string
  field: 'price' | 'volume' | 'indicator' | 'time'
  operator: 'gt' | 'lt' | 'gte' | 'lte' | 'cross_above' | 'cross_below'
  value: number | string
  label?: string
}

export interface ConditionalOrderAction {
  side: 'BUY' | 'SELL'
  quantity: number
  orderType: 'MARKET' | 'LIMIT'
  limitOffset?: number
}

export interface ConditionalOrderTemplate {
  id: string
  name: string
  conditions: Omit<ConditionalOrderCondition, 'id'>[]
  action: ConditionalOrderAction
  description?: string
}

export interface ConditionalOrder {
  id: string
  name: string
  type: 'breakout_buy' | 'pullback_sell'
  symbol: string
  conditions: ConditionalOrderCondition[]
  logic: 'AND' | 'OR'
  action: ConditionalOrderAction
  status: ConditionalOrderStatus
  validUntil?: string
  templateId?: string
  createdAt: string
  updatedAt: string
  triggeredAt?: string
}
