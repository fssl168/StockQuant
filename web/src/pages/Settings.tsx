import { useState, useCallback, useEffect } from 'react'
import { SaveOutlined } from '@ant-design/icons'
import { message } from '@/utils/message'
import { GeneralSettings, TradingSettings, AISettings, NotifierSettings, BrokerSettings, SoundSettings, DisplaySettings, RiskControlSettings } from '@/components/Settings'
import { CategorySidebar } from '@/components/Settings/CategorySidebar'
import { SettingsAlert } from '@/components/Settings/SettingsAlert'
import { useAuthStore } from '@/stores/authStore'
import client from '@/api/client'
import { ChartBar, Bell, SpeakerX, ShieldCheck, Gear, Brain, CurrencyCircleDollar } from '@phosphor-icons/react'

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

// 分类定义（与 Tab 顺序一致）
const CATEGORIES: { key: string; title: string; icon: React.ReactNode; description: string; fieldCount: number }[] = [
  { key: 'broker', title: '券商配置', icon: <CurrencyCircleDollar size={16} weight="fill" />, description: '交易通道与连接参数', fieldCount: 0 },
  { key: 'general', title: '通用设置', icon: <Gear size={16} weight="fill" />, description: '数据库、系统控制、数据源', fieldCount: 0 },
  { key: 'trading', title: '交易设置', icon: <ChartBar size={16} weight="fill" />, description: '佣金、滑点、执行参数', fieldCount: 0 },
  { key: 'ai_model', title: 'AI 模型', icon: <Brain size={16} weight="fill" />, description: '供应商、模型名称、推理参数', fieldCount: 0 },
  { key: 'notification', title: '通知渠道', icon: <Bell size={16} weight="fill" />, description: '机器人、Webhook、消息推送', fieldCount: 0 },
  { key: 'sound', title: '声音', icon: <SpeakerX size={16} weight="fill" />, description: '静音、音量、音效试听', fieldCount: 0 },
  { key: 'display', title: '显示偏好', icon: <ChartBar size={16} weight="fill" />, description: '机构模式、信息降噪、关键价位', fieldCount: 0 },
  { key: 'risk_control', title: '风控', icon: <ShieldCheck size={16} weight="fill" />, description: '金额红线、价格偏差、紧急平仓', fieldCount: 0 },
]

// 简化模式只显示核心分类
const WIZARD_KEYS = new Set(['broker', 'notification', 'sound', 'display', 'risk_control'])

