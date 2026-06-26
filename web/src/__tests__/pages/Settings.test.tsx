import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Settings from '@/pages/Settings'

// Mock @/api/client (Settings.tsx L73 client.get('/api/settings'), L122 client.post)
vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue(undefined),
  },
}))

// Mock @/stores/authStore (Settings.tsx L66 useAuthStore)
vi.mock('@/stores/authStore', () => ({
  useAuthStore: vi.fn(() => ({ user: { role: 'ADMIN' } })),
}))

// Mock @/components/Settings subcomponents (Settings.tsx L4 import)
vi.mock('@/components/Settings', () => ({
  GeneralSettings: vi.fn(() => <div data-testid="general-settings">GeneralSettings</div>),
  TradingSettings: vi.fn(() => <div data-testid="trading-settings">TradingSettings</div>),
  AISettings: vi.fn(() => <div data-testid="ai-settings">AISettings</div>),
  NotifierSettings: vi.fn(() => <div data-testid="notifier-settings">NotifierSettings</div>),
  BrokerSettings: vi.fn(() => <div data-testid="broker-settings">BrokerSettings</div>),
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

describe('Settings Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render page title 系统设置', () => {
    render(<Settings />)
    expect(screen.getByText('系统设置')).toBeInTheDocument()
  })

  it('should render 专家模式 toggle button in wizard mode (default)', () => {
    render(<Settings />)
    expect(screen.getByRole('button', { name: /专家模式/ })).toBeInTheDocument()
  })

  it('should render 保存设置 button', () => {
    render(<Settings />)
    expect(screen.getByRole('button', { name: /保存设置/ })).toBeInTheDocument()
  })

  it('should show only 券商配置 and 通知设置 tabs in wizard mode', () => {
    render(<Settings />)
    // wizard mode filters tabs to broker + notification
    expect(screen.getByText('券商配置')).toBeInTheDocument()
    expect(screen.getByText('通知设置')).toBeInTheDocument()
    // wizard mode hides these
    expect(screen.queryByText('通用设置')).not.toBeInTheDocument()
    expect(screen.queryByText('交易设置')).not.toBeInTheDocument()
  })

  it('should switch to expert mode and show all tabs on clicking 专家模式', async () => {
    const user = userEvent.setup()
    render(<Settings />)
    await user.click(screen.getByRole('button', { name: /专家模式/ }))
    // After switch, button label becomes 简化模式
    expect(screen.getByRole('button', { name: /简化模式/ })).toBeInTheDocument()
    // Expert mode shows all 5 tabs
    expect(screen.getByText('券商配置')).toBeInTheDocument()
    expect(screen.getByText('通用设置')).toBeInTheDocument()
    expect(screen.getByText('交易设置')).toBeInTheDocument()
    expect(screen.getByText('AI 模型')).toBeInTheDocument()
    expect(screen.getByText('通知设置')).toBeInTheDocument()
  })

  it('should call client.post on save and show success message', async () => {
    const user = userEvent.setup()
    render(<Settings />)
    await user.click(screen.getByRole('button', { name: /保存设置/ }))
    expect(client.post).toHaveBeenCalledWith('/api/settings', expect.any(Object))
    expect(message.success).toHaveBeenCalledWith('设置已保存，部分配置重启后生效')
  })

  it('should show error message on save failure', async () => {
    const user = userEvent.setup()
    vi.mocked(client.post).mockRejectedValueOnce(new Error('network error'))
    render(<Settings />)
    await user.click(screen.getByRole('button', { name: /保存设置/ }))
    expect(message.error).toHaveBeenCalledWith(expect.stringContaining('保存失败'))
  })

  it('should load settings on mount via client.get', () => {
    render(<Settings />)
    expect(client.get).toHaveBeenCalledWith('/api/settings')
  })
})
