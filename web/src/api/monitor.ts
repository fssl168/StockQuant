import client from './client'

export const monitorApi = {
  start: (symbols: string[], interval = 60) =>
    client.post('/monitor/start-monitoring', { symbols, interval }) as Promise<unknown>,
  stop: () => client.post('/monitor/stop-monitoring') as Promise<unknown>,
  status: () => client.get('/monitor/status') as Promise<{ running: boolean }>,
  brief: () => client.get('/monitor/brief') as Promise<{ brief: string }>,
}
