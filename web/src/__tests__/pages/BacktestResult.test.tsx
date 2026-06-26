import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import BacktestResult from '@/pages/BacktestResult'

vi.mock('react-router-dom', () => ({
  useParams: vi.fn(() => ({ id: 'test-backtest-id' })),
  Link: ({ children }: any) => <a>{children}</a>,
}))

vi.mock('@/api/dashboard', () => ({
  backtestApi: {
    get: vi.fn(() =>
      Promise.resolve({
        taskId: 'test-backtest-id',
        strategyName: 'Test Strategy',
        status: 'completed',
        metrics: {
          'Annualized Return': 0.15,
          'Max Drawdown': -0.08,
          'Sharpe Ratio': 1.2,
          'Sortino Ratio': 1.5,
          'Calmar Ratio': 1.8,
          'Win Rate': 0.6,
          'Total Trades': 42,
          'SQN (System Quality Number)': 2.1,
        },
        equityCurve: [1000000, 1050000, 1020000, 1080000],
        trades: [],
        error: null,
      })
    ),
  },
}))

vi.mock('@/api/ai', () => ({
  analyzeBacktest: vi.fn(() => Promise.resolve({ insight: 'Test AI insight' })),
}))

vi.mock('@/components/Chart/EquityChart', () => ({
  default: () => <div data-testid="equity-chart" />,
}))

vi.mock('@/components/Chart/DrawdownChart', () => ({
  default: () => <div data-testid="drawdown-chart" />,
}))

vi.mock('@/components/Chart/MonthHeatmap', () => ({
  default: () => <div data-testid="month-heatmap" />,
}))

vi.mock('@/components/Table/MetricTable', () => ({
  default: () => <div data-testid="metric-table" />,
}))

describe('BacktestResult Page', () => {
  it('should render back button', async () => {
    render(<BacktestResult />)
    expect(await screen.findByText('返回')).toBeInTheDocument()
  })

  it('should render equity curve section', async () => {
    render(<BacktestResult />)
    expect(await screen.findByTestId('equity-chart')).toBeInTheDocument()
  })

  it('should render drawdown chart section', async () => {
    render(<BacktestResult />)
    expect(await screen.findByTestId('drawdown-chart')).toBeInTheDocument()
  })

  it('should render monthly returns section', async () => {
    render(<BacktestResult />)
    expect(await screen.findByTestId('month-heatmap')).toBeInTheDocument()
  })

  it('should render full metrics table', async () => {
    render(<BacktestResult />)
    expect(await screen.findByTestId('metric-table')).toBeInTheDocument()
  })

  it('should render trade details section', async () => {
    render(<BacktestResult />)
    expect(await screen.findByText('交易明细')).toBeInTheDocument()
  })

  it('should render AI insight section', async () => {
    render(<BacktestResult />)
    expect(await screen.findByText('AI 解读')).toBeInTheDocument()
  })

  it('should render generate AI insight button', async () => {
    render(<BacktestResult />)
    expect(await screen.findByText('生成 AI 解读')).toBeInTheDocument()
  })
})
