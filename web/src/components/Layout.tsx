import React, { ReactNode } from 'react'
import { Layout, Menu } from 'antd'
import {
  DashboardOutlined,
  ExperimentOutlined,
  AreaChartOutlined,
  RobotOutlined,
  EyeOutlined,
  FundOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import './Layout.css'

const { Header, Sider, Content } = Layout

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/backtest', icon: <ExperimentOutlined />, label: '回测' },
  { key: '/backtest/:id', icon: <AreaChartOutlined />, label: '回测结果', hidden: true },
  { key: '/ai-chat', icon: <RobotOutlined />, label: 'AI 对话' },
  { key: '/monitor', icon: <EyeOutlined />, label: '盯盘' },
  { key: '/portfolio', icon: <FundOutlined />, label: '组合' },
  { key: '/settings', icon: <SettingOutlined />, label: '设置' },
]

interface Props {
  children: ReactNode
}

export default function AppLayout({ children }: Props) {
  const navigate = useNavigate()
  const location = useLocation()

  const visibleItems = menuItems.filter((m) => !m.hidden)

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="light" breakpoint="lg" collapsedWidth={80}>
        <div style={{ padding: '16px', textAlign: 'center', fontWeight: 700, fontSize: 16, borderBottom: '1px solid #f0f0f0' }}>
          StockQuant
        </div>
        <Menu
          mode="inline"
          items={visibleItems}
          selectedKeys={[location.pathname]}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', borderBottom: '1px solid #f0f0f0' }}>
          <span style={{ fontSize: 18, fontWeight: 600 }}>量化交易平台 v2.0</span>
        </Header>
        <Content style={{ margin: 24, padding: 24, background: '#fff', borderRadius: 8 }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  )
}
