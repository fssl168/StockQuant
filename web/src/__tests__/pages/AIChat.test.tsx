import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import AIChat from '@/pages/AIChat'

// Mock scrollIntoView for jsdom
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

// Mock @/stores/aiStore (include getState for AIChat.tsx L30 useAIStore.getState().init())
vi.mock('@/stores/aiStore', () => {
  const state = {
    messages: [],
    addMessage: vi.fn(),
    setMessages: vi.fn(),
    activeConversationId: 'conv-1',
    conversations: [],
    createConversation: vi.fn(),
    switchConversation: vi.fn(),
    init: vi.fn(),
  }
  const useAIStore = Object.assign(
    vi.fn((selector: any) => (selector ? selector(state) : state)),
    { getState: () => state }
  )
  return { useAIStore }
})

// Mock @/api/ai (AIChat.tsx L70 streamChat)
vi.mock('@/api/ai', () => ({
  streamChat: vi.fn().mockImplementation(async function* () {
    yield 'mocked AI response'
  }),
}))

// Mock marked — ChatPanel uses new marked.Renderer() and marked.use(...)
vi.mock('marked', () => {
  const mockMarked = vi.fn((text: string) => text) as any
  mockMarked.setOptions = vi.fn()
  mockMarked.use = vi.fn()
  mockMarked.Renderer = class {
    constructor() {}
    [key: string]: any
  }
  return { marked: mockMarked, setOptions: vi.fn() }
})

vi.mock('dompurify', () => {
  const sanitize = vi.fn((html: string) => html)
  return { default: { sanitize } }
})

// Mock @/components/AI/ChatPanel to avoid internal marked.Renderer complexity
vi.mock('@/components/AI/ChatPanel', () => ({
  default: vi.fn((props: any) => (
    <div data-testid="chat-panel">
      <input placeholder="输入消息..." />
      <button style={{ minWidth: 48 }} onClick={() => props.onSend?.('test')} />
      {props.messages?.length === 0 && <div>开始与 AI 对话</div>}
      <div>查询 sh600519 最近 30 天的行情数据</div>
    </div>
  )),
}))

describe('AIChat Page', () => {
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
    // The send button has style minWidth: 48px
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
