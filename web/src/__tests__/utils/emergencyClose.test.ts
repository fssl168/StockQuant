import { describe, it, expect, vi } from 'vitest'
import {
  emergencyCloseAll,
  type Position,
  type CloseResult,
} from '@/utils/emergencyClose'

// Mock the PlaceMarketOrderFn signature: returns { id } on success, throws on failure
type PlaceOrderFn = (order: {
  symbol: string
  side: 'SELL'
  type: 'MARKET'
  price: number
  quantity: number
}) => Promise<{ id: string }>

describe('emergencyCloseAll', () => {
  describe('empty input', () => {
    it('should return empty array when positions list is empty', async () => {
      const placeOrder = vi.fn() as unknown as PlaceOrderFn
      const results = await emergencyCloseAll([], placeOrder)
      expect(results).toEqual([])
      expect(placeOrder).not.toHaveBeenCalled()
    })
  })

  describe('single position', () => {
    it('should flatten a single position with one MARKET sell order', async () => {
      const placeOrder = vi.fn().mockResolvedValue({ id: 'ORD-1' }) as unknown as PlaceOrderFn
      const positions: Position[] = [
        { symbol: 'sh600519', shares: 100, price: 1700 },
      ]
      const results = await emergencyCloseAll(positions, placeOrder)

      expect(results).toHaveLength(1)
      expect(results[0]).toEqual<CloseResult>({
        symbol: 'sh600519',
        success: true,
        orderId: 'ORD-1',
      })
    })

    it('should submit order with side=SELL, type=MARKET, price=0, quantity=shares', async () => {
      const placeOrder = vi.fn().mockResolvedValue({ id: 'ORD-X' }) as unknown as PlaceOrderFn
      const positions: Position[] = [
        { symbol: 'sz000858', shares: 250, price: 150 },
      ]
      await emergencyCloseAll(positions, placeOrder)

      expect(placeOrder).toHaveBeenCalledTimes(1)
      expect(placeOrder).toHaveBeenCalledWith({
        symbol: 'sz000858',
        side: 'SELL',
        type: 'MARKET',
        price: 0,
        quantity: 250,
      })
    })

    it('should mark result as failed when placeMarketOrder throws Error', async () => {
      const placeOrder = vi.fn().mockRejectedValue(new Error('insufficient buying power')) as unknown as PlaceOrderFn
      const positions: Position[] = [
        { symbol: 'sh600519', shares: 100, price: 1700 },
      ]
      const results = await emergencyCloseAll(positions, placeOrder)

      expect(results).toHaveLength(1)
      expect(results[0]).toEqual<CloseResult>({
        symbol: 'sh600519',
        success: false,
        error: 'insufficient buying power',
      })
    })

    it('should fall back to generic error message for non-Error throws', async () => {
      const placeOrder = vi.fn().mockRejectedValue('string error') as unknown as PlaceOrderFn
      const positions: Position[] = [
        { symbol: 'sh600519', shares: 100, price: 1700 },
      ]
      const results = await emergencyCloseAll(positions, placeOrder)

      expect(results[0].success).toBe(false)
      expect(results[0].error).toBe('未知错误')
    })
  })

  describe('multiple positions', () => {
    it('should flatten all positions in order and collect results', async () => {
      const placeOrder = vi.fn()
        .mockResolvedValueOnce({ id: 'ORD-1' })
        .mockResolvedValueOnce({ id: 'ORD-2' })
        .mockResolvedValueOnce({ id: 'ORD-3' }) as unknown as PlaceOrderFn
      const positions: Position[] = [
        { symbol: 'sh600519', shares: 100, price: 1700 },
        { symbol: 'sz000858', shares: 200, price: 150 },
        { symbol: 'sh601318', shares: 300, price: 80 },
      ]
      const results = await emergencyCloseAll(positions, placeOrder)

      expect(results).toHaveLength(3)
      expect(results.map((r) => r.symbol)).toEqual([
        'sh600519',
        'sz000858',
        'sh601318',
      ])
      expect(results.every((r) => r.success)).toBe(true)
      expect(results.map((r) => r.orderId)).toEqual(['ORD-1', 'ORD-2', 'ORD-3'])
    })

    it('should continue with next position even if one fails', async () => {
      const placeOrder = vi.fn()
        .mockResolvedValueOnce({ id: 'ORD-1' })
        .mockRejectedValueOnce(new Error('market closed'))
        .mockResolvedValueOnce({ id: 'ORD-3' }) as unknown as PlaceOrderFn
      const positions: Position[] = [
        { symbol: 'AAA', shares: 100, price: 10 },
        { symbol: 'BBB', shares: 200, price: 20 },
        { symbol: 'CCC', shares: 300, price: 30 },
      ]
      const results = await emergencyCloseAll(positions, placeOrder)

      expect(results).toHaveLength(3)
      expect(results[0]).toMatchObject({ symbol: 'AAA', success: true, orderId: 'ORD-1' })
      expect(results[1]).toMatchObject({ symbol: 'BBB', success: false, error: 'market closed' })
      expect(results[2]).toMatchObject({ symbol: 'CCC', success: true, orderId: 'ORD-3' })
    })

    it('should execute positions sequentially (not in parallel)', async () => {
      const callOrder: string[] = []
      const placeOrder = vi.fn().mockImplementation(async (order: { symbol: string }) => {
        callOrder.push(`start-${order.symbol}`)
        await new Promise((r) => setTimeout(r, 10))
        callOrder.push(`end-${order.symbol}`)
        return { id: `ORD-${order.symbol}` }
      }) as unknown as PlaceOrderFn
      const positions: Position[] = [
        { symbol: 'A', shares: 1, price: 1 },
        { symbol: 'B', shares: 1, price: 1 },
        { symbol: 'C', shares: 1, price: 1 },
      ]
      await emergencyCloseAll(positions, placeOrder)

      // Sequential: each start-end pair is contiguous
      expect(callOrder).toEqual([
        'start-A', 'end-A',
        'start-B', 'end-B',
        'start-C', 'end-C',
      ])
    })

    it('should call placeMarketOrder exactly once per position', async () => {
      const placeOrder = vi.fn().mockResolvedValue({ id: 'ORD' }) as unknown as PlaceOrderFn
      const positions: Position[] = [
        { symbol: 'A', shares: 1, price: 1 },
        { symbol: 'B', shares: 1, price: 1 },
      ]
      await emergencyCloseAll(positions, placeOrder)
      expect(placeOrder).toHaveBeenCalledTimes(2)
    })
  })

  describe('result shape', () => {
    it('success result should NOT carry error field', async () => {
      const placeOrder = vi.fn().mockResolvedValue({ id: 'ORD-1' }) as unknown as PlaceOrderFn
      const results = await emergencyCloseAll(
        [{ symbol: 'X', shares: 1, price: 1 }],
        placeOrder,
      )
      expect(results[0].success).toBe(true)
      expect(results[0].error).toBeUndefined()
    })

    it('failure result should NOT carry orderId field', async () => {
      const placeOrder = vi.fn().mockRejectedValue(new Error('fail')) as unknown as PlaceOrderFn
      const results = await emergencyCloseAll(
        [{ symbol: 'X', shares: 1, price: 1 }],
        placeOrder,
      )
      expect(results[0].success).toBe(false)
      expect(results[0].orderId).toBeUndefined()
    })
  })
})
