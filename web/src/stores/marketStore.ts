import { create } from 'zustand'

interface MarketState {
  symbols: string[]
  addSymbol: (s: string) => void
  removeSymbol: (s: string) => void
  addWatchlist: (list: string[]) => void
  removeWatchlist: (list: string[]) => void
  clear: () => void
}

export const useMarketStore = create<MarketState>((set) => ({
  symbols: ['sh600519', 'sz000858', 'sh601318'],
  addSymbol: (s) => set((st) => ({ symbols: [...st.symbols, s] })),
  removeSymbol: (s) => set((st) => ({ symbols: st.symbols.filter((x) => x !== s) })),
  addWatchlist: (list) => set((st) => ({ symbols: [...new Set([...st.symbols, ...list])] })),
  removeWatchlist: (list) => set((st) => ({ symbols: st.symbols.filter((x) => !list.includes(x)) })),
  clear: () => set({ symbols: [] }),
}))
