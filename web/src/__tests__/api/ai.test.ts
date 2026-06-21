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
  it('aiApi.chat should call POST /api/ai/chat with conversation_id and message', async () => {
    const mockReply = { reply: 'Hello! How can I help?' }
    vi.mocked(client.post).mockResolvedValueOnce(mockReply)
    const result = await aiApi.chat('conv-1', 'hello')
    expect(client.post).toHaveBeenCalledWith('/api/ai/chat', { conversation_id: 'conv-1', message: 'hello' })
    expect(result).toEqual(mockReply)
  })

  it('aiApi.chat should propagate error on failure', async () => {
    vi.mocked(client.post).mockRejectedValueOnce(new Error('AI service unavailable'))
    await expect(aiApi.chat('conv-1', 'hello')).rejects.toThrow('AI service unavailable')
  })

  // ---- conversations ----
  it('aiApi.conversations should call GET /api/ai/conversations', async () => {
    const mockConvs = ['conv-1', 'conv-2']
    vi.mocked(client.get).mockResolvedValueOnce(mockConvs)
    const result = await aiApi.conversations()
    expect(client.get).toHaveBeenCalledWith('/api/ai/conversations')
    expect(result).toEqual(mockConvs)
  })

  it('aiApi.conversations should return empty array when none exist', async () => {
    vi.mocked(client.get).mockResolvedValueOnce([])
    const result = await aiApi.conversations()
    expect(result).toEqual([])
  })

  // ---- clear ----
  it('aiApi.clear should call DELETE /api/ai/conversation/:id', async () => {
    vi.mocked(client.delete).mockResolvedValueOnce(undefined)
    await aiApi.clear('conv-1')
    expect(client.delete).toHaveBeenCalledWith('/api/ai/conversation/conv-1')
  })

  it('aiApi.clear should propagate error', async () => {
    vi.mocked(client.delete).mockRejectedValueOnce(new Error('Delete failed'))
    await expect(aiApi.clear('invalid')).rejects.toThrow('Delete failed')
  })

  // ---- analyzeBacktest ----
  it('analyzeBacktest should call POST /api/ai/analyze-backtest/:id and return insight', async () => {
    const mockInsight = { insight: 'test insight' }
    vi.mocked(client.post).mockResolvedValueOnce(mockInsight)
    const result = await analyzeBacktest('bt-1')
    expect(client.post).toHaveBeenCalledWith('/api/ai/analyze-backtest/bt-1')
    expect(result).toEqual(mockInsight)
  })

  it('analyzeBacktest should propagate error', async () => {
    vi.mocked(client.post).mockRejectedValueOnce(new Error('Analysis failed'))
    await expect(analyzeBacktest('bt-invalid')).rejects.toThrow('Analysis failed')
  })
})
