import { useEffect, useState, useCallback } from 'react'
import { Layout, Menu, Badge, Modal, Button, Dropdown, Avatar, Space } from 'antd'
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
  Brain,
  ShieldCheck,
  Funnel,
  Users,
  House,
  SignOut,
  User,
  CaretDown,
  WarningCircle,
  AppWindow,
  XCircle,
} from '@phosphor-icons/react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useNotificationStore } from '@/stores/notificationStore'
import { useAuthStore } from '@/stores/authStore'
import { useTradingStore } from '@/stores/tradingStore'
import { useLayoutStore } from '@/stores/layoutStore'
import { getLatencyColorClass } from '@/hooks/useNetworkStatus'
import InstitutionalLayout from '@/components/Layout/InstitutionalLayout'

const { Header, Sider, Content } = Layout

// ─── 角色元数据 ──────────────────────────────────────────────────

const ROLE_META: Record<string, { label: string; color: string; icon: string }> = {
  ADMIN: { label: '管理员', color: '#ef4444', icon: '🛡️' },
  TRADER: { label: '交易员', color: '#3b82f6', icon: '💼' },
  VIEWER: { label: '观察者', color: '#6b7280', icon: '👁️' },
}

// ─── 菜单配置（分组 + 角色过滤）────────────────────────────────

interface MenuItem {
  key: string
  icon: React.ReactNode
  label: string
  roles?: string[]  // 如果为空数组则表示全部角色可见
}

const menuGroups: { title?: string; items: MenuItem[] }[] = [
  {
    title: '交易研究',
    items: [
      { key: '/', icon: <ChartPie size={18} weight="fill" />, label: '仪表盘' },
      { key: '/strategy', icon: <Code size={18} weight="fill" />, label: '策略管理' },
      { key: '/backtest', icon: <Flask size={18} weight="fill" />, label: '回测' },
      { key: '/optimize', icon: <SlidersHorizontal size={18} weight="fill" />, label: '参数优化' },
      { key: '/comparison', icon: <ChartBar size={18} weight="fill" />, label: '策略对比' },
    ],
  },
  {
    title: '市场数据',
    items: [
      { key: '/monitor', icon: <Eye size={18} weight="fill" />, label: '盯盘' },
      { key: '/data', icon: <Database size={18} weight="fill" />, label: '数据管理' },
      { key: '/portfolio', icon: <TrendUp size={18} weight="fill" />, label: '投资组合' },
      { key: '/trading', icon: <CurrencyCircleDollar size={18} weight="fill" />, label: '交易' },
    ],
  },
  {
    title: 'AI 助手',
    items: [
      { key: '/ai-chat', icon: <ChatCenteredText size={18} weight="fill" />, label: 'AI 对话' },
    ],
  },
  {
    title: '系统管理',
    items: [
      { key: '/admin/users', icon: <Users size={18} weight="fill" />, label: '用户管理' },
      { key: '/settings', icon: <Gear size={18} weight="fill" />, label: '系统设置' },
      { key: '/admin/scheduler', icon: <House size={18} weight="fill" />, label: '调度器' },
      { key: '/admin/audit', icon: <ChartBar size={18} weight="fill" />, label: '审计日志' },
      { key: '/memory', icon: <Brain size={18} weight="fill" />, label: 'AI 记忆' },
      { key: '/hallucination', icon: <ShieldCheck size={18} weight="fill" />, label: '反幻觉' },
      { key: '/ai-pipeline', icon: <Funnel size={18} weight="fill" />, label: 'AI 管线' },
    ],
  },
]

// 拍平菜单项列表
const ALL_MENU_ITEMS: MenuItem[] = []
menuGroups.forEach(g => ALL_MENU_ITEMS.push(...g.items))

function canSee(item: MenuItem, role: string | undefined): boolean {
  if (!item.roles || item.roles.length === 0) return true
  return item.roles.includes(role || 'VIEWER')
}

interface Props {
  children: React.ReactNode
}

