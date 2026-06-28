import { useState, useCallback, useEffect } from 'react'
import { Tabs, Button, Space, message, Typography, Divider, Card } from 'antd'
import { SaveOutlined, ExpandOutlined, CompressOutlined } from '@ant-design/icons'
import { GeneralSettings, TradingSettings, AISettings, NotifierSettings, BrokerSettings, SoundSettings, DisplaySettings, RiskControlSettings } from '@/components/Settings'
import { useAuthStore } from '@/stores/authStore'
import client from '@/api/client'

const { Title, Text } = Typography

interface SettingsProps {}

// 后端配置字段映射
const KEY_TO_BACKEND: Record<string, string> = {
  'database.url': 'database.url',
  'database.pool_size': 'database.pool_size',
  'database.max_overflow': 'database.max_overflow',
  'database.pool_timeout': 'database.pool_timeout',
  'database.echo': 'database.echo',
  'trading.mode': 'trading.mode',
  'trading.broker': 'trading.broker',
  'trading.xtp_ip': 'trading.xtp_ip',
  'trading.xtp_port': 'trading.xtp_port',
  'trading.xtp_key': 'trading.xtp_key',
  'trading.xtp_account': 'trading.xtp_account',
  'trading.qmt_path': 'trading.qmt_path',
  'trading.qmt_account': 'trading.qmt_account',
  'trading.ctp_broker_id': 'trading.ctp_broker_id',
  'trading.ctp_user': 'trading.ctp_user',
  'trading.ctp_password': 'trading.ctp_password',
  'trading.ctp_front': 'trading.ctp_front',
  'system.log_level': 'system.log_level',
  'system.web_port': 'system.web_port',
  'system.initial_capital': 'system.initial_capital',
  'system.commission_rate': 'system.commission_rate',
  'system.min_commission': 'system.min_commission',
  'system.stamp_tax_rate': 'system.stamp_tax_rate',
  'system.slippage': 'system.slippage',
  'system.lot_size': 'system.lot_size',
  'system.price_limit_ratio': 'system.price_limit_ratio',
  'data_provider.source': 'data_provider.source',
  'data_provider.alphafeed_key': 'data_provider.alphafeed_key',
  'data_provider.api_key': 'data_provider.api_key',
  'data_provider.api_url': 'data_provider.api_url',
  'baostock.enabled': 'baostock.enabled',
}

const KEY_FROM_BACKEND: Record<string, string> = {}
Object.entries(KEY_TO_BACKEND).forEach(([fe, be]) => {
  KEY_FROM_BACKEND[be] = fe
})

function toFrontendKey(backendKey: string): string {
  return KEY_FROM_BACKEND[backendKey] || backendKey
}

function toBackendKey(frontendKey: string): string {
  return KEY_TO_BACKEND[frontendKey] || frontendKey
}

export default function Settings(_props: SettingsProps) {
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [saving, setSaving] = useState(false)
  const [viewMode, setViewMode] = useState<'wizard' | 'expert'>('wizard')
  const [activeKeys, setActiveKeys] = useState<string[]>([])

  const { user } = useAuthStore()
  const isAdmin = user?.role?.toUpperCase() === 'ADMIN'

  // 加载配置
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const res = await client.get('/api/settings')
        const data = res.data as Record<string, unknown>
        
        const frontendValues: Record<string, unknown> = {}
        Object.entries(data).forEach(([key, value]) => {
          if (key === 'jwt' || key === 'system') return
          const feKey = toFrontendKey(key)
          frontendValues[feKey] = value
        })
        
        // 处理嵌套的 system 配置
        if (data.system && typeof data.system === 'object') {
          Object.entries(data.system as Record<string, unknown>).forEach(([key, value]) => {
            const feKey = toFrontendKey(`system.${key}`)
            frontendValues[feKey] = value
          })
        }
        
        setValues(frontendValues)
      } catch (e) {
        console.error('加载配置失败:', e)
      }
    }
    loadSettings()
  }, [])

  const handleValueChange = useCallback((key: string, value: unknown) => {
    setValues(prev => ({ ...prev, [key]: value }))
  }, [])

  const handleSave = useCallback(async () => {
    setSaving(true)
    try {
      const backendValues: Record<string, unknown> = {}
      const systemValues: Record<string, unknown> = {}

      Object.entries(values).forEach(([key, value]) => {
        const beKey = toBackendKey(key)
        if (beKey.startsWith('system.')) {
          systemValues[beKey.replace('system.', '')] = value
        } else {
          backendValues[beKey] = value
        }
      })

      if (Object.keys(systemValues).length > 0) {
        backendValues['system'] = systemValues
      }

      await client.post('/api/settings', backendValues)
      message.success('设置已保存，部分配置重启后生效')
    } catch (e: any) {
      message.error('保存失败: ' + (e.message || '未知错误'))
    } finally {
      setSaving(false)
    }
  }, [values])

  return (
    <div style={{ padding: '0 24px' }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={4} style={{ margin: 0 }}>系统设置</Title>
        <Space>
          <Button 
            icon={viewMode === 'expert' ? <CompressOutlined /> : <ExpandOutlined />} 
            onClick={() => setViewMode(viewMode === 'expert' ? 'wizard' : 'expert')}
          >
            {viewMode === 'expert' ? '简化模式' : '专家模式'}
          </Button>
          <Button 
            type="primary" 
            icon={<SaveOutlined />} 
            onClick={handleSave} 
            loading={saving}
          >
            保存设置
          </Button>
        </Space>
      </div>

      <Tabs
        activeKey={activeKeys.length > 0 ? activeKeys[0] : (viewMode === 'expert' ? 'general' : 'broker')}
        onChange={(key) => setActiveKeys([key])}
        style={{ background: '#fff', padding: '0 16px' }}
        items={[
          {
            key: 'broker',
            label: '券商配置',
            children: (
              <BrokerSettings values={values} onChange={handleValueChange} />
            ),
          },
          {
            key: 'general',
            label: '通用设置',
            children: (
              <GeneralSettings values={values} onChange={handleValueChange} />
            ),
          },
          {
            key: 'trading',
            label: '交易设置',
            children: (
              <TradingSettings values={values} onChange={handleValueChange} />
            ),
          },
          {
            key: 'ai_model',
            label: 'AI 模型',
            children: (
              <AISettings values={values} onChange={handleValueChange} />
            ),
          },
          {
            key: 'notification',
            label: '通知设置',
            children: (
              <NotifierSettings values={values} onChange={handleValueChange} />
            ),
          },
          {
            key: 'sound',
            label: '声音',
            children: (
              <SoundSettings />
            ),
          },
          {
            key: 'display',
            label: '显示偏好',
            children: (
              <DisplaySettings />
            ),
          },
          {
            key: 'risk_control',
            label: '风控',
            children: (
              <RiskControlSettings />
            ),
          },
        ].filter(tab => {
          // 专家模式显示所有标签，简化模式显示券商/通知/声音/显示/风控
          if (viewMode === 'wizard') {
            return ['broker', 'notification', 'sound', 'display', 'risk_control'].includes(tab.key as string)
          }
          // 非管理员隐藏系统设置
          if (!isAdmin && tab.key === 'system') {
            return false
          }
          return true
        })}
      />

      {/* 管理员面板 - 仅管理员可见 */}
      {isAdmin && (
        <>
          <Divider />
          <Card size="small" title="高级设置">
            <Text type="secondary">
              管理员可以执行以下操作：
            </Text>
            {/* TODO: 添加管理员操作按钮 */}
          </Card>
        </>
      )}
    </div>
  )
}
