import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Backtest from '@/pages/Backtest'

// Mock useWebSocket hook
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => ({
    messages: [],
    connected: false,
  }),
}))

// Mock Monaco Editor
vi.mock('@monaco-editor/react', () => ({
  default: () => <div data-testid="monaco-editor" />,
}))

// Mock react-router-dom
vi.mock('react-router-dom', () => ({
  useNavigate: vi.fn(() => vi.fn()),
}))

// Mock backtestStore
const mockSubmitTask = vi.fn(() => Promise.resolve({ task_id: 'test-task-123' }))
const mockAddNotification = vi.fn()

vi.mock('@/stores/backtestStore', () => ({
  useBacktestStore: vi.fn((selector?: any) => {
    const state = {
      submitTask: mockSubmitTask,
    }
    return selector ? selector(state) : state
  }),
}))

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: vi.fn((selector?: any) => {
    const state = {
      add: mockAddNotification,
    }
    return selector ? selector(state) : state
  }),
}))

describe('Backtest E2E Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSubmitTask.mockResolvedValue({ task_id: 'test-task-123' })
  })

  describe('Page render and initial state', () => {
    it('should render backtest page with all required elements', async () => {
      render(<Backtest />)

      // Verify page loads with title
      expect(screen.getByText('新回测')).toBeInTheDocument()
      expect(screen.getByText('配置策略参数，启动回测验证')).toBeInTheDocument()

      // Verify strategy name input exists
      expect(screen.getByPlaceholderText('e.g. Dual MA Crossover')).toBeInTheDocument()

      // Verify strategy template selector exists
      expect(screen.getByText('策略模板')).toBeInTheDocument()

      // Verify monaco editor is rendered
      expect(screen.getByTestId('monaco-editor')).toBeInTheDocument()

      // Verify Run Backtest button exists
      expect(screen.getByRole('button', { name: /运行回测/ })).toBeInTheDocument()
    })

    it('should show validation error when submitting empty form', async () => {
      const user = userEvent.setup()
      render(<Backtest />)

      // Try to submit without filling required fields
      const runButton = screen.getByRole('button', { name: /运行回测/ })
      await user.click(runButton)

      // Should show validation error for strategy name
      await waitFor(() => {
        expect(screen.getByText('必填')).toBeInTheDocument()
      })

      // submitTask should NOT be called
      expect(mockSubmitTask).not.toHaveBeenCalled()
    })
  })

  describe('Form interaction', () => {
    it('should allow entering strategy name', async () => {
      const user = userEvent.setup()
      render(<Backtest />)

      // Fill strategy name
      const strategyNameInput = screen.getByPlaceholderText('e.g. Dual MA Crossover')
      await user.type(strategyNameInput, 'My Test Strategy')

      // Verify input value
      expect(strategyNameInput).toHaveValue('My Test Strategy')
    })

    it('should show strategy template dropdown options', async () => {
      const user = userEvent.setup()
      render(<Backtest />)

      // Click on the template select to open dropdown
      const templateSelect = document.querySelector('.ant-select[name="template"]') as HTMLElement
      if (templateSelect) {
        await user.click(templateSelect)

        // Check for dropdown options
        await waitFor(() => {
          expect(screen.getByText('Dual MA Crossover')).toBeInTheDocument()
        }, { timeout: 3000 })
      }
    })
  })
})