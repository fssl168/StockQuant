import { useState, useRef, useEffect } from 'react'
import { Input, Button, List, Avatar, Typography, Space } from 'antd'
import { PaperPlaneTilt, User, ChatCircleText, Plus } from '@phosphor-icons/react'
import { useAIStore } from '@/stores/aiStore'

const { Text } = Typography

import { marked } from 'marked'

marked.setOptions({
  breaks: true,
  gfm: true,
})

function renderMarkdown(content: string): string {
  return marked(content) as string
}

export default function AIChat() {
  const messages = useAIStore((s) => s.messages)
  const addMessage = useAIStore((s) => s.addMessage)
  const convId = useAIStore((s) => s.activeConversationId)
  const conversations = useAIStore((s) => s.conversations)
  const activeConversationId = useAIStore((s) => s.activeConversationId)
  const createConversation = useAIStore((s) => s.createConversation)
  const switchConversation = useAIStore((s) => s.switchConversation)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  const handleSend = async () => {
    if (!input.trim() || sending) return
    const text = input.trim()
    setInput('')
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
            onClick={() => { createConversation(); setInput('') }}
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
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <Text type="secondary" style={{ marginBottom: 16, fontSize: 12 }}>
          与 AI 量化助手对话，探索策略、分析数据、解读回测结果
        </Text>

        <div style={{ flex: 1, overflowY: 'auto', paddingRight: 8 }}>
          {messages.length === 0 && !isStreaming && (
            <div style={{ textAlign: 'center', color: 'var(--color-text-tertiary)', marginTop: 100 }}>
              <ChatCircleText size={48} weight="duotone" style={{ color: 'var(--color-brand-primary)', marginBottom: 16 }} />
              <div style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>开始与 AI 对话</div>
              <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
                试试: "查询 sh600519 最近 30 天" 或 "解读我的回测结果"
              </div>
            </div>
          )}
          <List
            dataSource={messages}
            renderItem={(msg) => (
              <List.Item style={{
                paddingTop: 12, paddingBottom: 12,
                borderBottom: '1px solid var(--color-bg-surface)',
                background: msg.role === 'user' ? 'var(--color-brand-subtle)' : 'transparent',
                borderRadius: 4,
              }}>
                <List.Item.Meta
                  avatar={
                    <Avatar style={{
                      background: msg.role === 'user' ? 'var(--color-bg-elevated)' : 'var(--color-brand-primary)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      width: 28, height: 28,
                    }}>
                      {msg.role === 'user' ? <User size={16} weight="fill" /> : <ChatCircleText size={16} weight="fill" />}
                    </Avatar>
                  }
                  title={<Text strong style={{ fontSize: 12, color: msg.role === 'user' ? 'var(--color-brand-primary)' : 'var(--color-text-primary)' }}>
                    {msg.role === 'user' ? '您' : 'AI 助手'}
                  </Text>}
                  description={
                    <div
                      style={{ marginTop: 6, fontSize: 13, lineHeight: 1.7, color: 'var(--color-text-secondary)', ...(msg.role === 'user' ? { whiteSpace: 'pre-wrap', wordBreak: 'break-word' } : {}) }}
                      dangerouslySetInnerHTML={{
                        __html: msg.role === 'assistant'
                          ? renderMarkdown(msg.content as string)
                          : msg.content as string,
                      }}
                    />
                  }
                />
                <span style={{ color: 'var(--color-text-disabled)', fontSize: 10, fontFamily: 'var(--font-mono)', marginLeft: 12, alignSelf: 'start', marginTop: 4 }}>
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </span>
              </List.Item>
            )}
          />
          {/* Streaming message */}
          {isStreaming && (
            <List.Item style={{ paddingTop: 12, paddingBottom: 12, borderBottom: '1px solid var(--color-bg-surface)', borderRadius: 4 }}>
              <List.Item.Meta
                avatar={<Avatar style={{ background: 'var(--color-brand-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28 }}>
                  <ChatCircleText size={16} weight="fill" />
                </Avatar>}
                title={<Text strong style={{ fontSize: 12, color: 'var(--color-text-primary)' }}>AI 助手</Text>}
                description={<div
                  style={{ marginTop: 6, fontSize: 13, lineHeight: 1.7, color: 'var(--color-text-secondary)' }}
                  dangerouslySetInnerHTML={{
                    __html: renderMarkdown(streamingContent),
                  }}
                >
                  {!streamingContent && <span style={{ color: 'var(--color-text-tertiary)' }}>思考中...</span>}
                  <span className="typing-cursor" style={{ animation: 'blink 1s step-end infinite' }}>|</span>
                </div>}
              />
            </List.Item>
          )}
          <div ref={bottomRef} />
        </div>

        <Space style={{ marginTop: 12 }} size={8}>
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={handleSend}
            placeholder="输入消息..."
            size="large"
            disabled={sending}
            allowClear
          />
          <Button
            type="primary"
            icon={<PaperPlaneTilt size={18} />}
            onClick={handleSend}
            size="large"
            loading={sending}
            style={{ minWidth: 48 }}
          />
        </Space>

        <style>{`
          @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
        `}</style>
      </div>
    </div>
  )
}