export default function AppLayout({ children }: Props) {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, isAuthenticated, logout } = useAuthStore()
  const { positions } = useTradingStore()
  const { institutionalEnabled, toggleInstitutional } = useLayoutStore()
  const [time, setTime] = useState(new Date())
  const [apiLatency, setApiLatency] = useState<number | null>(null)
  const [backendAvailable, setBackendAvailable] = useState(false)
  const [networkColor, setNetworkColor] = useState<'green' | 'yellow' | 'red' | 'offline'>('green')
  const [emergencyConfirm, setEmergencyConfirm] = useState(false)
  const [emergencyClosing, setEmergencyClosing] = useState(false)

  const { messages: notifMessages } = useWebSocket(backendAvailable ? '/ws/notification' : null)

  // 通知
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

  // 时钟
  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  // 健康检查
  useEffect(() => {
    const check = async () => {
      const start = performance.now()
      try {
        const res = await fetch('/api/health', { method: 'GET' })
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

  // 网络延迟颜色（绿<50ms / 黄<200ms / 红>200ms / 离线）
  useEffect(() => {
    if (!backendAvailable || apiLatency === null) {
      setNetworkColor('yellow')
      return
    }
    if (apiLatency <= 50) setNetworkColor('green')
    else if (apiLatency <= 200) setNetworkColor('yellow')
    else setNetworkColor('red')
  }, [backendAvailable, apiLatency])

  // 机构模式切换
  const handleToggleInstitutional = useCallback(() => {
    toggleInstitutional()
  }, [toggleInstitutional])

  // 紧急平仓
  const handleEmergencyClose = useCallback(() => {
    setEmergencyConfirm(true)
  }, [])

  const handleEmergencyCloseCancel = useCallback(() => {
    setEmergencyConfirm(false)
  }, [])

  const handleEmergencyCloseConfirm = useCallback(async () => {
    setEmergencyConfirm(false)
    setEmergencyClosing(true)
    try {
      const { placeOrder } = await import('@/api/trading')
      const positions = useTradingStore.getState().positions
      const openPositions = positions.filter((p) => p.shares > 0)
      await Promise.all(
        openPositions.map((p) =>
          placeOrder({
            symbol: p.symbol,
            side: 'SELL' as const,
            type: 'MARKET' as const,
            price: p.price,
            quantity: p.shares,
          })
        )
      )
      await useTradingStore.getState().refreshAll()
    } catch (err) {
      console.error('紧急平仓失败:', err)
    } finally {
      setEmergencyClosing(false)
    }
  }, [])

  // 筛选可见菜单项
  const role = user?.role
  ALL_MENU_ITEMS.filter(item => canSee(item, role))

  // 构建分组菜单数据
  const menuData = menuGroups
    .map(group => ({
      ...group,
      items: group.items.filter(item => canSee(item, role)),
    }))
    .filter(group => group.items.length > 0)

  // 用户菜单
  const userRole = ROLE_META[role || 'VIEWER'] || ROLE_META.VIEWER
  const userMenuItems = [
    {
      key: 'profile',
      icon: <User size={16} weight="fill" />,
      label: <span>{user?.username}</span>,
      disabled: true,
    },
    { type: 'divider' as const },
    {
      key: 'logout',
      icon: <SignOut size={16} weight="fill" />,
      label: '退出登录',
      danger: true,
      onClick: () => {
        logout()
        navigate('/login')
      },
    },
  ]

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
        {/* Logo 区 */}
        <div style={brandStyle}>
          <ChartPie size={24} weight="fill" />
          <span>STOCKQUANT</span>
          <span style={{ color: 'var(--color-text-tertiary)', fontWeight: 400, fontSize: 11, marginLeft: 'auto' }}>v2.0</span>
        </div>

        {/* 分组菜单 */}
        <Menu
          mode="inline"
          items={menuData.map(group => ({
            type: 'group',
            label: group.title && <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)', fontWeight: 600, letterSpacing: '0.05em' }}>{group.title}</span>,
            key: `group-${group.title}`,
            children: group.items.map(item => ({
              ...item,
              label: item.label,
            })),
          }))}
          selectedKeys={[location.pathname]}
          onClick={({ key }) => { if (!key.includes('group-')) navigate(key) }}
          style={menuStyle}
        />
      </Sider>

      <Layout style={{ marginLeft: 220, minHeight: '100vh', background: 'var(--color-bg-base)' }}>
        {/* 顶部栏 */}
        <Header style={headerStyle}>
          <span style={{ fontSize: 13, color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-mono)', fontWeight: 500 }}>
            Institutional Quantitative Trading Platform
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {/* 后端状态 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: apiLatency !== null ? 'var(--color-success)' : 'var(--color-danger)',
                boxShadow: `0 0 6px ${apiLatency !== null ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)'}`,
              }} />
              <span style={{ fontSize: 11, color: getLatencyColorClass(networkColor), fontFamily: 'var(--font-mono)' }}>
                {apiLatency !== null ? `${apiLatency}ms` : '离线'}
              </span>
            </div>

            {/* 机构模式切换 */}
            {(user?.role === 'TRADER' || user?.role === 'ADMIN') && (
              <button
                onClick={handleToggleInstitutional}
                style={{
                  fontSize: 11,
                  color: institutionalEnabled ? 'var(--color-brand-primary)' : 'var(--color-text-tertiary)',
                  background: institutionalEnabled ? 'rgba(139,92,246,0.12)' : 'transparent',
                  border: `1px solid ${institutionalEnabled ? 'var(--color-brand-primary)' : 'var(--color-border-default)'}`,
                  borderRadius: 4,
                  padding: '2px 8px',
                  cursor: 'pointer',
                  fontFamily: 'var(--font-mono)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  transition: 'all 150ms ease',
                }}
              >
                <AppWindow size={12} weight="fill" />
                机构模式
              </button>
            )}

            {/* 紧急平仓 */}
            {(user?.role === 'TRADER' || user?.role === 'ADMIN') && positions.length > 0 && (
              <Button
                danger
                size="small"
                icon={<XCircle size={14} weight="bold" />}
                onClick={handleEmergencyClose}
                loading={emergencyClosing}
                style={{
                  background: '#ff4d4f',
                  borderColor: '#ff4d4f',
                  color: '#fff',
                  fontWeight: 600,
                  fontSize: 11,
                  height: 24,
                  padding: '0 8px',
                }}
              >
                紧急平仓
              </Button>
            )}

            {/* 时间 */}
            <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-mono)' }}>
              {time.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>

            {/* 角色徽标 */}
            {isAuthenticated && user && (
              <Badge
                count={
                  <span style={{ fontSize: 11, color: '#fff', fontWeight: 600 }}>
                    {userRole.icon} {userRole.label}
                  </span>
                }
                style={{
                  backgroundColor: `${userRole.color}22`,
                  borderColor: userRole.color,
                  borderWidth: 1,
                  borderStyle: 'solid',
                  borderRadius: 4,
                  padding: '2px 8px',
                }}
              />
            )}

            {/* GitHub */}
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

            {/* 用户菜单 */}
            {isAuthenticated && user && (
              <Dropdown
                menu={{ items: userMenuItems }}
                placement="bottomRight"
                arrow
              >
                <Space
                  style={{ cursor: 'pointer', paddingLeft: 4, paddingRight: 4 }}
                  onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.8' }}
                  onMouseLeave={(e) => { e.currentTarget.style.opacity = '1' }}
                >
                  <Avatar size="small" style={{ backgroundColor: userRole.color }}>
                    {userRole.icon}
                  </Avatar>
                  <span style={{ fontSize: 13, color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono)' }}>
                    {user.username}
                  </span>
                  <CaretDown size={12} weight="fill" />
                </Space>
              </Dropdown>
            )}
          </div>
        </Header>

        {/* 内容区 */}
        <Content style={contentStyle}>
          {institutionalEnabled ? (
            <InstitutionalLayout
              primaryContent={children}
              secondaryContent={<div style={{ textAlign: 'center', color: 'var(--color-text-tertiary)', fontSize: 11, paddingTop: 40 }}>大盘副屏<br /><span style={{ opacity: 0.6 }}>指数 · 热力图</span></div>}
              tertiaryContent={<div style={{ textAlign: 'center', color: 'var(--color-text-tertiary)', fontSize: 11, paddingTop: 40 }}>交易副屏<br /><span style={{ opacity: 0.6 }}>下单 · 持仓</span></div>}
            />
          ) : (
            children
          )}
        </Content>

        {/* 紧急平仓确认 */}
        <Modal
          title={
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <WarningCircle size={20} weight="fill" style={{ color: '#ff4d4f' }} />
              紧急平仓确认
            </span>
          }
          open={emergencyConfirm}
          onCancel={handleEmergencyCloseCancel}
          onOk={handleEmergencyCloseConfirm}
          okText="确认平仓"
          cancelText="取消"
          okButtonProps={{ danger: true, loading: emergencyClosing }}
          centered
        >
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>
            将平仓 <strong>{positions.filter((p) => p.shares > 0).length}</strong> 只持仓，确定执行？
          </p>
          <p style={{ color: '#ff4d4f', fontSize: 12, margin: 0 }}>
            <strong>警告：</strong>此操作不可撤销，所有订单将以市价提交。
          </p>
        </Modal>
      </Layout>
    </Layout>
  )
}
