import { useState } from 'react'
import { Button } from 'antd'
import { Plus } from '@phosphor-icons/react'
import { useAIStore } from '@/stores/aiStore'
import ChatPanel from '@/components/AI/ChatPanel'

export default function AIChat() {
  const messages = useAIStore((s) => s.messages)
  const addMessage = useAIStore((s) => s.addMessage)
  const convId = useAIStore((s) => s.activeConversationId)
  const conversations = useAIStore((s) => s.conversations)
  const activeConversationId = useAIStore((s) => s.activeConversationId)
  const createConversation = useAIStore((s) => s.createConversation)
  const switchConversation = useAIStore((s) => s.switchConversation)
  const [sending, setSending] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)

  const handleSend = async (text: string) => {
    if (sending) return
    addMessage('user', text)
    setSending(true)
    setIsStreaming(true)
    setStreamingContent('')
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: convId, message: text }),
      })
      if (!res.ok || !res.body) throw new Error('请求失败')
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let accumulated = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        accumulated += decoder.decode(value, { stream: true })
        setStreamingContent(accumulated)
      }
      addMessage('assistant', accumulated)
    } catch {
      addMessage('assistant', streamingContent || '请求失败，请重试。')
    } finally {
      setIsStreaming(false)
      setSending(false)
      setStreamingContent('')
    }
  }

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 120px)', gap: 0, maxWidth: 1100, margin: '0 auto' }}>
      {/* Left sidebar: Conversation list */}
      <div style={{
        width: 200, flexShrink: 0,
        borderRight: '1px solid var(--color-border-default)',
        display: 'flex', flexDirection: 'column',
        background: 'var(--color-bg-elevated)',
      }}>
        {/* New chat button */}
        <div style={{ padding: '12px', borderBottom: '1px solid var(--color-border-default)' }}>
          <Button
            type="primary"
            icon={<Plus size={15} />}
            block
            size="small"
            onClick={() => { createConversation() }}
          >
            新建对话
          </Button>
        </div>

        {/* Conversation list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
          {conversations.length === 0 && (
            <div style={{ textAlign: 'center', color: 'var(--color-text-tertiary)', fontSize: 11, marginTop: 24 }}>
              暂无历史对话
            </div>
          )}
          {conversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => switchConversation(conv.id)}
              style={{
                padding: '10px 12px',
                borderRadius: 6,
                marginBottom: 4,
                cursor: 'pointer',
                background: conv.id === activeConversationId ? 'var(--color-brand-subtle)' : 'transparent',
                border: conv.id === activeConversationId ? '1px solid var(--color-brand-primary)' : '1px solid transparent',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => { if (conv.id !== activeConversationId) e.currentTarget.style.background = 'var(--color-bg-hover)' }}
              onMouseLeave={(e) => { if (conv.id !== activeConversationId) e.currentTarget.style.background = 'transparent' }}
            >
              <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {conv.title || '新对话'}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
                <span style={{ fontSize: 10, color: 'var(--color-text-disabled)' }}>
                  {conv.messageCount} 条消息
                </span>
                <span style={{ fontSize: 10, color: 'var(--color-text-tertiary)' }}>
                  {new Date(conv.createdAt).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right: Chat area */}
      <ChatPanel
        messages={messages.map((m) => ({
          role: m.role as 'user' | 'assistant',
          content: m.content as string,
          timestamp: String(m.timestamp),
        }))}
        streamingContent={streamingContent}
        isStreaming={isStreaming}
        onSend={handleSend}
      />
    </div>
  )
}
