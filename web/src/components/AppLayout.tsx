import { useEffect, useState } from 'react'
import { Layout, Menu, Badge } from 'antd'
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
  ArrowSquareOut,
  CurrencyCircleDollar,
  SlidersHorizontal,
} from '@phosphor-icons/react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useNotificationStore } from '@/stores/notificationStore'

const { Header, Sider, Content } = Layout

const menuItems = [
  { key: '/', icon: <ChartPie size={20} weight="fill" />, label: '仪表盘' },
  { key: '/backtest', icon: <Flask size={20} weight="fill" />, label: '回测' },
  { key: '/backtest/:id', icon: <ChartBar size={20} weight="fill" />, label: '回测结果', hidden: true },
  { key: '/strategy', icon: <Code size={20} weight="fill" />, label: '策略' },
  { key: '/data', icon: <Database size={20} weight="fill" />, label: '数据' },
  { key: '/monitor', icon: <Eye size={20} weight="fill" />, label: '盯盘' },
  { key: '/trading', icon: <CurrencyCircleDollar size={20} weight="fill" />, label: '交易' },
  { key: '/optimize', icon: <SlidersHorizontal size={20} weight="fill" />, label: '优化' },
  { key: '/portfolio', icon: <TrendUp size={20} weight="fill" />, label: '组合' },
  { key: '/ai-chat', icon: <ChatCenteredText size={20} weight="fill" />, label: 'AI 对话' },
  { key: '/settings', icon: <Gear size={20} weight="fill" />, label: '设置' },
]

interface Props {
  children: React.ReactNode
}

export default function AppLayout({ children }: Props) {
  const navigate = useNavigate()
  const location = useLocation()
  const [time, setTime] = useState(new Date())
  const [apiLatency, setApiLatency] = useState<number | null>(null)
  const [backendAvailable, setBackendAvailable] = useState(false)

  const { messages: notifMessages } = useWebSocket(backendAvailable ? '/ws/notification' : null)

  useEffect(() => {
    if (notifMessages.length === 0) return
    const latest = notifMessages[notifMessages.length - 1]
    if (latest.type === 'notification' || latest.type === 'alert') {
      const data = latest.data as { type?: string; title?: string; message?: string }
      useNotificationStore.getState().add({
        type: (data.type ?? 'info') as 'signal' | 'alert' | 'info',
        title: data.title ?? '系统通知',
        message: data.message ?? '',
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      })
    }
  }, [notifMessages])

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const check = async () => {
      const start = performance.now()
      try {
        const res = await fetch('/api/health', { method: 'HEAD', signal: AbortSignal.timeout(3000) })
        setApiLatency(Math.round(performance.now() - start))
        setBackendAvailable(res.ok)
      } catch {
        setApiLatency(null)
        setBackendAvailable(false)
      }
    }
    check()
    const interval = setInterval(check, 30000)
    return () => clearInterval(interval)
  }, [])

  const visibleItems = menuItems.filter((m) => !m.hidden)

  const siderStyle: React.CSSProperties = {
    overflow: 'auto',
    height: '100vh',
    position: 'fixed',
    left: 0,
    top: 0,
    bottom: 0,
    background: 'var(--color-bg-elevated)',
    borderRight: '1px solid var(--color-border-default)',
  }

  const headerStyle: React.CSSProperties = {
    background: 'var(--color-bg-elevated)',
    borderBottom: '1px solid var(--color-border-default)',
    padding: '0 24px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 52,
    backdropFilter: 'blur(8px)',
  }

  const contentStyle: React.CSSProperties = {
    margin: 16,
    padding: 16,
    background: 'var(--color-bg-base)',
    minHeight: 'calc(100vh - 52px - 32px)',
    borderRadius: 8,
    border: '1px solid var(--color-border-default)',
  }

  const brandStyle: React.CSSProperties = {
    padding: '20px 18px',
    fontSize: 14,
    fontWeight: 700,
    letterSpacing: '0.08em',
    color: 'var(--color-brand-primary)',
    borderBottom: '1px solid var(--color-border-default)',
    fontFamily: 'var(--font-mono)',
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    userSelect: 'none',
  }

  const menuStyle: React.CSSProperties = {
    borderRight: 'none',
    paddingTop: 8,
    background: 'transparent',
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider width={220} style={siderStyle}>
        <div style={brandStyle}>
          <ChartPie size={24} weight="fill" />
          <span>STOCKQUANT</span>
          <span style={{ color: 'var(--color-text-tertiary)', fontWeight: 400, fontSize: 11, marginLeft: 'auto' }}>v2.0</span>
        </div>
        <Menu
          mode="inline"
          items={visibleItems}
          selectedKeys={[location.pathname]}
          onClick={({ key }) => navigate(key)}
          style={menuStyle}
        />
      </Sider>

      <Layout style={{ marginLeft: 220, minHeight: '100vh', background: 'var(--color-bg-base)' }}>
        <Header style={headerStyle}>
          <span style={{ fontSize: 13, color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-mono)', fontWeight: 500 }}>
            Institutional Quantitative Trading Platform
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: apiLatency !== null ? 'var(--color-success)' : 'var(--color-danger)',
                boxShadow: `0 0 6px ${apiLatency !== null ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)'}`,
              }} />
              <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                {apiLatency !== null ? `${apiLatency}ms` : '离线'}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Badge dot />
              <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                {time.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            </div>
            <a
              href="https://github.com/fssl168/StockQuant"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: 'var(--color-text-tertiary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 28,
                height: 28,
                borderRadius: 4,
                transition: 'color 150ms ease',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-brand-primary)' }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-text-tertiary)' }}
              aria-label="GitHub"
            >
              <ArrowSquareOut size={16} weight="bold" />
            </a>
          </div>
        </Header>

        <Content style={contentStyle}>
          {children}
        </Content>
      </Layout>
    </Layout>
  )
}
