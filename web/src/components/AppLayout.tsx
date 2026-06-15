import { useEffect, useState } from 'react'
import { Layout, Menu } from 'antd'
import {
  ChartPie,
  Flask,
  ChartBar,
  ChatCenteredText,
  Eye,
  TrendUp,
  Gear,
  Code,
  Database,
} from '@phosphor-icons/react'
import { useNavigate, useLocation } from 'react-router-dom'

const { Header, Sider, Content } = Layout

const menuItems = [
  { key: '/', icon: <ChartPie size={18} weight="fill" />, label: '仪表盘' },
  { key: '/backtest', icon: <Flask size={18} weight="fill" />, label: '回测' },
  { key: '/backtest/:id', icon: <ChartBar size={18} weight="fill" />, label: '回测结果', hidden: true },
  { key: '/strategy', icon: <Code size={18} weight="fill" />, label: '策略' },
  { key: '/data', icon: <Database size={18} weight="fill" />, label: '数据' },
  { key: '/monitor', icon: <Eye size={18} weight="fill" />, label: '盯盘' },
  { key: '/portfolio', icon: <TrendUp size={18} weight="fill" />, label: '组合' },
  { key: '/ai-chat', icon: <ChatCenteredText size={18} weight="fill" />, label: 'AI 对话' },
  { key: '/settings', icon: <Gear size={18} weight="fill" />, label: '设置' },
]

interface Props {
  children: React.ReactNode
}

export default function AppLayout({ children }: Props) {
  const navigate = useNavigate()
  const location = useLocation()
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const visibleItems = menuItems.filter((m) => !m.hidden)

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        width={200}
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          background: 'var(--surface-elevated)',
          backdropFilter: 'blur(12px)',
        }}
      >
        <div style={{
          padding: '18px 16px',
          fontSize: 14,
          fontWeight: 700,
          letterSpacing: '0.08em',
          color: '#0066FF',
          borderBottom: '1px solid var(--surface-border)',
          fontFamily: 'var(--font-mono)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          <ChartPie size={22} weight="fill" />
          <span>STOCKQUANT</span>
          <span style={{ color: '#555', fontWeight: 400, fontSize: 11 }}>/ 2.0</span>
        </div>
        <Menu
          mode="inline"
          items={visibleItems}
          selectedKeys={[location.pathname]}
          onClick={({ key }) => navigate(key)}
          style={{ borderRight: 'none', paddingTop: 8, background: 'transparent' }}
        />
      </Sider>
      <Layout
        style={{
          marginLeft: 200,
          minHeight: '100vh',
          background: 'var(--surface)',
        }}
      >
        <Header style={{
          background: 'var(--surface-elevated)',
          borderBottom: '1px solid var(--surface-border)',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          height: 48,
        }}>
          <span style={{ fontSize: 12, color: '#666', fontFamily: 'var(--font-mono)' }}>
            Institutional Quantitative Trading Platform
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: '#10b981',
                boxShadow: '0 0 4px rgba(16,185,129,0.4)',
              }} />
              <span style={{ fontSize: 11, color: '#666', fontFamily: 'var(--font-mono)' }}>
                {time.toLocaleTimeString('zh-CN', { hour12: false })}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: '#0066FF',
                boxShadow: '0 0 4px rgba(0,102,255,0.4)',
              }} />
              <span style={{ fontSize: 11, color: '#666', fontFamily: 'var(--font-mono)' }}>
                API 52ms
              </span>
            </div>
          </div>
        </Header>
        <Content style={{
          margin: 16,
          padding: 20,
          background: 'var(--surface)',
          borderRadius: 8,
          minHeight: 280,
          border: '1px solid var(--surface-border)',
        }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  )
}
