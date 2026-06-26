import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import Backtest from '@/pages/Backtest'

vi.mock('react-router-dom', () => ({
  useNavigate: vi.fn(() => vi.fn()),
}))

vi.mock('@/stores/backtestStore', () => ({
  useBacktestStore: vi.fn((selector: any) => {
    const state = { submitTask: vi.fn(() => Promise.resolve({ taskId: 'test-1' })) }
    return selector ? selector(state) : state
  }),
}))

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: vi.fn((selector: any) => {
    const state = { add: vi.fn() }
    return selector ? selector(state) : state
  }),
}))

vi.mock('@monaco-editor/react', () => ({
  default: () => <div data-testid="monaco-editor" />,
}))

describe('Backtest Page', () => {
  it('should render page title', () => {
    render(<Backtest />)
    expect(screen.getByText('新回测')).toBeInTheDocument()
  })

  it('should render subtitle', () => {
    render(<Backtest />)
    expect(screen.getByText('配置策略参数，启动回测验证')).toBeInTheDocument()
  })

  it('should render strategy name input', () => {
    render(<Backtest />)
    expect(screen.getByText('策略名称')).toBeInTheDocument()
  })

  it('should render strategy template selector', () => {
    render(<Backtest />)
    expect(screen.getByText('策略模板')).toBeInTheDocument()
  })

  it('should render monaco editor', () => {
    render(<Backtest />)
    expect(screen.getByTestId('monaco-editor')).toBeInTheDocument()
  })

  it('should render date pickers', () => {
    render(<Backtest />)
    expect(screen.getByText('开始日期')).toBeInTheDocument()
    expect(screen.getByText('结束日期')).toBeInTheDocument()
  })

  it('should render run backtest button', () => {
    render(<Backtest />)
    expect(screen.getByRole('button', { name: /运行回测/ })).toBeInTheDocument()
  })

  it('should render initial capital input', () => {
    render(<Backtest />)
    expect(screen.getByText('初始资金')).toBeInTheDocument()
  })
})
