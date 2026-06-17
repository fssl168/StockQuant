import axios from 'axios'

/**
 * Recursively convert object/darray keys from snake_case to camelCase.
 */
function snakeToCamel(obj: unknown): unknown {
  if (Array.isArray(obj)) {
    return obj.map(snakeToCamel)
  }
  if (obj !== null && typeof obj === 'object' && obj.constructor === Object) {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([key, value]) => [
        key.replace(/_([a-z])/g, (_, c) => c.toUpperCase()),
        snakeToCamel(value),
      ]),
    )
  }
  return obj
}

/** 从 localStorage 读取 JWT token */
function getToken(): string | null {
  try {
    return localStorage.getItem('auth_token')
  } catch {
    return null
  }
}

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 5000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器：自动附加 JWT token
client.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (r) => {
    // Convert snake_case keys to camelCase so frontend types work
    const data = snakeToCamel(r.data)
    return { ...r, data }
  },
  (error) => {
    const status = error.response?.status
    // 401 未认证：清除本地 token，跳转登录页
    if (status === 401) {
      try {
        localStorage.removeItem('auth_token')
      } catch {
        // ignore
      }
      // 避免在登录页重复跳转
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    if (status && status >= 500) {
      console.warn(`API ${error.config?.url} returned ${status}`)
      return null
    }
    const msg = error.response?.data?.detail || error.message || '请求失败'
    return Promise.reject(new Error(msg))
  },
)

export default client
