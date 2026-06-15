import { describe, it, expect, beforeEach } from 'vitest'
import * as tradingApi from '@/api/trading'
import type { Order, OrderSide, OrderType, Position, TradeRecord } from '@/types'

describe('Trading API', () => {
  beforeEach(() => {
    tradingApi.__resetSeed?.()
  })

  describe('getAccount()', () => {
    it('should return AccountInfo with correct structure', async () => {
      const account = await tradingApi.getAccount()
      expect(account).toHaveProperty('totalEquity')
      expect(account).toHaveProperty('cash')
      expect(account).toHaveProperty('frozenCash')
      expect(account).toHaveProperty('marketValue')
      expect(account).toHaveProperty('availableCash')
      expect(account).toHaveProperty('dailyPnl')
      expect(account).toHaveProperty('dailyPnlPct')
    })

    it('should have positive totalEquity', async () => {
      const account = await tradingApi.getAccount()
      expect(account.totalEquity).toBeGreaterThan(0)
    })

    it('should resolve within expected time', async () => {
      const start = Date.now()
      await tradingApi.getAccount()
      const elapsed = Date.now() - start
      expect(elapsed).toBeGreaterThanOrEqual(400)
      expect(elapsed).toBeLessThan(2000)
    })

    it('cash should be less than totalEquity', async () => {
      const account = await tradingApi.getAccount()
      expect(account.cash).toBeLessThan(account.totalEquity)
    })

    it('marketValue + cash should equal totalEquity approximately', async () => {
      const account = await tradingApi.getAccount()
      const diff = Math.abs(account.cash + account.marketValue - account.totalEquity)
      expect(diff).toBeLessThan(1) // Allow small floating-point tolerance
    })
  })

  describe('getOrders()', () => {
    it('should return array of Order objects', async () => {
      const orders = await tradingApi.getOrders()
      expect(Array.isArray(orders)).toBe(true)
      expect(orders.length).toBeGreaterThan(0)
    })

    it('each order should have required fields', async () => {
      const orders = await tradingApi.getOrders()
      orders.forEach((o: Order) => {
        expect(o).toHaveProperty('id')
        expect(o).toHaveProperty('symbol')
        expect(o).toHaveProperty('side')
        expect(o).toHaveProperty('type')
        expect(o).toHaveProperty('price')
        expect(o).toHaveProperty('quantity')
        expect(o).toHaveProperty('status')
      })
    })

    it('should include mixed status orders', async () => {
      const orders = await tradingApi.getOrders()
      const statuses = orders.map((o: Order) => o.status)
      expect(statuses).toContain('FILLED')
    })

    it('order IDs should be unique', async () => {
      const orders = await tradingApi.getOrders()
      const ids = orders.map((o: Order) => o.id)
      expect(new Set(ids).size).toBe(ids.length)
    })
  })

  describe('placeOrder()', () => {
    it('should add new order to orders list with SUBMITTED status for LIMIT', async () => {
      const order = await tradingApi.placeOrder({
        symbol: 'sh600519',
        side: 'BUY' as OrderSide,
        type: 'LIMIT' as OrderType,
        price: 1700,
        quantity: 100,
      })
      expect(order).toHaveProperty('id')
      expect(order.symbol).toBe('sh600519')
      expect(order.side).toBe('BUY')
      expect(order.status).toBe('SUBMITTED')
    })

    it('MARKET order should auto-fill and get FILLED status', async () => {
      const order = await tradingApi.placeOrder({
        symbol: 'sz000858',
        side: 'BUY' as OrderSide,
        type: 'MARKET' as OrderType,
        price: 150,
        quantity: 200,
      })
      expect(order.type).toBe('MARKET')
      expect(order.filledQty).toBe(200)
      expect(order.status).toBe('FILLED')
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
      ).rejects.toThrow('数量必须大于0')
    })

    it('should reject negative price', async () => {
      await expect(
        tradingApi.placeOrder({
          symbol: 'sh600519',
          side: 'BUY' as OrderSide,
          type: 'LIMIT' as OrderType,
          price: -10,
          quantity: 100,
        })
      ).rejects.toThrow('价格必须大于0')
    })

    it('SELL order should have correct side', async () => {
      const order = await tradingApi.placeOrder({
        symbol: 'sh600519',
        side: 'SELL' as OrderSide,
        type: 'LIMIT' as OrderType,
        price: 1800,
        quantity: 100,
      })
      expect(order.side).toBe('SELL')
      expect(order.status).toBe('SUBMITTED')
    })
  })

  describe('cancelOrder()', () => {
    it('should cancel a PENDING order', async () => {
      const orders = await tradingApi.getOrders()
      const pendingOrder = orders.find((o: Order) => o.status === 'PENDING')
      if (pendingOrder) {
        await tradingApi.cancelOrder(pendingOrder.id)
        const updatedOrders = await tradingApi.getOrders()
        const updated = updatedOrders.find((o: Order) => o.id === pendingOrder.id)
        expect(updated!.status).toBe('CANCELLED')
      }
    })

    it('should cancel a SUBMITTED order', async () => {
      const order = await tradingApi.placeOrder({
        symbol: 'sh600519',
        side: 'BUY' as OrderSide,
        type: 'LIMIT' as OrderType,
        price: 1700,
        quantity: 100,
      })
      expect(order.status).toBe('SUBMITTED')
      await tradingApi.cancelOrder(order.id)
      const updatedOrders = await tradingApi.getOrders()
      const updated = updatedOrders.find((o: Order) => o.id === order.id)
      expect(updated!.status).toBe('CANCELLED')
    })

    it('should NOT modify FILLED order status', async () => {
      const orders = await tradingApi.getOrders()
      const filledOrder = orders.find((o: Order) => o.status === 'FILLED')
      if (filledOrder) {
        const initialId = filledOrder.id
        await tradingApi.cancelOrder(filledOrder.id)
        const updatedOrders = await tradingApi.getOrders()
        const updated = updatedOrders.find((o: Order) => o.id === initialId)
        expect(updated!.status).toBe('FILLED')
      }
    })

    it('should NOT modify CANCELLED order status', async () => {
      const orders = await tradingApi.getOrders()
      const cancelledOrder = orders.find((o: Order) => o.status === 'CANCELLED')
      if (cancelledOrder) {
        await tradingApi.cancelOrder(cancelledOrder.id)
        const updatedOrders = await tradingApi.getOrders()
        const updated = updatedOrders.find((o: Order) => o.id === cancelledOrder.id)
        expect(updated!.status).toBe('CANCELLED')
      }
    })
  })

  describe('getPositions()', () => {
    it('should return array of Position objects', async () => {
      const positions = await tradingApi.getPositions()
      expect(Array.isArray(positions)).toBe(true)
      expect(positions.length).toBe(3)
    })

    it('each position should have required fields', async () => {
      const positions = await tradingApi.getPositions()
      positions.forEach((p: Position) => {
        expect(p).toHaveProperty('symbol')
        expect(p).toHaveProperty('shares')
        expect(p).toHaveProperty('pnl')
        expect(p).toHaveProperty('pnlPct')
      })
    })
  })

  describe('getTrades()', () => {
    it('should return array of TradeRecord objects', async () => {
      const trades = await tradingApi.getTrades()
      expect(Array.isArray(trades)).toBe(true)
      expect(trades.length).toBeGreaterThan(0)
    })

    it('each trade should have required fields', async () => {
      const trades = await tradingApi.getTrades()
      trades.forEach((t: TradeRecord) => {
        expect(t).toHaveProperty('id')
        expect(t).toHaveProperty('orderId')
        expect(t).toHaveProperty('symbol')
        expect(t).toHaveProperty('price')
        expect(t).toHaveProperty('timestamp')
      })
    })
  })
})
