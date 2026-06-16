import { useState, useRef, useEffect } from 'react'
import { Input, Button, List, Avatar, Typography } from 'antd'
import { PaperPlaneTilt, User, ChatCircleText } from '@phosphor-icons/react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const { Text } = Typography

marked.setOptions({
  breaks: true,
  gfm: true,
})

function renderMarkdown(content: string): string {
  return DOMPurify.sanitize(marked(content) as string)
}

interface ChatPanelProps {
  messages: Array<{
    role: 'user' | 'assistant'
    content: string
    timestamp: string
  }>
  streamingContent?: string
  isStreaming?: boolean
  onSend: (message: string) => void
}

export default function ChatPanel({ messages, streamingContent = '', isStreaming = false, onSend }: ChatPanelProps) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  const handleSend = () => {
    const text = input.trim()
    if (!text) return
    onSend(text)
    setInput('')
  }

  return (
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
                        ? renderMarkdown(msg.content)
                        : msg.content,
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

      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={handleSend}
          placeholder="输入消息..."
          size="large"
          disabled={isStreaming}
          allowClear
        />
        <Button
          type="primary"
          icon={<PaperPlaneTilt size={18} />}
          onClick={handleSend}
          size="large"
          loading={isStreaming}
          style={{ minWidth: 48 }}
        />
      </div>

      <style>{`
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
      `}</style>
    </div>
  )
}
