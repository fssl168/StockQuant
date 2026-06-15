import { BrowserRouter, Routes, Route } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import Dashboard from './pages/Dashboard'
import Backtest from './pages/Backtest'
import BacktestResult from './pages/BacktestResult'
import Strategy from './pages/Strategy'
import Data from './pages/Data'
import Monitor from './pages/Monitor'
import AIChat from './pages/AIChat'
import Portfolio from './pages/Portfolio'
import Settings from './pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout>
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
        </Routes>
      </AppLayout>
    </BrowserRouter>
  )
}
