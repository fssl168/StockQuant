import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Strategy from '@/pages/Strategy'

// Mock StrategyEditor component
vi.mock('@/components/Strategy/StrategyEditor', () => ({
  default: ({ code, onChange, onSave }: any) => (
    <div data-testid="strategy-editor">
      <textarea
        data-testid="code-editor"
        value={code || ''}
        onChange={(e) => onChange(e.target.value)}
      />
      <button data-testid="save-button" onClick={onSave}>保存</button>
    </div>
  ),
}))

// Mock PreviewPanel component
vi.mock('@/components/Strategy/PreviewPanel', () => ({
  default: ({ code }: any) => (code ? <div data-testid="preview-panel">Preview</div> : null),
}))

// Mock strategyApi
const mockStrategies = [
  { id: '1', name: 'Strategy A', code: 'code A', createdAt: '2024-01-01' },
  { id: '2', name: 'Strategy B', code: 'code B', createdAt: '2024-01-02' },
]

const mockCreateStrategy = vi.fn(() => Promise.resolve({ id: '3', name: 'New Strategy', code: 'new code' }))
const mockDeleteStrategy = vi.fn(() => Promise.resolve())
const mockFetchStrategies = vi.fn(() => Promise.resolve())

vi.mock('@/stores/strategyStore', () => ({
  useStrategyStore: vi.fn((selector?: any) => {
    const state = {
      strategies: mockStrategies,
      loading: false,
      fetchStrategies: mockFetchStrategies,
      createStrategy: mockCreateStrategy,
      deleteStrategy: mockDeleteStrategy,
    }
    return selector ? selector(state) : state
  }),
}))

// Mock client API
vi.mock('@/api/client', () => ({
  default: {
    post: vi.fn(() => Promise.resolve({ data: { code: 'generated code', name: 'Generated Strategy' } })),
    get: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

describe('Strategy CRUD E2E Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetchStrategies.mockResolvedValue(undefined)
  })

  describe('Page render', () => {
    it('should render strategy page with all required elements', async () => {
      render(<Strategy />)

      // Verify page title
      expect(screen.getByText('策略管理')).toBeInTheDocument()

      // Verify toolbar buttons
      expect(screen.getByRole('button', { name: /新建策略/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /模板库/ })).toBeInTheDocument()
    })

    it('should load and display strategy list', async () => {
      render(<Strategy />)

      // Wait for strategies to load
      await waitFor(() => {
        expect(screen.getByText('Strategy A')).toBeInTheDocument()
        expect(screen.getByText('Strategy B')).toBeInTheDocument()
      })

      // Verify fetch was called
      expect(mockFetchStrategies).toHaveBeenCalled()
    })
  })

  describe('Template library flow', () => {
    it('should open template library modal when clicking template button', async () => {
      const user = userEvent.setup()
      render(<Strategy />)

      // Wait for initial render
      await waitFor(() => {
        expect(screen.getByText('策略管理')).toBeInTheDocument()
      })

      // Click "模板库" button
      const templateButton = screen.getByRole('button', { name: /模板库/ })
      await user.click(templateButton)

      // Modal should open with template options
      await waitFor(() => {
        expect(screen.getByText('策略模板库')).toBeInTheDocument()
        expect(screen.getByText('Dual MA Crossover')).toBeInTheDocument()
      })
    })
  })

  describe('Create new strategy flow', () => {
    it('should reset form when clicking new strategy button', async () => {
      const user = userEvent.setup()
      render(<Strategy />)

      // Wait for strategies to load
      await waitFor(() => {
        expect(screen.getByText('Strategy A')).toBeInTheDocument()
      })

      // Click "新建策略" button
      const newButton = screen.getByRole('button', { name: /新建策略/ })
      await user.click(newButton)

      // Verify name input is cleared/empty
      const nameInput = screen.getByPlaceholderText('策略名称')
      expect(nameInput).toHaveValue('')
    })
  })
})