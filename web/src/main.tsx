import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import 'antd/dist/reset.css'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        token: {
          // Brand & layout
          colorPrimary: '#3b82f6',
          borderRadius: 8,
          colorBgBase: '#09090b',
          colorBgContainer: '#111113',
          colorBorder: '#27272a',
          fontFamily: 'var(--font-sans)',
          fontFamilyCode: 'var(--font-mono)',

          // Text colors — must match CSS variables exactly
          colorText: '#fafafa',
          colorTextSecondary: '#a1a1aa',
          colorTextTertiary: '#71717a',
          colorTextDisabled: '#52525b',

          // Background colors for different elevation levels
          colorBgLayout: '#09090b',
          colorBgElevated: '#111113',
          colorBgSpotlight: '#18181b',
          colorBgMask: 'rgba(0, 0, 0, 0.45)',

          // Fill / hover colors
          colorFill: 'rgba(255, 255, 255, 0.06)',
          colorFillSecondary: 'rgba(255, 255, 255, 0.04)',
          colorFillTertiary: 'rgba(255, 255, 255, 0.02)',

          // Border colors
          colorBorderSecondary: '#27272a',
        },
      }}
      locale={zhCN}>
      <AntApp>
      <App />
    </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
)
