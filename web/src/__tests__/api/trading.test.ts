import { describe, it, expect } from 'vitest'
import * as tradingApi from '@/api/trading'
import type { Order, OrderSide, OrderType, Position, TradeRecord } from '@/types'

describe('Trading API', () => {
  describe('getAccount()', () => {
    it('should return AccountInfo with correct structure', async () => {
      const account = await tradingApi.getAccount()
      expect(account).toHaveProperty('totalEquity')
      expect(account).toHaveProperty('availableCash')
      expect(account).toHaveProperty('positionValue')
      expect(account).toHaveProperty('todayPnl')
      expect(account).toHaveProperty('brokerMode')
    })

    it('should have positive total_equity', async () => {
      const account = await tradingApi.getAccount()
      expect(account.totalEquity).toBeGreaterThan(0)
    })
  })

  describe('getOrders()', () => {
    it('should return array of orders', async () => {
      const orders = await tradingApi.getOrders()
      expect(Array.isArray(orders)).toBe(true)
    })

    it('each order should have required fields', async () => {
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
      const order = await tradingApi.placeOrder({
        symbol: 'sh600519',
        side: 'BUY' as OrderSide,
        type: 'LIMIT' as OrderType,
        price: 1700,
        quantity: 100,
      })
      expect(order).toHaveProperty('orderId')
      expect(order.symbol).toBe('sh600519')
      expect(order.side).toBe('BUY')
      expect(order.status).toBe('SUBMITTED')
    })

    it('should reject zero quantity', async () => {
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
      const order = await tradingApi.placeOrder({
        symbol: 'sh600519',
        side: 'BUY' as OrderSide,
        type: 'LIMIT' as OrderType,
        price: 1700,
        quantity: 100,
      })
      expect(order.status).toBe('SUBMITTED')
      await tradingApi.cancelOrder((order as any).order_id)
      const updatedOrders = await tradingApi.getOrders()
      const updated = updatedOrders.find((o: Order) => (o as any).order_id === (order as any).order_id)
      expect(updated!.status).toBe('CANCELLED')
    })

    it('should NOT cancel a CANCELLED order', async () => {
      const order = await tradingApi.placeOrder({
        symbol: 'sh600519',
        side: 'BUY' as OrderSide,
        type: 'LIMIT' as OrderType,
        price: 1800,
        quantity: 100,
      })
      await tradingApi.cancelOrder((order as any).order_id)
      await expect(tradingApi.cancelOrder((order as any).order_id)).rejects.toThrow()
    })
  })

  describe('getPositions()', () => {
    it('should return array of positions', async () => {
      const positions = await tradingApi.getPositions()
      expect(Array.isArray(positions)).toBe(true)
    })

    it('each position should have required fields', async () => {
      const positions = await tradingApi.getPositions()
      positions.forEach((p: Position) => {
        expect(p).toHaveProperty('symbol')
        expect(p).toHaveProperty('shares')
      })
    })
  })

  describe('getTrades()', () => {
    it('should return array of trade records', async () => {
      const trades = await tradingApi.getTrades()
      expect(Array.isArray(trades)).toBe(true)
    })

    it('each trade should have required fields', async () => {
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
