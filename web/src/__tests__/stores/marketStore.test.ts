import { describe, it, expect, beforeEach } from 'vitest'
import { useMarketStore } from '@/stores/marketStore'

describe('MarketStore', () => {
  beforeEach(() => {
    // Reset to initial state
    useMarketStore.setState({
      symbols: ['sh600519', 'sz000858', 'sh601318'],
    })
  })

  // ---- initial state ----
  it('should have default symbols on init', () => {
    expect(useMarketStore.getState().symbols).toEqual(['sh600519', 'sz000858', 'sh601318'])
  })

  // ---- addSymbol ----
  it('addSymbol should append a new symbol', () => {
    useMarketStore.getState().addSymbol('sh600036')
    expect(useMarketStore.getState().symbols).toContain('sh600036')
    expect(useMarketStore.getState().symbols).toHaveLength(4)
  })

  it('addSymbol should allow duplicate symbols (no dedup)', () => {
    useMarketStore.getState().addSymbol('sh600519')
    const symbols = useMarketStore.getState().symbols
    const count = symbols.filter((s) => s === 'sh600519').length
    expect(count).toBe(2)
  })

  it('addSymbol should add to empty list', () => {
    useMarketStore.setState({ symbols: [] })
    useMarketStore.getState().addSymbol('sz000001')
    expect(useMarketStore.getState().symbols).toEqual(['sz000001'])
  })

  // ---- removeSymbol ----
  it('removeSymbol should remove existing symbol', () => {
    useMarketStore.getState().removeSymbol('sz000858')
    expect(useMarketStore.getState().symbols).not.toContain('sz000858')
    expect(useMarketStore.getState().symbols).toHaveLength(2)
  })

  it('removeSymbol should do nothing if symbol does not exist', () => {
    useMarketStore.getState().removeSymbol('nonexistent')
    expect(useMarketStore.getState().symbols).toHaveLength(3)
  })

  it('removeSymbol on empty list should not throw', () => {
    useMarketStore.setState({ symbols: [] })
    expect(() => useMarketStore.getState().removeSymbol('sh600519')).not.toThrow()
    expect(useMarketStore.getState().symbols).toEqual([])
  })

  // ---- clear ----
  it('clear should empty the symbols array', () => {
    useMarketStore.getState().clear()
    expect(useMarketStore.getState().symbols).toEqual([])
  })

  it('clear followed by addSymbol should work correctly', () => {
    useMarketStore.getState().clear()
    useMarketStore.getState().addSymbol('sh601398')
    expect(useMarketStore.getState().symbols).toEqual(['sh601398'])
  })
})
