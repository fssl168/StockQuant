import client from './client'

export const monitorApi = {
  start: (symbols: string[], interval = 60) =>
    client.post('/api/monitor/start-monitoring', { symbols, interval }) as Promise<unknown>,
  stop: () => client.post('/api/monitor/stop-monitoring') as Promise<unknown>,
  status: () => client.get('/api/monitor/status') as Promise<{ running: boolean }>,
  brief: (symbols?: string[]) => {
    const params = symbols ? `?symbols=${symbols.join(',')}` : ''
    return client.get(`/api/monitor/brief${params}`) as Promise<string>
  },
  summary: () => client.get('/api/monitor/summary') as Promise<{ summary: string }>,
  scan: (symbol: string) => client.get(`/api/monitor/scan/${symbol}`) as Promise<any[]>,
  getWatchlist: () =>
    client.get('/api/monitor/watchlist') as Promise<string[]>,
  updateWatchlist: (symbols: string[]) =>
    client.post('/api/monitor/watchlist', symbols) as Promise<string[]>,
  removeFromWatchlist: (symbols: string[]) =>
    client.delete('/api/monitor/watchlist', { data: symbols }) as Promise<string[]>,
}
