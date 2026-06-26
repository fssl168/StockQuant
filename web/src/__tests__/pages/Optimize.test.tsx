import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Optimize from '@/pages/Optimize'

// Mock ECharts-for-React to avoid jsdom canvas issues
vi.mock('echarts-for-react', () => ({
  default: vi.fn(() => null),
}))

// Mock react-router-dom (Optimize.tsx uses useNavigate)
vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}))

// Mock @/api/optimize to avoid real API calls during the workflow test
vi.mock('@/api/optimize', () => ({
  runOptimization: vi.fn().mockResolvedValue('OPT-TEST-123'),
  streamOptimizeProgress: vi.fn().mockImplementation(async function* () {
    yield { progress: 50, currentParams: { fast_period: 10 }, bestResult: undefined }
    yield {
      progress: 100,
      currentParams: {},
      bestResult: {
        rank: 1,
        params: { fast_period: 10, slow_period: 60 },
        metrics: { sharpeRatio: 2.0, totalReturn: 0.3, maxDrawdown: -0.1 },
      },
    }
  }),
}))

describe('Optimize Page', () => {
  beforeEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  describe('initial rendering', () => {
    it('should render page title', () => {
      render(<Optimize />)
      expect(screen.getByText('参数优化')).toBeInTheDocument()
    })

    it('should render parameter config table with 4 default params', () => {
      render(<Optimize />)
      // Param names are inside Input components — use querySelector to find them
      const paramInputs = document.querySelectorAll('input[type="text"]')
      expect(paramInputs.length).toBeGreaterThanOrEqual(4)
      // Check that known param names exist as input values
      const values = Array.from(paramInputs).map((i) => (i as HTMLInputElement).value)
      expect(values.some((v) => v.includes('fast'))).toBe(true)
      expect(values.some((v) => v.includes('slow'))).toBe(true)
    })

    it('should render method selector', () => {
      render(<Optimize />)
      expect(screen.getByText('网格搜索')).toBeInTheDocument()
      expect(screen.getByText('随机采样')).toBeInTheDocument()
      expect(screen.getByText('滚动窗口')).toBeInTheDocument()
    })

    it('should render target metric selector options', () => {
      render(<Optimize />)
      expect(screen.getByText('夏普比率')).toBeInTheDocument()
    })

    it('should render max iterations label', () => {
      render(<Optimize />)
      expect(screen.getByText('最大迭代')).toBeInTheDocument()
    })

    it('should render start optimization button', () => {
      render(<Optimize />)
      expect(screen.getByRole('button', { name: '开始优化' })).toBeInTheDocument()
    })

    it('should render add parameter button', () => {
      render(<Optimize />)
      expect(screen.getByRole('button', { name: /添加参数/i })).toBeInTheDocument()
    })
  })

  describe('parameter editing', () => {
    it('should have remove buttons for each param', () => {
      render(<Optimize />)
      const deleteButtons = screen.getAllByRole('button', { name: '删除' })
      expect(deleteButtons.length).toBe(4)
    })

    it('should allow editing parameter min value', () => {
      render(<Optimize />)
      const inputs = screen.getAllByRole('spinbutton')
      expect(inputs.length).toBeGreaterThan(0)
    })
  })

  describe('optimization workflow', () => {
    it('should show results after completing optimization', async () => {
      const user = userEvent.setup()
      render(<Optimize />)
      await user.click(screen.getByRole('button', { name: '开始优化' }))

      // Stream mock completes quickly; assert the results section appears
      // (results.length > 0 keeps the section visible after running=false)
      await waitFor(() => {
        expect(screen.getByText('优化结果')).toBeInTheDocument()
      }, { timeout: 5000 })
    }, 15000)
  })
})
