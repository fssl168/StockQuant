import { useState, useRef, useEffect } from 'react'
import { Button, Segmented } from 'antd'
import { Plus } from '@phosphor-icons/react'
import { useAIStore } from '@/stores/aiStore'
import ChatPanel from '@/components/AI/ChatPanel'
import { streamChat } from '@/api/ai'

type ChatMode = 'general' | 'strategy' | 'analysis' | 'monitor' | 'decision' | 'indicator'

const MODE_LABELS: Record<ChatMode, string> = {
  general: '通用',
  strategy: '策略',
  analysis: '数据分析',
  monitor: '盯盘',
  decision: '决策',
  indicator: '指标发现',
}

export default function AIChat() {
  const messages = useAIStore((s) => s.messages)
  const setMessages = useAIStore((s) => (s as any).setMessages)
  const addMessage = useAIStore((s) => s.addMessage)
  const convId = useAIStore((s) => s.activeConversationId)
  const conversations = useAIStore((s) => s.conversations)
  const activeConversationId = useAIStore((s) => s.activeConversationId)
  const createConversation = useAIStore((s) => s.createConversation)
  const switchConversation = useAIStore((s) => s.switchConversation)

  useEffect(() => {
    useAIStore.getState().init()
  }, [])
  const [sending, setSending] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [mode, setMode] = useState<ChatMode>('general')
  const [hasMore, setHasMore] = useState(false)
  const streamingRef = useRef('')

  const handleLoadMore = (moreMsgs: typeof messages) => {
    // 合并消息，去重
    const existingIds = new Set(messages.map((m: any) => m.timestamp))
    const newMsgs = moreMsgs.filter((m: any) => !existingIds.has(m.timestamp))
    if (setMessages) {
      setMessages([...newMsgs, ...messages])
    }
    // 如果返回的消息数少于限制，说明没有更多了
    if (moreMsgs.length < 50) {
      setHasMore(false)
    }
  }

  // 当切换会话或初始化时检查是否有更多消息
  useEffect(() => {
    const conv = conversations.find((c: any) => c.id === activeConversationId)
    if (conv && conv.messageCount > messages.length) {
      setHasMore(true)
    } else {
      setHasMore(false)
    }
  }, [activeConversationId, messages.length, conversations])

  const handleSend = async (text: string) => {
    if (sending) return
    addMessage('user', text)
    setSending(true)
    setIsStreaming(true)
    streamingRef.current = ''
    setStreamingContent('')
    try {
      for await (const chunk of streamChat(convId, text, { mode })) {
        streamingRef.current += chunk
        setStreamingContent(streamingRef.current)
      }
      addMessage('assistant', streamingRef.current)
    } catch {
      addMessage('assistant', streamingRef.current || '请求失败，请重试。')
    } finally {
      setIsStreaming(false)
      setSending(false)
      streamingRef.current = ''
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
                  {new Date(conv.createdAt).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right: Chat area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {/* Mode selector */}
        <div style={{ padding: '8px 16px', borderBottom: '1px solid var(--color-border-default)' }}>
          <Segmented
            value={mode}
            onChange={(v) => setMode(v as ChatMode)}
            options={Object.entries(MODE_LABELS).map(([value, label]) => ({
              value,
              label,
            }))}
            size="small"
          />
        </div>

        <ChatPanel
          messages={messages.map((m: any) => ({
            role: m.role as 'user' | 'assistant',
            content: m.content as string,
            timestamp: m.timestamp,
          }))}
          streamingContent={streamingContent}
          isStreaming={isStreaming}
          onSend={handleSend}
          mode={mode}
          conversationId={activeConversationId}
          onLoadMore={handleLoadMore}
          hasMore={hasMore}
        />
      </div>
    </div>
  )
}
