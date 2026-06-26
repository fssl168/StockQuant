import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useStrategyStore } from '@/stores/strategyStore'
import type { Strategy } from '@/types'

// Mock strategyApi
vi.mock('@/api/strategy', () => ({
  strategyApi: {
    list: vi.fn(),
    create: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    templates: vi.fn(),
  },
}))

import { strategyApi } from '@/api/strategy'

const mockStrategy: Strategy = {
  id: 's1',
  name: 'Test Strategy',
  code: 'print("hello")',
  description: 'A test strategy',
  parameters: {},
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-01T00:00:00Z',
}

describe('StrategyStore', () => {
  beforeEach(() => {
    // Reset store to initial state
    useStrategyStore.setState({
      strategies: [],
      loading: false,
      currentStrategy: null,
    })
    vi.clearAllMocks()
  })

  // ---- initial state ----
  it('should have empty strategies initially', () => {
    expect(useStrategyStore.getState().strategies).toEqual([])
  })

  it('should have loading=false initially', () => {
    expect(useStrategyStore.getState().loading).toBe(false)
  })

  it('should have currentStrategy=null initially', () => {
    expect(useStrategyStore.getState().currentStrategy).toBeNull()
  })

  // ---- fetchStrategies ----
  it('fetchStrategies should call strategyApi.list and populate strategies', async () => {
    vi.mocked(strategyApi.list).mockResolvedValueOnce([mockStrategy])
    await useStrategyStore.getState().fetchStrategies()
    expect(strategyApi.list).toHaveBeenCalledOnce()
    expect(useStrategyStore.getState().strategies).toEqual([mockStrategy])
    expect(useStrategyStore.getState().loading).toBe(false)
  })

  it('fetchStrategies should set loading=true during fetch', () => {
    vi.mocked(strategyApi.list).mockReturnValue(new Promise(() => {})) // never resolves
    useStrategyStore.getState().fetchStrategies()
    expect(useStrategyStore.getState().loading).toBe(true)
  })

  it('fetchStrategies should reset strategies to empty on error', async () => {
    useStrategyStore.setState({ strategies: [mockStrategy] })
    vi.mocked(strategyApi.list).mockRejectedValueOnce(new Error('Network error'))
    await useStrategyStore.getState().fetchStrategies()
    expect(useStrategyStore.getState().strategies).toEqual([])
    expect(useStrategyStore.getState().loading).toBe(false)
  })

  // ---- createStrategy ----
  it('createStrategy should call strategyApi.create and add result to strategies', async () => {
    const payload = { name: 'New', code: 'code', description: '', parameters: {} }
    vi.mocked(strategyApi.create).mockResolvedValueOnce({ ...mockStrategy, ...payload })
    await useStrategyStore.getState().createStrategy(payload)
    expect(strategyApi.create).toHaveBeenCalledWith(payload)
    expect(useStrategyStore.getState().strategies).toHaveLength(1)
    expect(useStrategyStore.getState().strategies[0].name).toBe('New')
  })

  it('createStrategy should not modify strategies on API error', async () => {
    useStrategyStore.setState({ strategies: [mockStrategy] })
    vi.mocked(strategyApi.create).mockRejectedValueOnce(new Error('Create failed'))
    await useStrategyStore.getState().createStrategy({ name: 'X', code: '', description: '', parameters: {} })
    expect(useStrategyStore.getState().strategies).toHaveLength(1) // unchanged
  })

  // ---- updateStrategy ----
  it('updateStrategy should call strategyApi.update and update in-place', async () => {
    useStrategyStore.setState({ strategies: [mockStrategy] })
    vi.mocked(strategyApi.update).mockResolvedValueOnce({ ...mockStrategy, name: 'Updated' })
    await useStrategyStore.getState().updateStrategy('s1', { name: 'Updated', code: 'new' })
    expect(strategyApi.update).toHaveBeenCalledWith('s1', { name: 'Updated', code: 'new' })
    expect(useStrategyStore.getState().strategies[0].name).toBe('Updated')
  })

  // ---- deleteStrategy ----
  it('deleteStrategy should call strategyApi.delete and remove from strategies', async () => {
    useStrategyStore.setState({ strategies: [mockStrategy] })
    vi.mocked(strategyApi.delete).mockResolvedValueOnce(undefined)
    await useStrategyStore.getState().deleteStrategy('s1')
    expect(strategyApi.delete).toHaveBeenCalledWith('s1')
    expect(useStrategyStore.getState().strategies).toHaveLength(0)
  })

  it('deleteStrategy should clear currentStrategy if it matches deleted id', async () => {
    useStrategyStore.setState({ strategies: [mockStrategy], currentStrategy: mockStrategy })
    vi.mocked(strategyApi.delete).mockResolvedValueOnce(undefined)
    await useStrategyStore.getState().deleteStrategy('s1')
    expect(useStrategyStore.getState().currentStrategy).toBeNull()
  })

  it('deleteStrategy should keep currentStrategy if id does not match', async () => {
    const other: Strategy = { ...mockStrategy, id: 's2' }
    useStrategyStore.setState({ strategies: [mockStrategy, other], currentStrategy: other })
    vi.mocked(strategyApi.delete).mockResolvedValueOnce(undefined)
    await useStrategyStore.getState().deleteStrategy('s1')
    expect(useStrategyStore.getState().currentStrategy).toEqual(other)
  })

  it('deleteStrategy should not modify strategies on API error', async () => {
    useStrategyStore.setState({ strategies: [mockStrategy] })
    vi.mocked(strategyApi.delete).mockRejectedValueOnce(new Error('Delete failed'))
    await useStrategyStore.getState().deleteStrategy('s1')
    expect(useStrategyStore.getState().strategies).toHaveLength(1) // unchanged
  })

  // ---- setCurrentStrategy ----
  it('setCurrentStrategy should set currentStrategy', () => {
    useStrategyStore.getState().setCurrentStrategy(mockStrategy)
    expect(useStrategyStore.getState().currentStrategy).toEqual(mockStrategy)
  })

  it('setCurrentStrategy should clear currentStrategy with null', () => {
    useStrategyStore.getState().setCurrentStrategy(mockStrategy)
    useStrategyStore.getState().setCurrentStrategy(null)
    expect(useStrategyStore.getState().currentStrategy).toBeNull()
  })
})
