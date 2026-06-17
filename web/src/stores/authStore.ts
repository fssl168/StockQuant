import { create } from 'zustand'
import client from '@/api/client'

interface User {
  username: string
  roles: string[]
}

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('auth_token'),
  user: null,
  isAuthenticated: !!localStorage.getItem('auth_token'),
  loading: false,

  login: async (username: string, password: string) => {
    set({ loading: true })
    try {
      const formData = new URLSearchParams()
      formData.append('username', username)
      formData.append('password', password)
      const res = await client.post('/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      const { access_token, user } = res.data as any
      localStorage.setItem('auth_token', access_token)
      set({ token: access_token, user, isAuthenticated: true, loading: false })
    } catch (e: any) {
      set({ loading: false })
      throw e
    }
  },

  logout: () => {
    localStorage.removeItem('auth_token')
    set({ token: null, user: null, isAuthenticated: false })
  },

  checkAuth: async () => {
    const token = localStorage.getItem('auth_token')
    if (!token) {
      set({ token: null, user: null, isAuthenticated: false })
      return
    }
    try {
      const res = await client.get('/auth/me')
      const user = res.data as User
      set({ token, user, isAuthenticated: true })
    } catch {
      localStorage.removeItem('auth_token')
      set({ token: null, user: null, isAuthenticated: false })
    }
  },
}))
