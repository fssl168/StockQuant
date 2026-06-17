import client from './client'

export const monitorApi = {
  start: (symbols: string[], interval = 60) =>
    client.post('/monitor/start-monitoring', { symbols, interval }) as Promise<unknown>,
  stop: () => client.post('/monitor/stop-monitoring') as Promise<unknown>,
  status: () => client.get('/monitor/status') as Promise<{ running: boolean }>,
  brief: (symbols?: string[]) => {
    const params = symbols ? `?symbols=${symbols.join(',')}` : ''
    return client.get(`/monitor/brief${params}`) as Promise<string>
  },
  summary: () => client.get('/monitor/summary') as Promise<{ summary: string }>,
  scan: (symbol: string) => client.get(`/monitor/scan/${symbol}`) as Promise<{ anomalies: { symbol: string; type: string; description: string; time: string }[] }>,
  getWatchlist: () =>
    client.get('/monitor/watchlist') as Promise<string[]>,
  updateWatchlist: (symbols: string[]) =>
    client.post('/monitor/watchlist', symbols) as Promise<string[]>,
}
