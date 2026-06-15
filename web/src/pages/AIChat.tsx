import { useState, useRef, useEffect } from 'react'
import { Input, Button, List, Avatar, Typography, Space } from 'antd'
import { PaperPlaneTilt, User, ChatCircleText } from '@phosphor-icons/react'
import { useAIStore } from '@/stores/aiStore'
import { aiApi } from '@/api/ai'

const { Text } = Typography

export default function AIChat() {
  const messages = useAIStore((s) => s.messages)
  const addMessage = useAIStore((s) => s.addMessage)
  const convId = useAIStore((s) => s.conversationId)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || sending) return
    const text = input.trim()
    setInput('')
    addMessage('user', text)
    setSending(true)
    try {
      const res = await aiApi.chat(convId, text)
      addMessage('assistant', (res as { reply: string }).reply)
    } catch {
      addMessage('assistant', '请求失败，请重试。')
    } finally {
      setSending(false)
    }
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: 'calc(100vh - 220px)',
      maxWidth: 900,
    }}>
      <Text type="secondary" style={{ marginBottom: 16, fontSize: 12 }}>
        与 AI 量化助手对话，探索策略、分析数据、解读回测结果
      </Text>

      <div style={{ flex: 1, overflowY: 'auto', paddingRight: 8 }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: '#555', marginTop: 100 }}>
            <ChatCircleText size={48} weight="duotone" style={{ color: '#0066FF', marginBottom: 16 }} />
            <div style={{ fontSize: 14, color: '#888' }}>开始与 AI 对话</div>
            <div style={{ fontSize: 11, color: '#555', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
              试试: "查询 sh600519 最近 30 天" 或 "解读我的回测结果"
            </div>
          </div>
        )}
        <List
          dataSource={messages}
          renderItem={(msg) => (
            <List.Item style={{
              paddingTop: 12, paddingBottom: 12,
              borderBottom: '1px solid #1a1a1a',
              background: msg.role === 'user' ? 'rgba(0,102,255,0.03)' : 'transparent',
              borderRadius: 4,
            }}>
              <List.Item.Meta
                avatar={
                  <Avatar style={{
                    background: msg.role === 'user' ? '#333' : '#0066FF',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    width: 28, height: 28,
                  }}>
                    {msg.role === 'user' ? <User size={16} weight="fill" /> : <ChatCircleText size={16} weight="fill" />}
                  </Avatar>
                }
                title={<Text strong style={{ fontSize: 12, color: msg.role === 'user' ? '#0066FF' : '#f0f0f0' }}>
                  {msg.role === 'user' ? '您' : 'AI 助手'}
                </Text>}
                description={
                  <div style={{
                    marginTop: 6, fontSize: 13, lineHeight: 1.7, color: '#ddd',
                    whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  }}>
                    {msg.content}
                  </div>
                }
              />
              <span style={{ color: '#444', fontSize: 10, fontFamily: 'var(--font-mono)', marginLeft: 12, alignSelf: 'start', marginTop: 4 }}>
                {new Date(msg.timestamp).toLocaleTimeString()}
              </span>
            </List.Item>
          )}
        />
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
    </div>
  )
}
