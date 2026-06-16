import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 5000,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.response.use(
  (r) => r.data,
  (error) => {
    if (error.response?.status >= 500) {
      console.warn(`API ${error.config?.url} returned ${error.response.status}`)
      return null
    }
    const msg = error.response?.data?.detail || error.message || '请求失败'
    return Promise.reject(new Error(msg))
  },
)

export default client
