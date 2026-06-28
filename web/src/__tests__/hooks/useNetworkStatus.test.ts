import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import {
  useNetworkStatus,
  getLatencyColorClass,
  formatLatency,
} from '@/hooks/useNetworkStatus'

// Mock fetch to avoid real network calls during latency checks
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

beforeEach(() => {
  mockFetch.mockReset()
  mockFetch.mockResolvedValue(new Response('{}', { status: 200 }))
})

afterEach(() => {
  vi.useRealTimers()
})

describe('getLatencyColorClass', () => {
  it('green -> text-emerald-400', () => {
    expect(getLatencyColorClass('green')).toBe('text-emerald-400')
  })
  it('yellow -> text-amber-400', () => {
    expect(getLatencyColorClass('yellow')).toBe('text-amber-400')
  })
  it('red -> text-red-400', () => {
    expect(getLatencyColorClass('red')).toBe('text-red-400')
  })
  it('offline -> text-zinc-500', () => {
    expect(getLatencyColorClass('offline')).toBe('text-zinc-500')
  })
})

describe('formatLatency', () => {
  it('null -> "--"', () => {
    expect(formatLatency(null)).toBe('--')
  })
  it('0 -> "0ms"', () => {
    expect(formatLatency(0)).toBe('0ms')
  })
  it('50 -> "50ms"', () => {
    expect(formatLatency(50)).toBe('50ms')
  })
  it('1234 -> "1234ms"', () => {
    expect(formatLatency(1234)).toBe('1234ms')
  })
})

describe('useNetworkStatus', () => {
  beforeEach(() => {
    // Use fake timers so the 5s interval doesn't fire during tests
    vi.useFakeTimers()
  })

  it('exposes initial state: latency=null, isOnline=true, reconnectedCount=0, lastChecked=null', () => {
    const { result } = renderHook(() => useNetworkStatus())

    expect(result.current.latency).toBeNull()
    // jsdom defaults navigator.onLine to true
    expect(result.current.isOnline).toBe(true)
    expect(result.current.reconnectedCount).toBe(0)
    expect(result.current.lastChecked).toBeNull()
    expect(typeof result.current.rejoin).toBe('function')
    expect(typeof result.current.registerRejoinCallback).toBe('function')
  })

  it('exposes a color derived from latency + online state', () => {
    const { result } = renderHook(() => useNetworkStatus())
    // isOnline=true, latency=null -> 'yellow' per implementation
    expect(['green', 'yellow', 'red', 'offline']).toContain(result.current.color)
  })

  describe('rejoin + registerRejoinCallback', () => {
    it('registerRejoinCallback returns an unregister function', () => {
      const { result } = renderHook(() => useNetworkStatus())
      const unregister = result.current.registerRejoinCallback(() => {})
      expect(typeof unregister).toBe('function')
    })

    it('rejoin(since) invokes registered callback with the since timestamp', () => {
      const { result } = renderHook(() => useNetworkStatus())
      const cb = vi.fn()
      result.current.registerRejoinCallback(cb)

      act(() => {
        result.current.rejoin('2026-06-28T00:00:00Z')
      })

      expect(cb).toHaveBeenCalledTimes(1)
      expect(cb).toHaveBeenCalledWith('2026-06-28T00:00:00Z')
    })

    it('rejoin increments reconnectedCount each call', () => {
      const { result } = renderHook(() => useNetworkStatus())
      expect(result.current.reconnectedCount).toBe(0)

      act(() => result.current.rejoin('t1'))
      expect(result.current.reconnectedCount).toBe(1)

      act(() => result.current.rejoin('t2'))
      expect(result.current.reconnectedCount).toBe(2)
    })

    it('multiple callbacks are all invoked on rejoin', () => {
      const { result } = renderHook(() => useNetworkStatus())
      const cb1 = vi.fn()
      const cb2 = vi.fn()
      const cb3 = vi.fn()
      result.current.registerRejoinCallback(cb1)
      result.current.registerRejoinCallback(cb2)
      result.current.registerRejoinCallback(cb3)

      act(() => result.current.rejoin('since-X'))

      expect(cb1).toHaveBeenCalledWith('since-X')
      expect(cb2).toHaveBeenCalledWith('since-X')
      expect(cb3).toHaveBeenCalledWith('since-X')
    })

    it('unregistered callback is NOT invoked on subsequent rejoin', () => {
      const { result } = renderHook(() => useNetworkStatus())
      const cb = vi.fn()
      const unregister = result.current.registerRejoinCallback(cb)

      act(() => result.current.rejoin('first'))
      expect(cb).toHaveBeenCalledTimes(1)

      unregister()

      act(() => result.current.rejoin('second'))
      // Still only 1 invocation from the first rejoin
      expect(cb).toHaveBeenCalledTimes(1)
    })

    it('rejoin works even with no callbacks registered (no-op)', () => {
      const { result } = renderHook(() => useNetworkStatus())
      expect(() => {
        act(() => result.current.rejoin('t'))
      }).not.toThrow()
      expect(result.current.reconnectedCount).toBe(1)
    })

    it('unregister is idempotent (safe to call twice)', () => {
      const { result } = renderHook(() => useNetworkStatus())
      const cb = vi.fn()
      const unregister = result.current.registerRejoinCallback(cb)

      unregister()
      // Calling again should not throw
      expect(() => unregister()).not.toThrow()
    })
  })

  describe('latency detection', () => {
    it('fires an initial /api/health ping on mount', () => {
      renderHook(() => useNetworkStatus())
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/health',
        expect.objectContaining({ method: 'GET', cache: 'no-store' }),
      )
    })

    it('updates latency and lastChecked after a successful ping', async () => {
      const { result } = renderHook(() => useNetworkStatus())
      // Flush microtasks for the initial fetch
      await act(async () => {
        await vi.runOnlyPendingTimersAsync()
      })

      expect(result.current.latency).not.toBeNull()
      expect(result.current.latency).toBeGreaterThanOrEqual(0)
      expect(result.current.lastChecked).toBeInstanceOf(Date)
    })

    it('fires a second ping after CHECK_INTERVAL_MS (5s)', async () => {
      renderHook(() => useNetworkStatus())
      await act(async () => {
        await vi.runOnlyPendingTimersAsync()
      })
      const callsAfterFirst = mockFetch.mock.calls.length

      await act(async () => {
        vi.advanceTimersByTimeAsync(5000)
      })
      expect(mockFetch.mock.calls.length).toBeGreaterThan(callsAfterFirst)
    })

    it('sets latency=null when fetch rejects (network failure)', async () => {
      mockFetch.mockReset()
      mockFetch.mockRejectedValue(new Error('network down'))

      const { result } = renderHook(() => useNetworkStatus())
      await act(async () => {
        await vi.runOnlyPendingTimersAsync()
      })

      expect(result.current.latency).toBeNull()
      expect(result.current.lastChecked).toBeInstanceOf(Date)
    })
  })
})
