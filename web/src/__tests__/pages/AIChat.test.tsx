import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import AIChat from '@/pages/AIChat'

// Mock scrollIntoView for jsdom
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

vi.mock('@/stores/aiStore', () => ({
  useAIStore: vi.fn((selector: any) => {
    const state = {
      messages: [],
      addMessage: vi.fn(),
      activeConversationId: 'conv-1',
      conversations: [],
      createConversation: vi.fn(),
      switchConversation: vi.fn(),
    }
    return selector ? selector(state) : state
  }),
}))

vi.mock('marked', () => {
  const mockMarked = vi.fn((text: string) => text) as any
  mockMarked.setOptions = vi.fn()
  return { marked: mockMarked, setOptions: vi.fn() }
})

vi.mock('dompurify', () => {
  const sanitize = vi.fn((html: string) => html)
  return { default: { sanitize } }
})

describe('AIChat Page', () => {
  it('should render AI assistant description', () => {
    render(<AIChat />)
    expect(screen.getByText(/与 AI 量化助手对话/)).toBeInTheDocument()
  })

  it('should render new conversation button', () => {
    render(<AIChat />)
    expect(screen.getByRole('button', { name: /新建对话/ })).toBeInTheDocument()
  })

  it('should render message input', () => {
    render(<AIChat />)
    expect(screen.getByPlaceholderText('输入消息...')).toBeInTheDocument()
  })

  it('should render send button', () => {
    render(<AIChat />)
    // The send button has PaperPlaneTilt icon, no text
    const sendButton = document.querySelector('button[style*="min-width: 48px"]') as HTMLButtonElement
    expect(sendButton).toBeTruthy()
  })

  it('should render empty state when no messages', () => {
    render(<AIChat />)
    expect(screen.getByText('开始与 AI 对话')).toBeInTheDocument()
  })

  it('should render empty conversation hint', () => {
    render(<AIChat />)
    expect(screen.getByText('暂无历史对话')).toBeInTheDocument()
  })

  it('should render example prompts', () => {
    render(<AIChat />)
    expect(screen.getByText(/查询 sh600519 最近 30 天/)).toBeInTheDocument()
  })
})
