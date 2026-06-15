import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Spin } from 'antd'
import AppLayout from './components/AppLayout'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Backtest = lazy(() => import('./pages/Backtest'))
const BacktestResult = lazy(() => import('./pages/BacktestResult'))
const Strategy = lazy(() => import('./pages/Strategy'))
const Data = lazy(() => import('./pages/Data'))
const Monitor = lazy(() => import('./pages/Monitor'))
const AIChat = lazy(() => import('./pages/AIChat'))
const Portfolio = lazy(() => import('./pages/Portfolio'))
const Settings = lazy(() => import('./pages/Settings'))
const Trading = lazy(() => import('./pages/Trading'))
const Optimize = lazy(() => import('./pages/Optimize'))

function PageLoader() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 'calc(100vh - 120px)' }}>
      <Spin size="large" />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
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
            <Route path="/settings" element={<Settings />} />
            <Route path="/trading" element={<Trading />} />
            <Route path="/optimize" element={<Optimize />} />
          </Routes>
        </Suspense>
      </AppLayout>
    </BrowserRouter>
  )
}
