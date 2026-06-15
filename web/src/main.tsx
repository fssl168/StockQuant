import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#3b82f6',
          borderRadius: 8,
          colorBgBase: '#09090b',
          colorBgContainer: '#111113',
          colorBorder: '#27272a',
          fontFamily: 'var(--font-sans)',
          fontFamilyCode: 'var(--font-mono)',
        },
      }}
      locale={zhCN}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>,
)