export default function Settings() {
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [initialValues, setInitialValues] = useState<Record<string, unknown>>({})
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [activeCategory, setActiveCategory] = useState('general')

  const { user } = useAuthStore()
  const isAdmin = user?.role?.toUpperCase() === 'ADMIN'

  // 计算 dirty count
  const dirtyCount = Object.keys(values).filter((k) => {
    const a = values[k]
    const b = initialValues[k]
    if (a === b) return false
    if (typeof a === 'boolean' || typeof a === 'number') return a !== b
    return String(a) !== String(b)
  }).length

  // 加载配置
  useEffect(() => {
    const loadSettings = async () => {
      setLoading(true)
      setLoadError(null)
      try {
        const res = await client.get('/api/settings')
        const data = res.data as Record<string, unknown>

        const frontendValues: Record<string, unknown> = {}
        if (data && typeof data === 'object') {
          Object.entries(data).forEach(([key, value]) => {
            if (key === 'jwt' || key === 'system') return
            const feKey = toFrontendKey(key)
            frontendValues[feKey] = value
          })
        }

        if (data?.system && typeof data.system === 'object') {
          Object.entries(data.system as Record<string, unknown>).forEach(([key, value]) => {
            const feKey = toFrontendKey(`system.${key}`)
            frontendValues[feKey] = value
          })
        }

        setValues(frontendValues)
        setInitialValues(JSON.parse(JSON.stringify(frontendValues)))
      } catch (e: any) {
        console.error('加载配置失败:', e)
        setLoadError('加载设置失败: ' + (e.message || '未知错误'))
      } finally {
        setLoading(false)
      }
    }
    loadSettings()
  }, [])

  // Toast auto-dismiss
  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), 3200)
    return () => window.clearTimeout(timer)
  }, [toast])

  // 计算每分类字段数
  const categoriesWithCount = CATEGORIES.map((cat) => {
    const count = Object.keys(values).filter((k) => {
      if (cat.key === 'broker') return k.startsWith('trading.broker') || k.startsWith('trading.xtp') || k.startsWith('trading.qmt') || k.startsWith('trading.ctp')
      if (cat.key === 'general') return k.startsWith('database.') || k.startsWith('trading.mode') || k.startsWith('system.log_level') || k.startsWith('system.web_port') || k.startsWith('system.initial_capital') || k.startsWith('data_provider') || k.startsWith('baostock')
      if (cat.key === 'trading') return k.startsWith('system.commission') || k.startsWith('system.min_commission') || k.startsWith('system.stamp_tax') || k.startsWith('system.slippage') || k.startsWith('system.lot_size') || k.startsWith('system.price_limit')
      if (cat.key === 'ai_model') return k.startsWith('ai.')
      if (cat.key === 'notification') return k.startsWith('notification.')
      if (cat.key === 'sound') return k === 'sound'
      if (cat.key === 'display') return k === 'display'
      if (cat.key === 'risk_control') return k === 'risk_control'
      return false
    }).length
    return { ...cat, fieldCount: count }
  })

  const handleValueChange = useCallback((key: string, value: unknown) => {
    setValues(prev => ({ ...prev, [key]: value }))
  }, [])

  const handleSave = useCallback(async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const backendValues: Record<string, unknown> = {}
      const systemValues: Record<string, unknown> = {}

      Object.entries(values ?? {}).forEach(([key, value]) => {
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

      await client.post('/api/settings/save', backendValues)
      setInitialValues(JSON.parse(JSON.stringify(values)))
      setToast({ type: 'success', message: '设置已保存，部分配置重启后生效' })
      message.success('设置已保存')
    } catch (e: any) {
      setSaveError('保存失败: ' + (e.message || '未知错误'))
      setToast({ type: 'error', message: '保存失败: ' + (e.message || '未知错误') })
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }, [values])

  const handleReset = useCallback(async () => {
    if (loading || saving) return
    try {
      const res = await client.get('/api/settings')
      const data = res.data as Record<string, unknown>

      const frontendValues: Record<string, unknown> = {}
      if (data && typeof data === 'object') {
        Object.entries(data).forEach(([key, value]) => {
          if (key === 'jwt' || key === 'system') return
          const feKey = toFrontendKey(key)
          frontendValues[feKey] = value
        })
      }

      if (data?.system && typeof data.system === 'object') {
        Object.entries(data.system as Record<string, unknown>).forEach(([key, value]) => {
          const feKey = toFrontendKey(`system.${key}`)
          frontendValues[feKey] = value
        })
      }

      setValues(frontendValues)
      setInitialValues(JSON.parse(JSON.stringify(frontendValues)))
      setLoadError(null)
      setToast({ type: 'success', message: '设置已重置' })
    } catch (e: any) {
      setLoadError('重置失败: ' + (e.message || '未知错误'))
      setToast({ type: 'error', message: '重置失败' })
    }
  }, [loading, saving])

  // 当前可见分类
  const visibleCategories = categoriesWithCount.filter((cat) => {
    return WIZARD_KEYS.has(cat.key)
  })

  // 渲染当前激活分类的内容
  const renderCategoryContent = () => {
    const commonProps = { values, onChange: handleValueChange }

    switch (activeCategory) {
      case 'broker': return <BrokerSettings {...commonProps} />
      case 'general': return <GeneralSettings {...commonProps} />
      case 'trading': return <TradingSettings {...commonProps} />
      case 'ai_model': return <AISettings {...commonProps} />
      case 'notification': return <NotifierSettings {...commonProps} />
      case 'sound': return <SoundSettings />
      case 'display': return <DisplaySettings />
      case 'risk_control': return <RiskControlSettings />
      default: return null
    }
  }

  return (
    <div className="min-h-screen px-4 pb-6 pt-4 md:px-6">
      {/* Header */}
      <header className="mb-4 rounded-2xl border border-white/8 bg-card/80 p-4 backdrop-blur-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl font-semibold text-white">系统设置</h1>
            <p className="text-sm text-secondary">默认使用 .env 中的配置</p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="btn-secondary"
              onClick={handleReset}
              disabled={loading || saving}
            >
              重置
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={handleSave}
              disabled={!dirtyCount || saving || loading}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <SaveOutlined size={14} />
              {saving ? '保存中...' : `保存配置${dirtyCount ? ` (${dirtyCount})` : ''}`}
            </button>
          </div>
        </div>

        {saveError && (
          <SettingsAlert
            className="mt-3"
            title="保存失败"
            message={saveError}
          />
        )}
      </header>

      {loadError && (
        <SettingsAlert
          title="加载设置失败"
          message={loadError}
          className="mb-4"
        />
      )}

      {loading ? (
        <div className="space-y-4 animate-fade-in">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="rounded-xl border border-white/8 bg-elevated/60 p-4">
              <div className="h-3 w-32 rounded bg-white/10" />
              <div className="mt-3 h-10 rounded-lg bg-white/6" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px_1fr]">
          {/* Left sidebar */}
          <CategorySidebar
            categories={visibleCategories}
            activeKey={activeCategory}
            onSelect={setActiveCategory}
          />

          {/* Right form area */}
          <section className="space-y-3 rounded-2xl border border-white/8 bg-card/60 p-4 backdrop-blur-sm">
            {renderCategoryContent() || (
              <div className="rounded-xl border border-white/8 bg-elevated/40 p-5 text-sm text-secondary">
                当前分类下暂无配置项。
              </div>
            )}
          </section>
        </div>
      )}

      {/* Admin panel */}
      {isAdmin && (
        <div className="mt-4 rounded-2xl border border-white/8 bg-card/60 p-4 backdrop-blur-sm">
          <h3 className="text-base font-semibold text-white">高级设置</h3>
          <p className="mt-1 text-sm text-secondary">
            管理员可以执行以下操作：
          </p>
          {/* TODO: 添加管理员操作按钮 */}
        </div>
      )}

      {/* Toast notification */}
      {toast && (
        <div className="fixed bottom-5 right-5 z-50 w-[320px] max-w-[calc(100vw-24px)]">
          <SettingsAlert
            title={toast.type === 'success' ? '操作成功' : '操作失败'}
            message={toast.message}
            variant={toast.type === 'success' ? 'success' : 'error'}
          />
        </div>
      )}
    </div>
  )
}
