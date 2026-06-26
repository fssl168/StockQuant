import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import Monitor from '@/pages/Monitor'

vi.mock('@/stores/marketStore', () => {
  const state = {
    symbols: ['sh600519', 'sz000858', 'sh601318'],
    addSymbol: vi.fn(),
    removeSymbol: vi.fn(),
    addWatchlist: vi.fn(),
    clear: vi.fn(),
  }
  const useMarketStore = Object.assign(
    vi.fn((selector: any) => (selector ? selector(state) : state)),
    { getState: () => state }
  )
  return { useMarketStore }
})

vi.mock('@/stores/notificationStore', () => {
  const state = { notifications: [], add: vi.fn(), deleteNotification: vi.fn() }
  const useNotificationStore = Object.assign(
    vi.fn((selector: any) => (selector ? selector(state) : state)),
    { getState: () => state }
  )
  return { useNotificationStore }
})

vi.mock('@/api/monitor', () => ({
  monitorApi: {
    start: vi.fn(() => Promise.resolve()),
    stop: vi.fn(() => Promise.resolve()),
    status: vi.fn(() => Promise.resolve({ running: false })),
    brief: vi.fn(() => Promise.resolve('')), // brief returns a string, not an object
    getWatchlist: vi.fn(() => Promise.resolve(['sh600519', 'sz000858', 'sh601318'])),
    updateWatchlist: vi.fn(() => Promise.resolve(['sh600519', 'sz000858', 'sh601318'])),
    removeFromWatchlist: vi.fn(() => Promise.resolve()),
    scan: vi.fn(() => Promise.resolve({ signals: [] })),
    summary: vi.fn(() => Promise.resolve({ total: 0, triggered: 0 })),
  },
}))

vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: vi.fn(() => ({ messages: [], connected: false })),
}))

vi.mock('@/api/data', () => ({
  dataApi: {
    health: vi.fn(() => Promise.resolve({ status: 'ok' })),
  },
}))

vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({})),
  },
}))

describe('Monitor Page', () => {
  it('should render page title', () => {
    render(<Monitor />)
    expect(screen.getByText('实时盯盘')).toBeInTheDocument()
  })

  it('should render subtitle', () => {
    render(<Monitor />)
    expect(screen.getByText('自选股管理与实时信号扫描')).toBeInTheDocument()
  })

  it('should render watchlist section', () => {
    render(<Monitor />)
    expect(screen.getByText('自选股列表')).toBeInTheDocument()
  })

  it('should render stock symbol input', () => {
    render(<Monitor />)
    expect(screen.getByPlaceholderText('输入股票代码 (e.g. sh600519)')).toBeInTheDocument()
  })

  it('should render add button', () => {
    render(<Monitor />)
    expect(screen.getByRole('button', { name: /添加/ })).toBeInTheDocument()
  })

  it('should render scan control section', () => {
    render(<Monitor />)
    expect(screen.getByText('扫描控制')).toBeInTheDocument()
  })

  it('should render alert rules section', () => {
    render(<Monitor />)
    expect(screen.getByText('告警规则')).toBeInTheDocument()
  })

  it('should render alert switches and inputs', () => {
    render(<Monitor />)
    expect(screen.getByText('涨跌幅超限提醒')).toBeInTheDocument()
    expect(screen.getByText('成交量异常检测')).toBeInTheDocument()
  })

  it('should render recent signals section', () => {
    render(<Monitor />)
    expect(screen.getByText('最近信号')).toBeInTheDocument()
  })
})
