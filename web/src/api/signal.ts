import client from './client'

export interface Signal {
  id: string
  symbol: string
  side: 'BUY' | 'SELL' | 'HOLD'
  source: string
  confidence: number
  reason: string
  price?: number
  quantity?: number
  timestamp: string
  priority: number
}

export interface SignalStats {
  active_count: number
  by_side: Record<string, number>
  by_source: Record<string, number>
}

export const signalApi = {
  list: (params?: { symbol?: string; side?: string; source?: string }) =>
    client.get('/signals', { params }),
  add: (data: { symbol: string; side: string; source?: string; confidence?: number; reason?: string; price?: number; quantity?: number }) =>
    client.post('/signals', data),
  remove: (id: string) =>
    client.delete(`/signals/${id}`),
  audit: (params?: { symbol?: string; limit?: number }) =>
    client.get('/signals/audit', { params }),
  stats: () =>
    client.get('/signals/stats'),
}
