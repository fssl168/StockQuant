import client from './client'

export const schedulerApi = {
  listTasks: () => client.get('/scheduler/tasks'),
  addTask: (data: any) => client.post('/scheduler/tasks', data),
  removeTask: (id: string) => client.delete(`/scheduler/tasks/${id}`),
  start: () => client.post('/scheduler/start'),
  stop: () => client.post('/scheduler/stop'),
  status: () => client.get('/scheduler/status'),
}
