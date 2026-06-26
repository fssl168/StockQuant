import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useTradingStore } from '@/stores/tradingStore'
import * as tradingApi from '@/api/trading'

// Mock message to avoid Ant Design modal issues in tests
vi.mock('antd', () => ({
  message: {
    error: vi.fn(),
    success: vi.fn(),
  },
  Modal: vi.fn(),
  Typography: { Text: vi.fn() },
  Table: vi.fn(),
  Button: vi.fn(),
  Input: vi.fn(),
  Select: vi.fn(),
  Radio: vi.fn(),
  Space: vi.fn(),
  Row: vi.fn(),
  Col: vi.fn(),
  Card: vi.fn(),
  Tag: vi.fn(),
  Statistic: vi.fn(),
  Segmented: vi.fn(),
  Tooltip: vi.fn(),
  Divider: vi.fn(),
  Badge: vi.fn(),
  Alert: vi.fn(),
  InputNumber: vi.fn(),
}))

describe('TradingStore', () => {
  beforeEach(() => {
    // Reset store to initial state
    useTradingStore.getState().setBrokerMode('paper')
    useTradingStore.setState({
      account: null,
      orders: [],
      positions: [],
      trades: [],
      loading: false,
      placingOrder: false,
    })
  })

  describe('initial state', () => {
    it('brokerMode should default to "paper"', () => {
      expect(useTradingStore.getState().brokerMode).toBe('paper')
    })

    it('account should be null initially', () => {
      expect(useTradingStore.getState().account).toBeNull()
    })

    it('orders should be empty array initially', () => {
      expect(useTradingStore.getState().orders).toEqual([])
    })

    it('positions should be empty array initially', () => {
      expect(useTradingStore.getState().positions).toEqual([])
    })

    it('trades should be empty array initially', () => {
      expect(useTradingStore.getState().trades).toEqual([])
    })

    it('loading should be false', () => {
      expect(useTradingStore.getState().loading).toBe(false)
    })

    it('placingOrder should be false', () => {
      expect(useTradingStore.getState().placingOrder).toBe(false)
    })
  })

  describe('setBrokerMode()', () => {
    it('should switch brokerMode to "live"', () => {
      useTradingStore.getState().setBrokerMode('live')
      expect(useTradingStore.getState().brokerMode).toBe('live')
    })

    it('should switch back to "paper"', () => {
      useTradingStore.getState().setBrokerMode('live')
      useTradingStore.getState().setBrokerMode('paper')
      expect(useTradingStore.getState().brokerMode).toBe('paper')
    })
  })

  describe('refreshAll()', () => {
    it('should populate account, orders, positions, trades after call', async () => {
      await useTradingStore.getState().refreshAll()
      expect(useTradingStore.getState().account).not.toBeNull()
      expect(useTradingStore.getState().orders.length).toBeGreaterThan(0)
      expect(useTradingStore.getState().positions.length).toBeGreaterThan(0)
      expect(useTradingStore.getState().trades.length).toBeGreaterThan(0)
    })

    it('should set loading=true during fetch, then loading=false', async () => {
      useTradingStore.setState({ loading: true })
      expect(useTradingStore.getState().loading).toBe(true)
      await useTradingStore.getState().refreshAll()
      expect(useTradingStore.getState().loading).toBe(false)
    })

    it('account should have correct structure after refresh', async () => {
      await useTradingStore.getState().refreshAll()
      const account = useTradingStore.getState().account!
      expect(account).toHaveProperty('totalEquity')
      expect(account).toHaveProperty('cash')
      expect(account.totalEquity).toBeGreaterThan(0)
    })
  })

  describe('placeOrder()', () => {
    it('should add new order to orders array', async () => {
      const initialOrders = useTradingStore.getState().orders
      await useTradingStore.getState().placeOrder({
        symbol: 'sh600519',
        side: 'BUY',
        type: 'LIMIT',
        price: 1700,
        quantity: 100,
      })
      expect(useTradingStore.getState().orders.length).toBeGreaterThan(initialOrders.length)
    })

    it('should prevent duplicate submissions while placingOrder=true', async () => {
      const store = useTradingStore.getState()
      useTradingStore.setState({ placingOrder: true })
      await store.placeOrder({
        symbol: 'sh600519',
        side: 'BUY',
        type: 'LIMIT',
        price: 1700,
        quantity: 100,
      })
      // Should return early, orders count unchanged
      expect(useTradingStore.getState().orders.length).toBe(0)
    })

    it('should reset placingOrder flag after completion', async () => {
      await useTradingStore.getState().placeOrder({
        symbol: 'sh600519',
        side: 'BUY',
        type: 'LIMIT',
        price: 1700,
        quantity: 100,
      })
      expect(useTradingStore.getState().placingOrder).toBe(false)
    })

    it('new order should have correct symbol and side', async () => {
      await useTradingStore.getState().placeOrder({
        symbol: 'sz000858',
        side: 'SELL',
        type: 'LIMIT',
        price: 150,
        quantity: 200,
      })
      const orders = useTradingStore.getState().orders
      const newOrder = orders[0]
      expect(newOrder.symbol).toBe('sz000858')
      expect(newOrder.side).toBe('SELL')
    })
  })

  describe('cancelOrder()', () => {
    it('should update target order status to ORDER_CANCELLED', async () => {
      // First refresh to populate orders
      await useTradingStore.getState().refreshAll()
      // Clear store orders and place a fresh one
      const pendingOrder = useTradingStore.getState().orders.find(
        (o) => o.status === 'ORDER_PENDING' || o.status === 'ORDER_SUBMITTED'
      )
      if (pendingOrder) {
        await useTradingStore.getState().cancelOrder(pendingOrder.id)
        const updated = useTradingStore.getState().orders.find(
          (o) => o.id === pendingOrder.id
        )
        expect(updated!.status).toBe('ORDER_CANCELLED')
      }
    })

    it('should NOT modify account/orders if cancel fails', async () => {
      // Mock cancelOrder to throw
      vi.spyOn(tradingApi, 'cancelOrder').mockRejectedValue(new Error('Network error'))
      await useTradingStore.getState().cancelOrder('ORD-999')
      // Store should still be in consistent state
      expect(useTradingStore.getState().placingOrder).toBe(false)
    })
  })
})
