import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

import client from '@/api/client'
import { strategyApi } from '@/api/strategy'

describe('Strategy API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ---- list ----
  it('strategyApi.list should call GET /strategy', async () => {
    const mockList = [{ id: 's1', name: 'test', code: 'code', description: '', parameters: {}, created_at: '', updated_at: '' }]
    vi.mocked(client.get).mockResolvedValueOnce(mockList)
    const result = await strategyApi.list()
    expect(client.get).toHaveBeenCalledWith('/strategy')
    expect(result).toEqual(mockList)
  })

  it('strategyApi.list should return empty array when no strategies', async () => {
    vi.mocked(client.get).mockResolvedValueOnce([])
    const result = await strategyApi.list()
    expect(result).toEqual([])
  })

  // ---- create ----
  it('strategyApi.create should call POST /strategy with data', async () => {
    const mockCreated = { id: 's1', name: 'test', code: 'code', description: '', parameters: {}, created_at: '2024-01-01', updated_at: '2024-01-01' }
    vi.mocked(client.post).mockResolvedValueOnce(mockCreated)
    const payload = { name: 'test', code: 'code', description: '', parameters: {} }
    const result = await strategyApi.create(payload)
    expect(client.post).toHaveBeenCalledWith('/strategy', payload)
    expect(result).toEqual(mockCreated)
  })

  // ---- get ----
  it('strategyApi.get should call GET /strategy/:id', async () => {
    const mockStrategy = { id: 's1', name: 'test', code: 'code', description: '', parameters: {}, created_at: '', updated_at: '' }
    vi.mocked(client.get).mockResolvedValueOnce(mockStrategy)
    const result = await strategyApi.get('s1')
    expect(client.get).toHaveBeenCalledWith('/strategy/s1')
    expect(result).toEqual(mockStrategy)
  })

  // ---- update ----
  it('strategyApi.update should call PUT /strategy/:id with partial data', async () => {
    const mockUpdated = { id: 's1', name: 'updated', code: 'new code', description: '', parameters: {}, created_at: '', updated_at: '' }
    vi.mocked(client.put).mockResolvedValueOnce(mockUpdated)
    const payload = { name: 'updated', code: 'new code' }
    const result = await strategyApi.update('s1', payload)
    expect(client.put).toHaveBeenCalledWith('/strategy/s1', payload)
    expect(result).toEqual(mockUpdated)
  })

  // ---- delete ----
  it('strategyApi.delete should call DELETE /strategy/:id', async () => {
    vi.mocked(client.delete).mockResolvedValueOnce(undefined)
    await strategyApi.delete('s1')
    expect(client.delete).toHaveBeenCalledWith('/strategy/s1')
  })

  it('strategyApi.delete should propagate error', async () => {
    vi.mocked(client.delete).mockRejectedValueOnce(new Error('Not found'))
    await expect(strategyApi.delete('invalid')).rejects.toThrow('Not found')
  })

  // ---- templates ----
  it('strategyApi.templates should return non-empty array with name and code', () => {
    const result = strategyApi.templates()
    expect(Array.isArray(result)).toBe(true)
    expect(result.length).toBeGreaterThan(0)
    result.forEach((t) => {
      expect(t).toHaveProperty('name')
      expect(t).toHaveProperty('code')
      expect(typeof t.name).toBe('string')
      expect(typeof t.code).toBe('string')
    })
  })

  it('strategyApi.templates should include Dual MA Crossover template', () => {
    const result = strategyApi.templates()
    const dualMA = result.find((t) => t.name === 'Dual MA Crossover')
    expect(dualMA).toBeDefined()
    expect(dualMA!.code).toContain('DualMACrossover')
  })
})
