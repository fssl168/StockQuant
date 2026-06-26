import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

import client from '@/api/client'
import * as tradingApi from '@/api/trading'
import type { Order, OrderSide, OrderType, Position, TradeRecord } from '@/types'

describe('Trading API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getAccount()', () => {
    it('should return AccountInfo with correct structure', async () => {
      const mockAccount = {
        totalEquity: 1000000,
        availableCash: 500000,
        positionValue: 500000,
        todayPnl: 10000,
        brokerMode: 'paper',
      }
      vi.mocked(client.get).mockResolvedValueOnce(mockAccount)
      const account = await tradingApi.getAccount()
      expect(client.get).toHaveBeenCalledWith('/api/trading/account')
      expect(account).toHaveProperty('totalEquity')
      expect(account).toHaveProperty('availableCash')
      expect(account).toHaveProperty('positionValue')
      expect(account).toHaveProperty('todayPnl')
      expect(account).toHaveProperty('brokerMode')
    })

    it('should have positive total_equity', async () => {
      vi.mocked(client.get).mockResolvedValueOnce({ totalEquity: 1000000 })
      const account = await tradingApi.getAccount()
      expect(account.totalEquity).toBeGreaterThan(0)
    })
  })

  describe('getOrders()', () => {
    it('should return array of orders', async () => {
      vi.mocked(client.get).mockResolvedValueOnce([])
      const orders = await tradingApi.getOrders()
      expect(client.get).toHaveBeenCalledWith('/api/trading/orders')
      expect(Array.isArray(orders)).toBe(true)
    })

    it('each order should have required fields', async () => {
      const mockOrders = [
        { orderId: '1', symbol: 'sh600519', side: 'BUY', status: 'SUBMITTED' },
      ]
      vi.mocked(client.get).mockResolvedValueOnce(mockOrders)
      const orders = await tradingApi.getOrders()
      orders.forEach((o: Order) => {
        expect(o).toHaveProperty('orderId')
        expect(o).toHaveProperty('symbol')
        expect(o).toHaveProperty('side')
        expect(o).toHaveProperty('status')
      })
    })
  })

  describe('placeOrder()', () => {
    it('should create a new order with SUBMITTED status for LIMIT', async () => {
      const mockOrder = {
        orderId: '1',
        symbol: 'sh600519',
        side: 'BUY',
        status: 'SUBMITTED',
      }
      vi.mocked(client.post).mockResolvedValueOnce(mockOrder)
      const order = await tradingApi.placeOrder({
        symbol: 'sh600519',
        side: 'BUY' as OrderSide,
        type: 'LIMIT' as OrderType,
        price: 1700,
        quantity: 100,
      })
      expect(client.post).toHaveBeenCalledWith('/api/trading/order', expect.objectContaining({
        symbol: 'sh600519',
        side: 'BUY',
        type: 'LIMIT',
        price: 1700,
        quantity: 100,
      }))
      expect(order).toHaveProperty('orderId')
      expect((order as any).symbol).toBe('sh600519')
      expect((order as any).side).toBe('BUY')
      expect((order as any).status).toBe('SUBMITTED')
    })

    it('should reject zero quantity', async () => {
      vi.mocked(client.post).mockRejectedValueOnce(new Error('Invalid quantity'))
      await expect(
        tradingApi.placeOrder({
          symbol: 'sh600519',
          side: 'BUY' as OrderSide,
          type: 'LIMIT' as OrderType,
          price: 1700,
          quantity: 0,
        })
      ).rejects.toThrow()
    })

    it('should reject missing symbol', async () => {
      vi.mocked(client.post).mockRejectedValueOnce(new Error('Invalid symbol'))
      await expect(
        tradingApi.placeOrder({
          symbol: '',
          side: 'BUY' as OrderSide,
          type: 'LIMIT' as OrderType,
          price: 1700,
          quantity: 100,
        })
      ).rejects.toThrow()
    })
  })

  describe('cancelOrder()', () => {
    it('should cancel a SUBMITTED order', async () => {
      // place order first
      vi.mocked(client.post).mockResolvedValueOnce({
        orderId: '1',
        symbol: 'sh600519',
        side: 'BUY',
        status: 'SUBMITTED',
      })
      const order = await tradingApi.placeOrder({
        symbol: 'sh600519',
        side: 'BUY' as OrderSide,
        type: 'LIMIT' as OrderType,
        price: 1700,
        quantity: 100,
      })
      expect((order as any).status).toBe('SUBMITTED')

      // cancel order
      vi.mocked(client.delete).mockResolvedValueOnce({})
      await tradingApi.cancelOrder((order as any).orderId)
      expect(client.delete).toHaveBeenCalledWith('/api/trading/order/1')

      // verify cancelled
      vi.mocked(client.get).mockResolvedValueOnce([
        { orderId: '1', symbol: 'sh600519', side: 'BUY', status: 'CANCELLED' },
      ])
      const updatedOrders = await tradingApi.getOrders()
      const updated = updatedOrders.find((o: Order) => (o as any).orderId === (order as any).orderId)
      expect(updated!.status).toBe('CANCELLED')
    })

    it('should NOT cancel a CANCELLED order', async () => {
      // place order
      vi.mocked(client.post).mockResolvedValueOnce({
        orderId: '1',
        symbol: 'sh600519',
        side: 'BUY',
        status: 'SUBMITTED',
      })
      const order = await tradingApi.placeOrder({
        symbol: 'sh600519',
        side: 'BUY' as OrderSide,
        type: 'LIMIT' as OrderType,
        price: 1800,
        quantity: 100,
      })

      // first cancel succeeds
      vi.mocked(client.delete).mockResolvedValueOnce({})
      await tradingApi.cancelOrder((order as any).orderId)

      // second cancel fails
      vi.mocked(client.delete).mockRejectedValueOnce(new Error('Order already cancelled'))
      await expect(tradingApi.cancelOrder((order as any).orderId)).rejects.toThrow()
    })
  })

  describe('getPositions()', () => {
    it('should return array of positions', async () => {
      vi.mocked(client.get).mockResolvedValueOnce([])
      const positions = await tradingApi.getPositions()
      expect(client.get).toHaveBeenCalledWith('/api/trading/positions')
      expect(Array.isArray(positions)).toBe(true)
    })

    it('each position should have required fields', async () => {
      const mockPositions = [{ symbol: 'sh600519', shares: 100 }]
      vi.mocked(client.get).mockResolvedValueOnce(mockPositions)
      const positions = await tradingApi.getPositions()
      positions.forEach((p: Position) => {
        expect(p).toHaveProperty('symbol')
        expect(p).toHaveProperty('shares')
      })
    })
  })

  describe('getTrades()', () => {
    it('should return array of trade records', async () => {
      vi.mocked(client.get).mockResolvedValueOnce([])
      const trades = await tradingApi.getTrades()
      expect(client.get).toHaveBeenCalledWith('/api/trading/trades')
      expect(Array.isArray(trades)).toBe(true)
    })

    it('each trade should have required fields', async () => {
      const mockTrades = [
        { tradeId: '1', orderId: '1', symbol: 'sh600519', price: 1700 },
      ]
      vi.mocked(client.get).mockResolvedValueOnce(mockTrades)
      const trades = await tradingApi.getTrades()
      trades.forEach((t: TradeRecord) => {
        expect(t).toHaveProperty('tradeId')
        expect(t).toHaveProperty('orderId')
        expect(t).toHaveProperty('symbol')
        expect(t).toHaveProperty('price')
      })
    })
  })
})
