import client from './client'

export const adminApi = {
  listUsers: () => client.get('/api/admin/users'),
  createUser: (data: { username: string; password: string; roles: string[] }) =>
    client.post('/api/admin/users', data),
  updateUser: (userId: string, data: { roles?: string[]; disabled?: boolean }) =>
    client.put(`/api/admin/users/${userId}`, data),
  resetPassword: (userId: string, password: string) =>
    client.post(`/api/admin/users/${userId}/password`, { password }),
  toggleDisable: (userId: string) =>
    client.post(`/api/admin/users/${userId}/toggle-disable`),
  deleteUser: (userId: string) =>
    client.delete(`/api/admin/users/${userId}`),
}
