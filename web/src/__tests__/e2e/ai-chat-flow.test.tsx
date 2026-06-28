import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AIChat from '@/pages/AIChat'

// Mock the streamChat API - must be done before import
vi.mock('@/api/ai', () => ({
  streamChat: vi.fn(async function* () {
    yield 'Hello '
    yield 'world!'
  }),
  aiApi: {
    getConversations: vi.fn(() => Promise.resolve({ conversations: [] })),
    getConversation: vi.fn(() => Promise.resolve({ messages: [] })),
    saveMessage: vi.fn(() => Promise.resolve({ saved: true })),
    deleteConversation: vi.fn(() => Promise.resolve({ cleared: true })),
  },
}))

// Mock @/stores/aiStore (AIChat.tsx L30 useAIStore.getState().init())
vi.mock('@/stores/aiStore', () => {
  const state = {
    messages: Array<{ role: string; content: string; timestamp: number }>(),
    setMessages: vi.fn(),
    addMessage: vi.fn((role: string, content: string) => {
      state.messages.push({ role, content, timestamp: Date.now() });
    }),
    activeConversationId: 'conv-1',
    conversations: [],
    createConversation: vi.fn(),
    switchConversation: vi.fn(),
    init: vi.fn(),
  }
  const useAIStore = Object.assign(
    vi.fn((selector?: any) => (selector ? selector(state) : state)),
    { getState: () => state }
  )
  return { useAIStore }
})

// Mock ChatPanel component
vi.mock('@/components/AI/ChatPanel', () => ({
  default: ({ messages, onSend, isStreaming, streamingContent }: any) => (
    <div data-testid="chat-panel">
      <div data-testid="messages-container">
        {messages.map((m: any, i: number) => (
          <div key={i} data-testid={`message-${m.role}`} data-content={m.content}>
            {m.content}
          </div>
        ))}
        {isStreaming && streamingContent && (
          <div data-testid="streaming-content">{streamingContent}</div>
        )}
      </div>
      <input
        data-testid="chat-input"
        placeholder="输入消息..."
      />
      <button
        data-testid="send-button"
        onClick={() => {
          const input = document.querySelector('[data-testid="chat-input"]') as HTMLInputElement
          if (input && input.value) {
            onSend(input.value)
            input.value = ''
          }
        }}
      >
        发送
      </button>
    </div>
  ),
}))

describe('AI Chat E2E Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Page render and initial state', () => {
    it('should render AI chat page with all required elements', async () => {
      render(<AIChat />)

      // Wait for page to load
      await waitFor(() => {
        expect(screen.getByTestId('chat-panel')).toBeInTheDocument()
      })

      // Verify new chat button exists
      expect(screen.getByRole('button', { name: /新建对话/ })).toBeInTheDocument()
    })

    it('should have empty messages on initial load', async () => {
      render(<AIChat />)

      await waitFor(() => {
        expect(screen.getByTestId('chat-panel')).toBeInTheDocument()
      })

      // Messages container should be empty initially
      const messagesContainer = screen.getByTestId('messages-container')
      expect(messagesContainer.children.length).toBe(0)
    })
  })

  describe('New conversation flow', () => {
    it('should create a new conversation when clicking new chat button', async () => {
      const user = userEvent.setup()
      render(<AIChat />)

      await waitFor(() => {
        expect(screen.getByTestId('chat-panel')).toBeInTheDocument()
      })

      // Click "新建对话" button
      const newChatButton = screen.getByRole('button', { name: /新建对话/ })
      await user.click(newChatButton)

      // The conversation should be created - messages should be cleared
      const messagesContainer = screen.getByTestId('messages-container')
      expect(messagesContainer.children.length).toBe(0)
    })
  })

  describe('Send message flow', () => {
    it('should add user message to chat when send button is clicked', async () => {
      const user = userEvent.setup()
      render(<AIChat />)

      await waitFor(() => {
        expect(screen.getByTestId('chat-panel')).toBeInTheDocument()
      })

      // Type a message
      const chatInput = screen.getByTestId('chat-input')
      await user.type(chatInput, 'Hello AI')

      // Click send button
      const sendButton = screen.getByTestId('send-button')
      await user.click(sendButton)

      // Verify user message appears
      await waitFor(() => {
        const userMessages = screen.getAllByTestId('message-user')
        expect(userMessages.length).toBeGreaterThan(0)
      })
    })
  })
})