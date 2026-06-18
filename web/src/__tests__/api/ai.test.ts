import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

import client from '@/api/client'
import { aiApi, analyzeBacktest } from '@/api/ai'

describe('AI API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ---- chat ----
  it('aiApi.chat should call POST /chat with conversation_id and message', async () => {
    const mockReply = { reply: 'Hello! How can I help?' }
    vi.mocked(client.post).mockResolvedValueOnce(mockReply)
    const result = await aiApi.chat('conv-1', 'hello')
    expect(client.post).toHaveBeenCalledWith('/chat', { conversation_id: 'conv-1', message: 'hello' })
    expect(result).toEqual(mockReply)
  })

  it('aiApi.chat should propagate error on failure', async () => {
    vi.mocked(client.post).mockRejectedValueOnce(new Error('AI service unavailable'))
    await expect(aiApi.chat('conv-1', 'hello')).rejects.toThrow('AI service unavailable')
  })

  // ---- conversations ----
  it('aiApi.conversations should call GET /chat/conversations', async () => {
    const mockConvs = ['conv-1', 'conv-2']
    vi.mocked(client.get).mockResolvedValueOnce(mockConvs)
    const result = await aiApi.conversations()
    expect(client.get).toHaveBeenCalledWith('/chat/conversations')
    expect(result).toEqual(mockConvs)
  })

  it('aiApi.conversations should return empty array when none exist', async () => {
    vi.mocked(client.get).mockResolvedValueOnce([])
    const result = await aiApi.conversations()
    expect(result).toEqual([])
  })

  // ---- clear ----
  it('aiApi.clear should call DELETE /chat/:id', async () => {
    vi.mocked(client.delete).mockResolvedValueOnce(undefined)
    await aiApi.clear('conv-1')
    expect(client.delete).toHaveBeenCalledWith('/chat/conv-1')
  })

  it('aiApi.clear should propagate error', async () => {
    vi.mocked(client.delete).mockRejectedValueOnce(new Error('Delete failed'))
    await expect(aiApi.clear('invalid')).rejects.toThrow('Delete failed')
  })

  // ---- analyzeBacktest ----
  // client 响应拦截器直接返回响应体，故 mock 直接返回 payload
  it('analyzeBacktest should call POST /ai/analyze-backtest/:id and return insight', async () => {
    const mockInsight = { insight: 'test insight' }
    vi.mocked(client.post).mockResolvedValueOnce(mockInsight)
    const result = await analyzeBacktest('bt-1')
    expect(client.post).toHaveBeenCalledWith('/ai/analyze-backtest/bt-1')
    expect(result).toEqual(mockInsight)
  })

  it('analyzeBacktest should propagate error', async () => {
    vi.mocked(client.post).mockRejectedValueOnce(new Error('Analysis failed'))
    await expect(analyzeBacktest('bt-invalid')).rejects.toThrow('Analysis failed')
  })
})
