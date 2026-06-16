import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import Dashboard from '@/pages/Dashboard'

vi.mock('@/api/dashboard', () => ({
  dashboardApi: {
    metrics: vi.fn(() => Promise.resolve({ metrics: {} })),
    signals: vi.fn(() => Promise.resolve([])),
    recentBacktests: vi.fn(() => Promise.resolve([])),
  },
}))

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: vi.fn((selector: any) => {
    const state = { notifications: [] }
    return selector ? selector(state) : state
  }),
}))

vi.mock('@/components/Chart/EquityChart', () => ({
  default: () => <div data-testid="equity-chart" />,
}))

describe('Dashboard Page', () => {
  it('should render page title', () => {
    render(<Dashboard />)
    expect(screen.getByText('系统概览')).toBeInTheDocument()
  })

  it('should render metric cards', () => {
    render(<Dashboard />)
    expect(screen.getByText('总权益')).toBeInTheDocument()
    expect(screen.getByText('今日盈亏')).toBeInTheDocument()
    expect(screen.getByText('持仓数')).toBeInTheDocument()
  })

  it('should render annualized return metric', () => {
    render(<Dashboard />)
    expect(screen.getByText('年化收益')).toBeInTheDocument()
  })

  it('should render max drawdown metric', () => {
    render(<Dashboard />)
    expect(screen.getByText('最大回撤')).toBeInTheDocument()
  })

  it('should render sharpe ratio metric', () => {
    render(<Dashboard />)
    expect(screen.getByText('夏普比率')).toBeInTheDocument()
  })

  it('should render equity chart after loading', async () => {
    render(<Dashboard />)
    expect(await screen.findByTestId('equity-chart')).toBeInTheDocument()
  })

  it('should render AI signals section', () => {
    render(<Dashboard />)
    expect(screen.getByText('AI 信号')).toBeInTheDocument()
  })

  it('should render backtest history section', () => {
    render(<Dashboard />)
    expect(screen.getByText('回测历史')).toBeInTheDocument()
  })
})
