import { create } from 'zustand'

interface MarketState {
  symbols: string[]
  addSymbol: (s: string) => void
  removeSymbol: (s: string) => void
  clear: () => void
}

export const useMarketStore = create<MarketState>((set) => ({
  symbols: ['sh600519', 'sz000858', 'sh601318'],
  addSymbol: (s) => set((st) => ({ symbols: [...st.symbols, s] })),
  removeSymbol: (s) => set((st) => ({ symbols: st.symbols.filter((x) => x !== s) })),
  clear: () => set({ symbols: [] }),
}))
