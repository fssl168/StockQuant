import { create } from 'zustand'
import client from '@/api/client'

interface User {
  username: string
  roles: string[]
  role?: string  // 主角色（取 roles[0]）
}

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
  hasRole: (role: string) => boolean
}

export const useAuthStore = create<AuthState>((set, get) => ({
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
      const res = await client.post('/api/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      // 拦截器直接返回响应体裸数据（已 camelCase），无需再读 .data
      const data = res as any
      const token = data.accessToken
      const user: User = data.user || { username, roles: [] }
      // 补全主角色
      user.role = user.roles?.[0]?.toUpperCase() || 'VIEWER'
      localStorage.setItem('auth_token', token)
      set({ token, user, isAuthenticated: true, loading: false })
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
      const res = await client.get('/api/auth/me')
      // /auth/me 直接返回 user 对象；拦截器返回裸数据，无需再读 .data
      const user = res as unknown as User
      user.role = user.roles?.[0]?.toUpperCase() || 'VIEWER'
      set({ token, user, isAuthenticated: true })
    } catch {
      localStorage.removeItem('auth_token')
      set({ token: null, user: null, isAuthenticated: false })
    }
  },

  hasRole: (role: string) => {
    const state = get()
    return state.user?.roles?.map(r => r.toUpperCase()).includes(role.toUpperCase())
      || state.user?.role?.toUpperCase() === role.toUpperCase()
  },
}))
