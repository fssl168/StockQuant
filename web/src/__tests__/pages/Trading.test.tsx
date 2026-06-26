import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import Trading from '@/pages/Trading'
import { useTradingStore } from '@/stores/tradingStore'

vi.mock('@/stores/tradingStore', () => ({
  useTradingStore: vi.fn(),
}))

describe('Trading Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    const mockCancelOrder = vi.fn().mockResolvedValue(undefined)
    const mockPlaceOrder = vi.fn().mockResolvedValue(undefined)
    const mockRefreshAll = vi.fn().mockResolvedValue(undefined)
    const mockSetBrokerMode = vi.fn()

    const commonState = {
      account: {
        totalEquity: 1234567,
        cash: 456789,
        frozenCash: 12000,
        marketValue: 777778,
        availableCash: 444789,
        dailyPnl: 12345,
        dailyPnlPct: 1.02,
      },
      orders: [
        {
          id: 'ORD-101',
          symbol: 'sh600519',
          side: 'BUY',
          type: 'LIMIT',
          price: 1720,
          quantity: 100,
          filledQty: 100,
          filledAvgPrice: 1720.5,
          status: 'FILLED',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      ],
      positions: [
        { symbol: 'sh600519', name: '贵州茅台', shares: 100, cost: 1680, price: 1725.5, pnl: 4550, pnlPct: 2.71 },
      ],
      trades: [],
      loading: false,
      placingOrder: false,
      setBrokerMode: mockSetBrokerMode,
      refreshAll: mockRefreshAll,
      placeOrder: mockPlaceOrder,
      cancelOrder: mockCancelOrder,
    }

    ;(useTradingStore as unknown as ReturnType<typeof vi.fn>).mockImplementation((selector) => {
      const src = selector.toString()
      // Check setBrokerMode BEFORE brokerMode — 'setBrokerMode' contains the substring 'brokerMode'
      if (src.includes('setBrokerMode')) return commonState.setBrokerMode
      if (src.includes('brokerMode')) return 'paper'
      if (src.includes('account')) return commonState.account
      if (src.includes('orders')) return commonState.orders
      if (src.includes('positions')) return commonState.positions
      if (src.includes('trades')) return commonState.trades
      if (src.includes('loading')) return commonState.loading
      if (src.includes('placingOrder')) return commonState.placingOrder
      if (src.includes('refreshAll')) return commonState.refreshAll
      if (src.includes('placeOrder')) return commonState.placeOrder
      if (src.includes('cancelOrder')) return commonState.cancelOrder
      return undefined
    })
  })

  describe('rendering', () => {
    it('should render page title', () => {
      render(<Trading />)
      expect(screen.getByText('交易执行')).toBeInTheDocument()
    })

    it('should render account info labels', () => {
      render(<Trading />)
      expect(screen.getByText('总权益')).toBeInTheDocument()
      expect(screen.getByText('可用资金')).toBeInTheDocument()
      expect(screen.getByText('持仓市值')).toBeInTheDocument()
      expect(screen.getByText('今日盈亏')).toBeInTheDocument()
    })

    it('should render Paper/Live mode toggle', () => {
      render(<Trading />)
      expect(screen.getByText('模拟盘')).toBeInTheDocument()
      expect(screen.getByText('实盘')).toBeInTheDocument()
    })

    it('should render Order Form panel', () => {
      render(<Trading />)
      expect(screen.getByText('股票代码')).toBeInTheDocument()
    })

    it('should render Position Panel', () => {
      render(<Trading />)
      expect(screen.getByText('当前持仓')).toBeInTheDocument()
    })

    it('should render Order Book table', () => {
      render(<Trading />)
      expect(screen.getByText('订单簿')).toBeInTheDocument()
    })
  })

  describe('Order form interaction', () => {
    it('should render stock symbol input', () => {
      render(<Trading />)
      const input = screen.getByPlaceholderText('e.g. sh600519') as HTMLInputElement
      expect(input).toBeInTheDocument()
    })

    it('should have BUY and SELL radio buttons', () => {
      render(<Trading />)
      expect(screen.getByRole('radio', { name: '买入' })).toBeInTheDocument()
      expect(screen.getByRole('radio', { name: '卖出' })).toBeInTheDocument()
    })

    it('should render direction and type labels', () => {
      render(<Trading />)
      // Use query to check these exist without erroring on duplicates
      const allText = document.body.textContent
      expect(allText).toContain('方向')
      expect(allText).toContain('类型')
    })

    it('should show estimated amount label', () => {
      render(<Trading />)
      expect(screen.getByText('预估金额')).toBeInTheDocument()
    })

    it('should render buy/sell button', () => {
      render(<Trading />)
      const buyButton = screen.getByRole('button', { name: /买入/ })
      expect(buyButton).toBeInTheDocument()
    })
  })

  describe('Live mode warning', () => {
    it('should NOT show warning alert in paper mode', () => {
      render(<Trading />)
      const alert = screen.queryByText(/实盘交易模式/)
      expect(alert).not.toBeInTheDocument()
    })
  })
})
