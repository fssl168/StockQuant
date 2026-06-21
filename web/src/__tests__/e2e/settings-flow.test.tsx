import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Settings from '@/pages/Settings'

// Mock client API
vi.mock('@/api/client', () => ({
  default: {
    post: vi.fn(() => Promise.resolve({ success: true })),
    get: vi.fn(() => Promise.resolve({ settings: {} })),
  },
}))

// Mock LLMConfigForm component
vi.mock('@/components/Settings/LLMConfigForm', () => ({
  default: ({ values, onChange }: any) => (
    <div data-testid="llm-config-form">
      <input
        data-testid="ai-provider-input"
        value={values['ai.provider'] || ''}
        onChange={(e) => onChange('ai.provider', e.target.value)}
      />
    </div>
  ),
}))

// Mock AgentToggles component
vi.mock('@/components/Settings/AgentToggles', () => ({
  default: ({ values, onChange }: any) => (
    <div data-testid="agent-toggles">
      <input
        data-testid="evolution-enabled"
        type="checkbox"
        checked={values['evolution.enabled'] || false}
        onChange={(e) => onChange('evolution.enabled', e.target.checked)}
      />
    </div>
  ),
}))

// Mock NotifierForm component
vi.mock('@/components/Settings/NotifierForm', () => ({
  default: ({ values, onChange }: any) => (
    <div data-testid="notifier-form">
      <input
        data-testid="dingtalk-webhook"
        value={values['notification.dingtalk_webhook'] || ''}
        onChange={(e) => onChange('notification.dingtalk_webhook', e.target.value)}
      />
    </div>
  ),
}))

// Mock message from Ant Design - include Typography
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd')
  return {
    ...actual,
    message: {
      success: vi.fn(),
      error: vi.fn(),
    },
    Typography: {
      Title: ({ children }: any) => <div>{children}</div>,
      Text: ({ children }: any) => <span>{children}</span>,
    },
  }
})

describe('Settings E2E Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Page render', () => {
    it('should render settings page with all required elements', async () => {
      render(<Settings />)

      // Wait for page to load
      await waitFor(() => {
        expect(screen.getByText('运行配置中心')).toBeInTheDocument()
      })

      // Verify mode toggle exists
      expect(screen.getByText('向导模式')).toBeInTheDocument()
      expect(screen.getByText('专家模式')).toBeInTheDocument()
    })

    it('should display main setting groups in expert mode', async () => {
      render(<Settings />)

      // Wait for page to load
      await waitFor(() => {
        expect(screen.getByText('运行配置中心')).toBeInTheDocument()
      })

      // Verify main setting groups are visible
      await waitFor(() => {
        expect(screen.getByText('系统总控')).toBeInTheDocument()
        expect(screen.getByText('数据源')).toBeInTheDocument()
      })
    })

    it('should have expand/collapse button', async () => {
      render(<Settings />)

      await waitFor(() => {
        expect(screen.getByText('运行配置中心')).toBeInTheDocument()
      })

      expect(screen.getByText('全部折叠')).toBeInTheDocument()
    })
  })

  describe('Expand/collapse all flow', () => {
    it('should toggle expand/collapse all groups', async () => {
      const user = userEvent.setup()
      render(<Settings />)

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByText('运行配置中心')).toBeInTheDocument()
      })

      // Click "全部折叠" button
      const expandButton = screen.getByText('全部折叠')
      await user.click(expandButton)

      // Should now show "全部展开" text
      await waitFor(() => {
        expect(screen.getByText('全部展开')).toBeInTheDocument()
      })
    })
  })
})