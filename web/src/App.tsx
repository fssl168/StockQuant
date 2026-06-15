import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Backtest from './pages/Backtest'
import BacktestResult from './pages/BacktestResult'
import AIChat from './pages/AIChat'
import Monitor from './pages/Monitor'
import Portfolio from './pages/Portfolio'
import Settings from './pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/backtest" element={<Backtest />} />
          <Route path="/backtest/:id" element={<BacktestResult />} />
          <Route path="/ai-chat" element={<AIChat />} />
          <Route path="/monitor" element={<Monitor />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
