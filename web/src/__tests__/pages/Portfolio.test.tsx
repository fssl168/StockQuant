import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import Portfolio from '@/pages/Portfolio'

vi.mock('react-router-dom', () => ({
  useNavigate: vi.fn(() => vi.fn()),
}))

vi.mock('echarts-for-react', () => ({
  default: () => <div data-testid="echarts" />,
}))

vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn((url: string) => {
      // 持仓数据由 API 提供（已移除硬编码 mock），测试按路径返回样例持仓
      if (url === '/portfolio/positions') {
        return Promise.resolve([
          { symbol: 'sh600519', name: '贵州茅台', shares: 100, cost: 1700, price: 1750, pnl: 5000, pnlPct: 2.94, sector: '白酒' },
          { symbol: 'sz000858', name: '五粮液', shares: 200, cost: 160, price: 155, pnl: -1000, pnlPct: -3.12, sector: '白酒' },
        ])
      }
      return Promise.resolve(null)
    }),
  },
}))

describe('Portfolio Page', () => {
  it('should render page title after loading', async () => {
    render(<Portfolio />)
    await waitFor(() => {
      expect(screen.getByText('投资组合')).toBeInTheDocument()
    })
  })

  it('should render subtitle after loading', async () => {
    render(<Portfolio />)
    await waitFor(() => {
      expect(screen.getByText(/持仓汇总/)).toBeInTheDocument()
    })
  })

  it('should render summary cards after loading', async () => {
    render(<Portfolio />)
    await waitFor(() => {
      expect(screen.getByText('总市值')).toBeInTheDocument()
      expect(screen.getByText('总成本')).toBeInTheDocument()
      expect(screen.getByText('累计盈亏')).toBeInTheDocument()
      expect(screen.getByText('收益率')).toBeInTheDocument()
      expect(screen.getByText('持仓数')).toBeInTheDocument()
    })
  })

  it('should render position detail table after loading', async () => {
    render(<Portfolio />)
    await waitFor(() => {
      expect(screen.getByText('持仓明细')).toBeInTheDocument()
    })
  })

  it('should render industry distribution chart after loading', async () => {
    render(<Portfolio />)
    await waitFor(() => {
      expect(screen.getByText('行业分布')).toBeInTheDocument()
    })
  })

  it('should render PnL distribution chart after loading', async () => {
    render(<Portfolio />)
    await waitFor(() => {
      expect(screen.getByText('盈亏分布')).toBeInTheDocument()
    })
  })

  it('should render quick trade button after loading', async () => {
    render(<Portfolio />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /快捷交易/ })).toBeInTheDocument()
    })
  })

  it('should render position data in table after loading', async () => {
    render(<Portfolio />)
    await waitFor(() => {
      expect(screen.getByText('贵州茅台')).toBeInTheDocument()
      expect(screen.getByText('五粮液')).toBeInTheDocument()
    })
  })

  it('should show skeleton while loading', () => {
    render(<Portfolio />)
    // Skeleton should be visible initially
    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument()
  })
})
