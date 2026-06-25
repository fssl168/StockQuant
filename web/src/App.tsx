import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Spin } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AppLayout from './components/AppLayout'
import { useAuthStore } from './stores/authStore'
import Login from './pages/Login'
import { ErrorBoundary } from './components/ErrorBoundary'

// 创建 React Query 客户端
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 分钟内数据视为新鲜
      gcTime: 10 * 60 * 1000, // 10 分钟缓存
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Backtest = lazy(() => import('./pages/Backtest'))
const BacktestResult = lazy(() => import('./pages/BacktestResult'))
const Strategy = lazy(() => import('./pages/Strategy'))
const Data = lazy(() => import('./pages/Data'))
const Monitor = lazy(() => import('./pages/Monitor'))
const AIChat = lazy(() => import('./pages/AIChat'))
const Portfolio = lazy(() => import('./pages/Portfolio'))
const Settings = lazy(() => import('./pages/Settings'))
const TradingDemo = lazy(() => import('./pages/Trading'))
const Trading = lazy(() => import('./pages/Trading'))
const Optimize = lazy(() => import('./pages/Optimize'))
const Comparison = lazy(() => import('./pages/Comparison'))
const Memory = lazy(() => import('./pages/Memory'))
const Hallucination = lazy(() => import('./pages/Hallucination'))
const AIPipeline = lazy(() => import('./pages/AIPipeline'))

function PageLoader() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 'calc(100vh - 120px)' }}>
      <Spin size="large" />
    </div>
  )
}

/** 角色权限检查 */
function hasPermission(requiredRoles: string[], userRoles: string[]): boolean {
  if (!userRoles || userRoles.length === 0) return false
  return userRoles.some(role => requiredRoles.includes(role))
}

/** 路由守卫 - 基于角色权限 */
function RoleRoute({ 
  children, 
  requiredRoles = ['VIEWER', 'TRADER', 'ADMIN'] 
}: { 
  children: React.ReactNode
  requiredRoles?: string[]
}) {
  const { user } = useAuthStore()
  // roles 可能是字符串（逗号分隔）或数组
  const rawRoles = user?.roles
  const rawRole = user?.role
  
  let userRoles: string[] = []
  const rolesUnknown = rawRoles as unknown
  if (Array.isArray(rolesUnknown)) {
    userRoles = (rolesUnknown as string[]).map((r: string) => r.toUpperCase())
  } else if (typeof rolesUnknown === 'string' && rolesUnknown) {
    userRoles = rolesUnknown.split(',').map((r: string) => r.trim().toUpperCase())
  }
  // 也检查 role 字段
  if (typeof rawRole === 'string' && rawRole) {
    userRoles.push(rawRole.toUpperCase())
  }
  
  if (!hasPermission(requiredRoles, userRoles)) {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}

/** 认证守卫 */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, checkAuth } = useAuthStore()
  const location = useLocation()

  useEffect(() => {
    checkAuth()
    const onStorage = () => {
      if (!localStorage.getItem('auth_token')) {
        useAuthStore.setState({ token: null, user: null, isAuthenticated: false })
      }
    }
    window.addEventListener('storage', onStorage)
    const timer = setInterval(() => {
      if (!localStorage.getItem('auth_token') && useAuthStore.getState().isAuthenticated) {
        useAuthStore.setState({ token: null, user: null, isAuthenticated: false })
      }
    }, 1000)
    return () => {
      window.removeEventListener('storage', onStorage)
      clearInterval(timer)
    }
  }, [checkAuth])

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return <>{children}</>
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/*"
              element={
                <RequireAuth>
                  <AppLayout>
                    <Suspense fallback={<PageLoader />}>
                      <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/backtest" element={<Backtest />} />
                        <Route path="/backtest/:id" element={<BacktestResult />} />
                        <Route path="/strategy" element={<Strategy />} />
                        <Route path="/data" element={<Data />} />
                        <Route path="/monitor" element={<Monitor />} />
                        <Route path="/portfolio" element={<Portfolio />} />
                        <Route path="/ai-chat" element={<AIChat />} />
                        {/* 交易页面 */}
                        <Route path="/trading" element={<Trading />} />
                        {/* 设置页面 - 仅 ADMIN 可访问 */}
                        <Route path="/settings" element={<RoleRoute requiredRoles={['ADMIN']}><Settings /></RoleRoute>} />
                        <Route path="/optimize" element={<Optimize />} />
                        <Route path="/trading-demo" element={<TradingDemo />} />
                        <Route path="/comparison" element={<Comparison />} />
                        {/* AI 基础设施页面 - 仅 ADMIN 可访问 */}
                        <Route path="/memory" element={<Memory />} />
                        <Route path="/hallucination" element={<Hallucination />} />
                        <Route path="/ai-pipeline" element={<AIPipeline />} />
                      </Routes>
                    </Suspense>
                  </AppLayout>
                </RequireAuth>
              }
            />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}

