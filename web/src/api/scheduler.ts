import client from './client'

export const schedulerApi = {
  listTasks: () => client.get('/api/scheduler/tasks'),
  addTask: (data: any) => client.post('/api/scheduler/tasks', data),
  removeTask: (id: string) => client.delete(`/api/scheduler/tasks/${id}`),
  start: () => client.post('/api/scheduler/start'),
  stop: () => client.post('/api/scheduler/stop'),
  status: () => client.get('/api/scheduler/status'),
}
