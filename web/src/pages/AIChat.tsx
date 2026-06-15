import { useState, useRef, useEffect } from 'react'
import { Input, Button, List, Avatar } from 'antd'
import { SendOutlined } from '@ant-design/icons'
import { useAIStore } from '@/stores/aiStore'
import { aiApi } from '@/api/ai'
import type { InputRef } from 'antd'

export default function AIChat() {
  const messages = useAIStore((s) => s.messages)
  const addMessage = useAIStore((s) => s.addMessage)
  const convId = useAIStore((s) => s.conversationId)
  const setInput = useState('')
  const [input, setInput] = setInput
  const inputRef = useRef<InputRef>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim()) return
    const text = input.trim()
    setInput('')
    addMessage('user', text)

    try {
      const res = await aiApi.chat(convId, text)
      addMessage('assistant', (res as { reply: string }).reply)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '发送失败，请重试'
      addMessage('assistant', msg)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: '#999', marginTop: 100 }}>
            <Avatar size={64} icon={<SendOutlined />} style={{ background: '#1677ff' }} />
            <p style={{ marginTop: 16, fontSize: 16 }}>开始与 AI 量化助手对话</p>
          </div>
        )}
        <List
          dataSource={messages}
          renderItem={(msg) => (
            <List.Item>
              <List.Item.Meta
                avatar={<Avatar style={{ background: msg.role === 'user' ? '#1677ff' : '#52c41a' }}>
                  {msg.role === 'user' ? 'U' : 'AI'}
                </Avatar>}
                title={msg.role === 'user' ? '你' : '助手'}
                description={<div style={{ whiteSpace: 'pre-wrap', marginTop: 4 }}>{msg.content}</div>}
              />
              <span style={{ color: '#999', fontSize: 12, marginLeft: 12 }}>
                {new Date(msg.timestamp).toLocaleTimeString()}
              </span>
            </List.Item>
          )}
        />
        <div ref={bottomRef} />
      </div>

      <div style={{ borderTop: '1px solid #f0f0f0', padding: 16, display: 'flex', gap: 8 }}>
        <Input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={handleSend}
          placeholder="输入消息...（如：查询 sh600519 最近 30 天行情）"
          size="large"
        />
        <Button type="primary" icon={<SendOutlined />} size="large" onClick={handleSend}>
          发送
        </Button>
      </div>
    </div>
  )
}
