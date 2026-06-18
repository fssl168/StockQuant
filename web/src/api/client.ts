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
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 30000,
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
    // Convert snake_case keys to camelCase so frontend types work.
    // 直接返回响应体数据（而非整个 axios response），与各调用方及单测 mock 的契约一致。
    return snakeToCamel(r.data) as any
  },
  (error) => {
    const status = error.response?.status
    // 401 未认证：清除本地 token，由 React Router 守卫处理跳转
    if (status === 401) {
      try {
        localStorage.removeItem('auth_token')
      } catch {
        // ignore
      }
    }
    // 统一错误处理：5xx 不再返回 null，而是 reject Error
    // 调用方通过 try/catch 处理错误
    const msg = error.response?.data?.detail || error.message || '请求失败'
    return Promise.reject(new Error(msg))
  },
)

export default client
