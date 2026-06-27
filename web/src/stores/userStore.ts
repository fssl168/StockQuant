import { create } from 'zustand'
import client from '@/api/client'

export interface User {
  id: string
  username: string
  roles: string[]
  disabled: boolean
  createdAt: string
  lastLoginAt?: string
}

interface UserState {
  users: User[]
  loading: boolean
  fetchUsers: () => Promise<void>
  createUser: (data: { username: string; password: string; roles: string[] }) => Promise<void>
  updateUser: (userId: string, data: { roles?: string[]; disabled?: boolean }) => Promise<void>
  resetPassword: (userId: string, password: string) => Promise<void>
  toggleDisable: (userId: string) => Promise<void>
  deleteUser: (userId: string) => Promise<void>
}

function normalizeUser(u: any): User {
  return {
    id: u.id ?? u.userId ?? '',
    username: u.username ?? '',
    roles: Array.isArray(u.roles) ? u.roles : [u.roles ?? 'VIEWER'],
    disabled: !!u.disabled,
    createdAt: u.createdAt ?? u.created_at ?? '',
    lastLoginAt: u.lastLoginAt ?? u.last_login_at,
  }
}

export const useUserStore = create<UserState>((set, get) => ({
  users: [],
  loading: false,

  fetchUsers: async () => {
    set({ loading: true })
    try {
      const res = await client.get('/api/admin/users')
      set({ users: (res as unknown as any[]).map(normalizeUser), loading: false })
    } catch (e: any) {
      set({ loading: false })
      throw e
    }
  },

  createUser: async (data) => {
    await client.post('/api/admin/users', data)
    await get().fetchUsers()
  },

  updateUser: async (userId, data) => {
    await client.put(`/api/admin/users/${userId}`, data)
    await get().fetchUsers()
  },

  resetPassword: async (userId, password) => {
    await client.post(`/api/admin/users/${userId}/password`, { password })
  },

  toggleDisable: async (userId) => {
    await client.post(`/api/admin/users/${userId}/toggle-disable`)
    await get().fetchUsers()
  },

  deleteUser: async (userId) => {
    await client.delete(`/api/admin/users/${userId}`)
    await get().fetchUsers()
  },
}))
