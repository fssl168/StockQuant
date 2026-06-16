import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import Monitor from '@/pages/Monitor'

vi.mock('@/stores/marketStore', () => ({
  useMarketStore: vi.fn((selector: any) => {
    const state = {
      symbols: ['sh600519', 'sz000858', 'sh601318'],
      addSymbol: vi.fn(),
      removeSymbol: vi.fn(),
      clear: vi.fn(),
    }
    return selector ? selector(state) : state
  }),
}))

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: vi.fn((selector: any) => {
    const state = { notifications: [], add: vi.fn() }
    return selector ? selector(state) : state
  }),
}))

vi.mock('@/api/monitor', () => ({
  monitorApi: {
    start: vi.fn(() => Promise.resolve()),
    stop: vi.fn(() => Promise.resolve()),
    status: vi.fn(() => Promise.resolve({ running: false })),
    brief: vi.fn(() => Promise.resolve({ brief: '' })),
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
