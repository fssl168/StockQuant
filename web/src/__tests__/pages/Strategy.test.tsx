import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import Strategy from '@/pages/Strategy'

vi.mock('@/stores/strategyStore', () => ({
  useStrategyStore: vi.fn((selector: any) => {
    const state = {
      strategies: [],
      loading: false,
      fetchStrategies: vi.fn(),
      createStrategy: vi.fn(),
      deleteStrategy: vi.fn(),
      updateStrategy: vi.fn(),
    }
    return selector ? selector(state) : state
  }),
  // Also mock the static getState for handleSave
}))

vi.mock('@monaco-editor/react', () => ({
  default: () => <div data-testid="monaco-editor" />,
}))

describe('Strategy Page', () => {
  it('should render page title', () => {
    render(<Strategy />)
    expect(screen.getByText('策略管理')).toBeInTheDocument()
  })

  it('should render strategy editor section', () => {
    render(<Strategy />)
    expect(screen.getByText('策略编辑器')).toBeInTheDocument()
  })

  it('should render monaco editor', () => {
    render(<Strategy />)
    expect(screen.getByTestId('monaco-editor')).toBeInTheDocument()
  })

  it('should render strategy list section', () => {
    render(<Strategy />)
    expect(screen.getByText(/策略列表/)).toBeInTheDocument()
  })

  it('should render create strategy button', () => {
    render(<Strategy />)
    expect(screen.getByRole('button', { name: /新建策略/ })).toBeInTheDocument()
  })

  it('should render template library button', () => {
    render(<Strategy />)
    expect(screen.getByRole('button', { name: /模板库/ })).toBeInTheDocument()
  })

  it('should render save button', () => {
    render(<Strategy />)
    expect(screen.getByRole('button', { name: /保存/ })).toBeInTheDocument()
  })

  it('should render syntax check button', () => {
    render(<Strategy />)
    expect(screen.getByRole('button', { name: /语法检查/ })).toBeInTheDocument()
  })

  it('should render strategy name input', () => {
    render(<Strategy />)
    expect(screen.getByPlaceholderText('策略名称')).toBeInTheDocument()
  })
})
