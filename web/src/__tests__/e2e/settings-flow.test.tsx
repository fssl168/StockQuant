import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Settings from '@/pages/Settings'

// Mock @/api/client
vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: { 'trading.mode': 'paper', system: { log_level: 'INFO' } } }),
    post: vi.fn().mockResolvedValue(undefined),
  },
}))

// Mock @/stores/authStore
vi.mock('@/stores/authStore', () => ({
  useAuthStore: vi.fn(() => ({ user: { role: 'ADMIN' } })),
}))

// Mock @/components/Settings subcomponents
vi.mock('@/components/Settings', () => ({
  GeneralSettings: vi.fn(() => <div data-testid="general-settings">GeneralSettings</div>),
  TradingSettings: vi.fn(() => <div data-testid="trading-settings">TradingSettings</div>),
  AISettings: vi.fn(() => <div data-testid="ai-settings">AISettings</div>),
  NotifierSettings: vi.fn(() => <div data-testid="notifier-settings">NotifierSettings</div>),
  BrokerSettings: vi.fn(() => <div data-testid="broker-settings">BrokerSettings</div>),
  // P2-9 / refactoring: 新增的设置子组件 — 必须在 mock 中导出，否则 Settings.tsx 渲染时报错
  SoundSettings: vi.fn(() => <div data-testid="sound-settings">SoundSettings</div>),
  DisplaySettings: vi.fn(() => <div data-testid="display-settings">DisplaySettings</div>),
  RiskControlSettings: vi.fn(() => <div data-testid="risk-control-settings">RiskControlSettings</div>),
}))

// Mock antd message to capture success/error calls
vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd')
  return {
    ...actual,
    message: { ...actual.message, success: vi.fn(), error: vi.fn() },
  }
})

import { message } from 'antd'
import client from '@/api/client'

describe('Settings E2E Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Page render', () => {
    it('should render settings page with title and mode toggle', async () => {
      render(<Settings />)

      await waitFor(() => {
        expect(screen.getByText('系统设置')).toBeInTheDocument()
      })

      // Wizard mode (default) shows 专家模式 toggle button
      expect(screen.getByRole('button', { name: /专家模式/ })).toBeInTheDocument()
      // Save button
      expect(screen.getByRole('button', { name: /保存设置/ })).toBeInTheDocument()
    })

    it('should load settings from API on mount', async () => {
      render(<Settings />)
      expect(client.get).toHaveBeenCalledWith('/api/settings')
    })

    it('should show wizard tabs (券商配置 + 通知设置) by default', async () => {
      render(<Settings />)
      await waitFor(() => {
        expect(screen.getByText('系统设置')).toBeInTheDocument()
      })
      expect(screen.getByText('券商配置')).toBeInTheDocument()
      expect(screen.getByText('通知设置')).toBeInTheDocument()
      // Wizard mode hides these
      expect(screen.queryByText('通用设置')).not.toBeInTheDocument()
      expect(screen.queryByText('交易设置')).not.toBeInTheDocument()
    })
  })

  describe('Mode switch flow', () => {
    it('should switch to expert mode and reveal all tabs', async () => {
      const user = userEvent.setup()
      render(<Settings />)

      await waitFor(() => {
        expect(screen.getByText('系统设置')).toBeInTheDocument()
      })

      // Click 专家模式 toggle
      await user.click(screen.getByRole('button', { name: /专家模式/ }))

      // Button label flips to 简化模式
      expect(screen.getByRole('button', { name: /简化模式/ })).toBeInTheDocument()
      // All 5 tabs now visible
      expect(screen.getByText('券商配置')).toBeInTheDocument()
      expect(screen.getByText('通用设置')).toBeInTheDocument()
      expect(screen.getByText('交易设置')).toBeInTheDocument()
      expect(screen.getByText('AI 模型')).toBeInTheDocument()
      expect(screen.getByText('通知设置')).toBeInTheDocument()
    })

    it('should toggle back to wizard mode', async () => {
      const user = userEvent.setup()
      render(<Settings />)

      await waitFor(() => {
        expect(screen.getByText('系统设置')).toBeInTheDocument()
      })

      // Switch to expert
      await user.click(screen.getByRole('button', { name: /专家模式/ }))
      expect(screen.getByRole('button', { name: /简化模式/ })).toBeInTheDocument()

      // Switch back to wizard
      await user.click(screen.getByRole('button', { name: /简化模式/ }))
      expect(screen.getByRole('button', { name: /专家模式/ })).toBeInTheDocument()
      // Hidden tabs disappear again
      expect(screen.queryByText('通用设置')).not.toBeInTheDocument()
    })
  })

  describe('Save flow', () => {
    it('should call client.post and show success message on save', async () => {
      const user = userEvent.setup()
      render(<Settings />)

      await waitFor(() => {
        expect(screen.getByText('系统设置')).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /保存设置/ }))

      await waitFor(() => {
        expect(client.post).toHaveBeenCalledWith('/api/settings', expect.any(Object))
        expect(message.success).toHaveBeenCalledWith('设置已保存，部分配置重启后生效')
      })
    })

    it('should show error message on save failure', async () => {
      const user = userEvent.setup()
      vi.mocked(client.post).mockRejectedValueOnce(new Error('network error'))
      render(<Settings />)

      await waitFor(() => {
        expect(screen.getByText('系统设置')).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /保存设置/ }))

      await waitFor(() => {
        expect(message.error).toHaveBeenCalledWith(expect.stringContaining('保存失败'))
      })
    })
  })
})
