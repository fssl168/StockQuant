import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#0066FF',
          borderRadius: 8,
          colorBgBase: '#0a0a0a',
        },
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>,
)
