# -*- coding: utf-8 -*-
"""React Query Hooks - 统一管理服务端状态"""

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import client from '@/api/client'
import type { Strategy, BacktestTask, KlineData, MarketQuote, Position, Order } from '@/types'

// ============ Strategy Hooks ============

export function useStrategies() {
  return useQuery({
    queryKey: ['strategies'],
    queryFn: async () => {
      const { data } = await client.get<Strategy[]>('/api/strategies')
      return data
    },
  })
}

export function useStrategy(id: string) {
  return useQuery({
    queryKey: ['strategy', id],
    queryFn: async () => {
      const { data } = await client.get<Strategy>(`/api/strategies/${id}`)
      return data
    },
    enabled: !!id,
  })
}

export function useCreateStrategy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (strategy: Partial<Strategy>) => {
      const { data } = await client.post<Strategy>('/api/strategies', strategy)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] })
    },
  })
}

export function useUpdateStrategy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...strategy }: Partial<Strategy> & { id: string }) => {
      const { data } = await client.put<Strategy>(`/api/strategies/${id}`, strategy)
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] })
      queryClient.invalidateQueries({ queryKey: ['strategy', variables.id] })
    },
  })
}

export function useDeleteStrategy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await client.delete(`/api/strategies/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] })
    },
  })
}

// ============ Backtest Hooks ============

export function useBacktestTasks() {
  return useQuery({
    queryKey: ['backtest-tasks'],
    queryFn: async () => {
      const { data } = await client.get<BacktestTask[]>('/api/backtest/tasks')
      return data
    },
    refetchInterval: 5000, // 每5秒轮询任务状态
  })
}

export function useBacktestResult(taskId: string) {
  return useQuery({
    queryKey: ['backtest-result', taskId],
    queryFn: async () => {
      const { data } = await client.get(`/api/backtest/result/${taskId}`)
      return data
    },
    enabled: !!taskId,
    refetchInterval: 3000, // 轮询结果
  })
}

export function useRunBacktest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (config: Record<string, unknown>) => {
      const { data } = await client.post<{ task_id: string }>('/api/backtest/run', config)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backtest-tasks'] })
    },
  })
}

// ============ Market Data Hooks ============

export function useKlineData(symbol: string, timeframe: string = '1d', limit: number = 100) {
  return useQuery({
    queryKey: ['kline', symbol, timeframe, limit],
    queryFn: async () => {
      const { data } = await client.get<KlineData[]>(`/api/data/kline/${symbol}`, {
        params: { timeframe, limit },
      })
      return data
    },
    enabled: !!symbol,
    staleTime: 60000, // 行情数据1分钟内视为新鲜
  })
}

export function useMarketQuote(symbol: string) {
  return useQuery({
    queryKey: ['quote', symbol],
    queryFn: async () => {
      const { data } = await client.get<MarketQuote>(`/api/data/quote/${symbol}`)
      return data
    },
    enabled: !!symbol,
    refetchInterval: 5000, // 5秒刷新报价
  })
}

// ============ Trading Hooks ============

export function usePositions() {
  return useQuery({
    queryKey: ['positions'],
    queryFn: async () => {
      const { data } = await client.get<Position[]>('/api/trading/positions')
      return data
    },
    refetchInterval: 10000, // 10秒刷新持仓
  })
}

export function useOrders(status?: string) {
  return useQuery({
    queryKey: ['orders', status],
    queryFn: async () => {
      const { data } = await client.get<Order[]>('/api/trading/orders', {
        params: status ? { status } : undefined,
      })
      return data
    },
    refetchInterval: 5000, // 5秒刷新订单
  })
}

export function usePlaceOrder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (order: { symbol: string; side: string; type: string; price: number; quantity: number }) => {
      const { data } = await client.post('/api/trading/order', order)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      queryClient.invalidateQueries({ queryKey: ['positions'] })
    },
  })
}

export function useCancelOrder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (orderId: string) => {
      await client.delete(`/api/trading/order/${orderId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    },
  })
}

// ============ Dashboard Hooks ============

export function useDashboardStats() {
  return useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: async () => {
      const { data } = await client.get('/api/dashboard/stats')
      return data
    },
    refetchInterval: 30000, // 30秒刷新
  })
}

// ============ Settings Hooks ============

export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      const { data } = await client.get('/api/settings')
      return data
    },
  })
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (settings: Record<string, unknown>) => {
      await client.put('/api/settings', settings)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}
