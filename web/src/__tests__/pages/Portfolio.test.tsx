import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import Portfolio from '@/pages/Portfolio'

vi.mock('react-router-dom', () => ({
  useNavigate: vi.fn(() => vi.fn()),
}))

vi.mock('echarts-for-react', () => ({
  default: () => <div data-testid="echarts" />,
}))

describe('Portfolio Page', () => {
  it('should render page title', () => {
    render(<Portfolio />)
    expect(screen.getByText('投资组合')).toBeInTheDocument()
  })

  it('should render subtitle', () => {
    render(<Portfolio />)
    expect(screen.getByText('持仓汇总与盈亏分析')).toBeInTheDocument()
  })

  it('should render summary cards', () => {
    render(<Portfolio />)
    expect(screen.getByText('总市值')).toBeInTheDocument()
    expect(screen.getByText('总成本')).toBeInTheDocument()
    expect(screen.getByText('累计盈亏')).toBeInTheDocument()
    expect(screen.getByText('收益率')).toBeInTheDocument()
    expect(screen.getByText('持仓数')).toBeInTheDocument()
  })

  it('should render position detail table', () => {
    render(<Portfolio />)
    expect(screen.getByText('持仓明细')).toBeInTheDocument()
  })

  it('should render industry distribution chart', () => {
    render(<Portfolio />)
    expect(screen.getByText('行业分布')).toBeInTheDocument()
  })

  it('should render PnL distribution chart', () => {
    render(<Portfolio />)
    expect(screen.getByText('盈亏分布')).toBeInTheDocument()
  })

  it('should render quick trade button', () => {
    render(<Portfolio />)
    expect(screen.getByRole('button', { name: /快捷交易/ })).toBeInTheDocument()
  })

  it('should render position data in table', () => {
    render(<Portfolio />)
    expect(screen.getByText('贵州茅台')).toBeInTheDocument()
    expect(screen.getByText('五粮液')).toBeInTheDocument()
  })
})
