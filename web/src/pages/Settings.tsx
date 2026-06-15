import { useState, useCallback, useEffect, useRef } from 'react'
import {
  Card, Collapse, Button, InputNumber, Switch, Select, Slider, Input, Space, Typography,
  Modal, Tag, Badge, FloatButton,
} from 'antd'
import {
  Warning, Sparkle, Rocket, Bell,
  Laptop, Coin, Wallet, Target, Clock,
  WifiHigh, FunnelSimple, ArrowsClockwise,
  CheckCircle, XCircle,
  Brain, Notebook,
} from '@phosphor-icons/react'

const { Title, Text } = Typography

interface SettingEntry {
  key: string
  value: unknown
  defaultValue: unknown
  value_type: string
  label: string
  description: string
  secret: boolean
  min?: number
  max?: number
  step?: number
  scale?: number
  unit?: string
  slider?: boolean
  options?: { value: string; label: string }[]
}

interface GroupEntry {
  key: string
  label: string
  icon: string
  iconComponent: React.ReactNode
  items: SettingEntry[]
}

const GROUPS: GroupEntry[] = [
  {
    key: 'system_control', label: '系统总控', icon: 'Laptop',
    iconComponent: <Laptop size={16} weight="fill" style={{ color: '#0066FF' }} />,
    items: [
      { key: 'trading.mode', value: 'simulator', defaultValue: 'simulator', value_type: 'select', label: '交易模式', description: '平台运行模式', secret: false, options: [{ value: 'backtest', label: '回测模式' }, { value: 'simulator', label: '模拟盘' }, { value: 'live', label: '实盘' }] },
      { key: 'system.log_level', value: 'INFO', defaultValue: 'INFO', value_type: 'select', label: '日志级别', description: '日志详细程度', secret: false, options: [{ value: 'DEBUG', label: 'DEBUG' }, { value: 'INFO', label: 'INFO' }, { value: 'WARNING', label: 'WARNING' }, { value: 'ERROR', label: 'ERROR' }] },
      { key: 'system.web_port', value: 8000, defaultValue: 8000, value_type: 'number', label: 'Web 端口', description: 'API 服务端口', secret: false, min: 1, max: 65535, step: 1 },
      { key: 'system.initial_capital', value: 1000000, defaultValue: 1000000, value_type: 'number', label: '初始资金', description: '回测/模拟盘初始资金', secret: false, min: 10000, max: 1_000_000_000, step: 100000 },
    ],
  },
  {
    key: 'data_source', label: '数据源', icon: 'Coin',
    iconComponent: <Coin size={16} weight="fill" style={{ color: '#0066FF' }} />,
    items: [
      { key: 'data_provider.source', value: 'akshare', defaultValue: 'akshare', value_type: 'select', label: '默认数据源', description: '主用数据提供商', secret: false, options: [{ value: 'baostock', label: 'BaoStock' }, { value: 'akshare', label: 'AkShare' }, { value: 'csv', label: 'CSV' }, { value: 'parquet', label: 'Parquet' }] },
      { key: 'data_provider.api_key', value: '', defaultValue: '', value_type: 'password', label: 'API Key', description: '数据源认证密钥', secret: true },
      { key: 'data_provider.api_url', value: '', defaultValue: '', value_type: 'string', label: 'API URL', description: '数据源接口地址', secret: false },
      { key: 'baostock.enabled', value: true, defaultValue: true, value_type: 'boolean', label: '启用 BaoStock', description: '使用 BaoStock 作为备用数据源', secret: false },
      { key: 'data_provider.duckdb_path', value: '', defaultValue: '', value_type: 'string', label: 'DuckDB 路径', description: '本地分析数据库路径', secret: false },
    ],
  },
  {
    key: 'trading_cost', label: '交易成本', icon: 'Wallet',
    iconComponent: <Wallet size={16} weight="fill" style={{ color: '#0066FF' }} />,
    items: [
      { key: 'system.commission_rate', value: 0.00025, defaultValue: 0.00025, value_type: 'float', label: '佣金费率', description: '买卖双向佣金', secret: false, min: 0, max: 0.003, step: 0.00001, scale: 100000, unit: '%', slider: true },
      { key: 'system.min_commission', value: 5, defaultValue: 5, value_type: 'number', label: '最低佣金', description: '单笔最低收费（元）', secret: false, min: 0, max: 50, step: 0.5 },
      { key: 'system.stamp_tax_rate', value: 0.0005, defaultValue: 0.0005, value_type: 'float', label: '印花税率', description: '卖出时征收', secret: false, min: 0, max: 0.01, step: 0.0001, scale: 10000, unit: '%', slider: true },
    ],
  },
  {
    key: 'execution_params', label: '执行参数', icon: 'Target',
    iconComponent: <Target size={16} weight="fill" style={{ color: '#0066FF' }} />,
    items: [
      { key: 'system.slippage', value: 0, defaultValue: 0, value_type: 'float', label: '滑点', description: '固定滑点（元）', secret: false, min: 0, max: 1, step: 0.01, scale: 100, unit: '元', slider: true },
      { key: 'system.lot_size', value: 100, defaultValue: 100, value_type: 'number', label: '最小交易单位', description: 'A 股 100 股整数倍', secret: false, min: 100, max: 1000, step: 100 },
      { key: 'system.price_limit_ratio', value: 0.1, defaultValue: 0.1, value_type: 'float', label: '涨跌停比例', description: '主板 ±10% 创业板 ±20%', secret: false, min: 0.05, max: 0.3, step: 0.01, scale: 100, unit: '%', slider: true },
    ],
  },
  {
    key: 'trading_session', label: '交易时段', icon: 'Clock',
    iconComponent: <Clock size={16} weight="fill" style={{ color: '#0066FF' }} />,
    items: [
      { key: 'system.morning_open', value: '09:30', defaultValue: '09:30', value_type: 'string', label: '早盘开盘', description: 'A 股早盘开始时间', secret: false },
      { key: 'system.morning_close', value: '11:30', defaultValue: '11:30', value_type: 'string', label: '早盘收盘', description: 'A 股早盘结束时间', secret: false },
      { key: 'system.afternoon_open', value: '13:00', defaultValue: '13:00', value_type: 'string', label: '午后开盘', description: 'A 股午后开始时间', secret: false },
      { key: 'system.afternoon_close', value: '15:00', defaultValue: '15:00', value_type: 'string', label: '午后收盘', description: 'A 股午后结束时间', secret: false },
    ],
  },
  {
    key: 'broker_channel', label: '券商通道', icon: 'Connection',
    iconComponent: <WifiHigh size={16} weight="fill" style={{ color: '#0066FF' }} />,
    items: [
      { key: 'trading.broker', value: 'simulator', defaultValue: 'simulator', value_type: 'select', label: 'Broker 类型', description: '交易通道类型', secret: false, options: [{ value: 'simulator', label: '模拟器' }, { value: 'qmt', label: 'QMT' }, { value: 'xtp', label: 'XTP' }] },
      { key: 'trading.poll_interval_sec', value: 1, defaultValue: 1, value_type: 'number', label: '轮询间隔', description: '行情刷新间隔（秒）', secret: false, min: 0.1, max: 60, step: 0.1 },
      { key: 'trading.auto_reconcile_minutes', value: 30, defaultValue: 30, value_type: 'number', label: '自动对账', description: '对账间隔（分钟）', secret: false, min: 5, max: 1440, step: 5 },
    ],
  },
  {
    key: 'risk_control', label: '风控阈值', icon: 'Warning',
    iconComponent: <Warning size={16} weight="fill" style={{ color: '#f59e0b' }} />,
    items: [
      { key: 'risk_control.max_stop_loss_pct', value: 0.08, defaultValue: 0.08, value_type: 'float', label: '单笔止损', description: '单笔最大亏损比例', secret: false, min: 0.01, max: 0.3, step: 0.01, scale: 100, unit: '%', slider: true },
      { key: 'risk_control.max_pos_per_stock', value: 0.3, defaultValue: 0.3, value_type: 'float', label: '单票仓位', description: '单只股票最大仓位占比', secret: false, min: 0.05, max: 1, step: 0.05, scale: 100, unit: '%', slider: true },
      { key: 'risk_control.max_total_pos', value: 0.9, defaultValue: 0.9, value_type: 'float', label: '总仓位上限', description: '最大总仓位占比', secret: false, min: 0.1, max: 1, step: 0.05, scale: 100, unit: '%', slider: true },
      { key: 'risk_control.max_daily_loss_pct', value: 0.02, defaultValue: 0.02, value_type: 'float', label: '日亏损熔断', description: '单日最大亏损触发熔断', secret: false, min: 0.005, max: 0.1, step: 0.005, scale: 100, unit: '%', slider: true },
      { key: 'risk_control.max_drawdown_pct', value: 0.15, defaultValue: 0.15, value_type: 'float', label: '回撤熔断', description: '累计最大回撤触发暂停', secret: false, min: 0.05, max: 0.5, step: 0.01, scale: 100, unit: '%', slider: true },
    ],
  },
  {
    key: 'ai_model', label: 'AI 模型', icon: 'MagicStick',
    iconComponent: <Brain size={16} weight="fill" style={{ color: '#0066FF' }} />,
    items: [
      { key: 'ai_model.provider', value: 'openai', defaultValue: 'openai', value_type: 'select', label: 'LLM Provider', description: 'AI 模型提供商', secret: false, options: [{ value: 'openai', label: 'OpenAI' }, { value: 'anthropic', label: 'Anthropic' }, { value: 'deepseek', label: 'DeepSeek' }] },
      { key: 'ai_model.api_url', value: '', defaultValue: '', value_type: 'string', label: 'API URL', description: '模型接口地址', secret: false },
      { key: 'ai_model.api_key', value: '', defaultValue: '', value_type: 'password', label: 'API Key', description: '模型认证密钥', secret: true },
      { key: 'ai_model.model', value: 'gpt-4o', defaultValue: 'gpt-4o', value_type: 'select', label: '模型', description: '使用的具体模型', secret: false, options: [{ value: 'gpt-4o', label: 'GPT-4o' }, { value: 'gpt-4', label: 'GPT-4' }, { value: 'claude-3-opus', label: 'Claude 3 Opus' }] },
      { key: 'ai_model.temperature', value: 0.3, defaultValue: 0.3, value_type: 'float', label: 'Temperature', description: '生成随机性控制', secret: false, min: 0, max: 2, step: 0.1, scale: 10, slider: true },
      { key: 'ai_model.timeout_sec', value: 30, defaultValue: 30, value_type: 'number', label: '超时秒数', description: 'LLM 调用超时（秒）', secret: false, min: 5, max: 120, step: 5 },
    ],
  },
  {
    key: 'evolution', label: '策略进化', icon: 'Rocket',
    iconComponent: <Rocket size={16} weight="fill" style={{ color: '#0066FF' }} />,
    items: [
      { key: 'evolution.enabled', value: false, defaultValue: false, value_type: 'boolean', label: '启用进化', description: '开启 AI 策略自动进化', secret: false },
      { key: 'evolution.llm_provider', value: 'openai', defaultValue: 'openai', value_type: 'select', label: '进化 LLM', description: '策略进化专用模型', secret: false, options: [{ value: 'openai', label: 'OpenAI' }, { value: 'anthropic', label: 'Anthropic' }] },
      { key: 'evolution.llm_model', value: 'gpt-4o', defaultValue: 'gpt-4o', value_type: 'select', label: '进化模型', description: '', secret: false, options: [{ value: 'gpt-4o', label: 'GPT-4o' }, { value: 'claude-3-opus', label: 'Claude 3 Opus' }] },
      { key: 'evolution.llm_temperature', value: 0.5, defaultValue: 0.5, value_type: 'float', label: '进化温度', description: '', secret: false, min: 0, max: 2, step: 0.1, scale: 10, slider: true },
      { key: 'evolution.llm_retry', value: 3, defaultValue: 3, value_type: 'number', label: '重试次数', description: '进化失败重试次数', secret: false, min: 0, max: 10, step: 1 },
    ],
  },
  {
    key: 'notification', label: '通知推送', icon: 'Bell',
    iconComponent: <Bell size={16} weight="fill" style={{ color: '#0066FF' }} />,
    items: [
      { key: 'notification.dingtalk_webhook', value: '', defaultValue: '', value_type: 'password', label: 'DingTalk Webhook', description: '', secret: true },
      { key: 'notification.wechat_webhook', value: '', defaultValue: '', value_type: 'password', label: '企业微信 Webhook', description: '', secret: true },
      { key: 'notification.telegram_bot_token', value: '', defaultValue: '', value_type: 'password', label: 'Telegram Bot Token', description: '', secret: true },
      { key: 'notification.email_enabled', value: false, defaultValue: false, value_type: 'boolean', label: '邮件通知', description: '启用邮件推送', secret: false },
    ],
  },
  {
    key: 'fundamental_adapter', label: '基本面适配', icon: 'Document',
    iconComponent: <Notebook size={16} weight="fill" style={{ color: '#0066FF' }} />,
    items: [
      { key: 'fundamental_adapter.enabled', value: false, defaultValue: false, value_type: 'boolean', label: '启用基本面', description: '', secret: false },
      { key: 'fundamental_adapter.apply_in_backtest', value: true, defaultValue: true, value_type: 'boolean', label: '回测中应用', description: '', secret: false },
      { key: 'fundamental_adapter.cache_ttl', value: 3600, defaultValue: 3600, value_type: 'number', label: '缓存时间（秒）', description: '', secret: false, min: 60, max: 86400, step: 60 },
    ],
  },
  {
    key: 'signal', label: '信号管理', icon: 'FunnelSimple',
    iconComponent: <FunnelSimple size={16} weight="fill" style={{ color: '#0066FF' }} />,
    items: [
      { key: 'signal.dedup_cooldown_sec', value: 300, defaultValue: 300, value_type: 'number', label: '去重冷却', description: '重复信号冷却时间（秒）', secret: false, min: 0, max: 3600, step: 30 },
      { key: 'signal.dedup_audit_rejected', value: true, defaultValue: true, value_type: 'boolean', label: '审计拒绝信号', description: '', secret: false },
    ],
  },
  {
    key: 'history_sync', label: '历史同步', icon: 'ArrowsClockwise',
    iconComponent: <ArrowsClockwise size={16} weight="fill" style={{ color: '#0066FF' }} />,
    items: [
      { key: 'history_sync.write_mode', value: 'append', defaultValue: 'append', value_type: 'select', label: '写入模式', description: '', secret: false, options: [{ value: 'append', label: '追加' }, { value: 'overwrite', label: '覆盖' }] },
      { key: 'history_sync.interval_minutes', value: 60, defaultValue: 60, value_type: 'number', label: '同步间隔（分钟）', description: '', secret: false, min: 5, max: 1440, step: 5 },
      { key: 'history_sync.lookback_days', value: 30, defaultValue: 30, value_type: 'number', label: '回看天数', description: '', secret: false, min: 1, max: 365, step: 1 },
    ],
  },
  {
    key: 'kafka_messaging', label: '消息总线', icon: 'Connection',
    iconComponent: <WifiHigh size={16} weight="fill" style={{ color: '#0066FF' }} />,
    items: [
      { key: 'kafka.enabled', value: false, defaultValue: false, value_type: 'boolean', label: '启用 Kafka', description: '', secret: false },
      { key: 'kafka.bootstrap_servers', value: 'localhost:9092', defaultValue: 'localhost:9092', value_type: 'string', label: 'Bootstrap 服务器', description: '', secret: false },
      { key: 'kafka.consumer_group', value: 'stockquant', defaultValue: 'stockquant', value_type: 'string', label: '消费者组', description: '', secret: false },
    ],
  },
]

export default function Settings() {
  const [viewMode, setViewMode] = useState<'wizard' | 'expert'>('expert')
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [dirtyKeys, setDirtyKeys] = useState<Set<string>>(new Set())
  const [adminModal, setAdminModal] = useState(false)
  const [adminToken, setAdminToken] = useState('')
  const [saving, setSaving] = useState(false)
  const [allExpanded, setAllExpanded] = useState(true)
  const passwordRef = useRef<any>(null)

  useEffect(() => {
    const initial: Record<string, unknown> = {}
    GROUPS.forEach((g) => g.items.forEach((item) => { initial[item.key] = item.value }))
    setValues(initial)
  }, [])

  const handleValueChange = useCallback((key: string, newVal: unknown) => {
    setValues((prev) => ({ ...prev, [key]: newVal }))
    setDirtyKeys((prev) => {
      const next = new Set(prev)
      const group = GROUPS.flatMap((g) => g.items).find((i) => i.key === key)
      if (group && newVal !== group.defaultValue) next.add(key)
      else next.delete(key)
      return next
    })
  }, [])

  const handleSave = () => {
    setAdminModal(true)
  }

  const handleAdminConfirm = () => {
    setSaving(true)
    setTimeout(() => {
      setDirtyKeys(new Set())
      setSaving(false)
      setAdminModal(false)
      setAdminToken('')
    }, 800)
  }

  const handleDiscard = () => {
    const initial: Record<string, unknown> = {}
    GROUPS.forEach((g) => g.items.forEach((item) => { initial[item.key] = item.value }))
    setValues(initial)
    setDirtyKeys(new Set())
  }

  const renderControl = (item: SettingEntry) => {
    const val = values[item.key]

    switch (item.value_type) {
      case 'boolean':
        return <Switch checked={val as boolean} onChange={(v) => handleValueChange(item.key, v)} size="small" />
      case 'select':
        return (
          <Select
            value={val as string}
            onChange={(v) => handleValueChange(item.key, v)}
            size="small"
            style={{ minWidth: 160 }}
            options={item.options}
          />
        )
      case 'password':
        return (
          <Input.Password
            value={val as string}
            placeholder="sk-..."
            size="small"
            style={{ minWidth: 180 }}
            onChange={(e) => handleValueChange(item.key, e.target.value)}
          />
        )
      case 'time':
      case 'string':
        return (
          <Input
            value={String(val ?? '')}
            size="small"
            style={{ minWidth: 180 }}
            placeholder={item.description}
            onChange={(e) => {
              const v = e.target.value
              handleValueChange(item.key, v)
            }}
          />
        )
      case 'float':
      case 'number': {
        const numVal = typeof val === 'number' ? val : parseFloat(String(val ?? 0))
        if (item.slider) {
          return (
            <Space direction="vertical" style={{ width: 200 }} size={4}>
              <Slider
                min={item.min ?? 0}
                max={item.max ?? 100}
                step={item.step ?? 0.01}
                value={numVal * (item.scale ?? 1)}
                onChange={(v) => handleValueChange(item.key, v / (item.scale ?? 1))}
                tooltip={{ formatter: (v) => v ? `${(v * (item.scale ?? 1)).toFixed(2)}${item.unit ?? ''}` : '' }}
              />
              <InputNumber
                value={numVal}
                min={item.min}
                max={item.max}
                step={item.step}
                style={{ width: '100%' }}
                size="small"
                formatter={(v) => `${v}${item.unit ?? ''}`}
                parser={(v) => parseFloat(v ?? '0') / (item.scale ?? 1)}
                onChange={(v) => handleValueChange(item.key, v)}
              />
            </Space>
          )
        }
        return (
          <InputNumber
            value={numVal}
            min={item.min}
            max={item.max}
            step={item.step ?? 1}
            size="small"
            style={{ minWidth: 120 }}
            formatter={(v) => `${v}${item.unit ?? ''}`}
            parser={(v) => parseFloat(v ?? '0')}
            onChange={(v) => handleValueChange(item.key, v)}
          />
        )
      }
      default:
        return <Input value={String(val)} size="small" onChange={(e) => handleValueChange(item.key, e.target.value)} />
    }
  }

  const dirtyCount = dirtyKeys.size

  return (
    <div style={{ maxWidth: 1000 }}>
      {/* Banner */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(168,85,247,0.15) 0%, rgba(0,102,255,0.15) 100%)',
        border: '1px solid rgba(168,85,247,0.2)',
        borderRadius: 8,
        padding: '14px 20px',
        marginBottom: 20,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        backdropFilter: 'blur(8px)',
      }}>
        <div>
          <Title level={5} style={{ margin: 0, fontWeight: 600, fontSize: 14, color: '#f0f0f0' }}>
            <Sparkle size={16} weight="fill" style={{ color: '#a855f7', marginRight: 8 }} />
            运行配置中心
          </Title>
          <Text type="secondary" style={{ fontSize: 12 }}>所有修改保存后热生效，无需重启服务</Text>
        </div>
      </div>

      {/* Toolbar */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16,
      }}>
        <Space size={16}>
          <Space size={4}>
            <Tag
              color={viewMode === 'wizard' ? 'blue' : 'default'}
              style={{ cursor: 'pointer', fontWeight: viewMode === 'wizard' ? 600 : 400 }}
              onClick={() => setViewMode('wizard')}
            >
              向导模式
            </Tag>
            <Tag
              color={viewMode === 'expert' ? 'blue' : 'default'}
              style={{ cursor: 'pointer', fontWeight: viewMode === 'expert' ? 600 : 400 }}
              onClick={() => setViewMode('expert')}
            >
              专家模式
            </Tag>
          </Space>
          <Button size="small" type="link" onClick={() => setAllExpanded(!allExpanded)}>
            {allExpanded ? '全部折叠' : '全部展开'}
          </Button>
        </Space>
        <Space>
          {dirtyCount > 0 && (
            <Tag color="orange" style={{ margin: 0 }}>
              <Badge count={dirtyCount} overflowCount={99} /> 未保存
            </Tag>
          )}
        </Space>
      </div>

      {/* Wizard Mode */}
      {viewMode === 'wizard' && (
        <div>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Card size="small" styles={{ body: { padding: 20 } }}>
              <Text>向导模式已移除，请使用专家模式。</Text>
            </Card>
          </Space>
        </div>
      )}

      {/* Expert Mode */}
      {viewMode === 'expert' && (
        <Collapse
          bordered={false}
          expandIconPosition="right"
          defaultActiveKey={allExpanded ? GROUPS.map((g) => g.key) : []}
          style={{ background: 'transparent' }}
          items={GROUPS.map((g) => ({
            key: g.key,
            label: (
              <Space style={{ fontSize: 13, fontWeight: 600 }}>
                {g.iconComponent} {g.label}
                <Tag color="default" style={{ fontSize: 11, margin: 0 }}>{g.items.length}</Tag>
              </Space>
            ),
            children: (
              <Space direction="vertical" style={{ width: '100%' }} size={10}>
                {g.items.map((item) => {
                  const isDirty = dirtyKeys.has(item.key)
                  return (
                    <div
                      key={item.key}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '140px 1fr 36px',
                        gap: 12,
                        alignItems: 'center',
                        padding: '6px 12px',
                        borderRadius: 6,
                        background: isDirty ? 'rgba(245,158,11,0.04)' : 'transparent',
                        border: isDirty ? '1px solid rgba(245,158,11,0.15)' : '1px solid transparent',
                      }}
                    >
                      <div>
                        <Text style={{ fontSize: 12, fontWeight: 500 }}>{item.label}</Text>
                        {item.description && (
                          <div style={{ fontSize: 11, color: '#555', marginTop: 1 }}>{item.description}</div>
                        )}
                      </div>
                      {renderControl(item)}
                      {isDirty ? (
                        <CheckCircle size={14} weight="fill" style={{ color: '#f59e0b', cursor: 'pointer' }} />
                      ) : (
                        <XCircle size={14} weight="fill" style={{ color: '#333' }} />
                      )}
                    </div>
                  )
                })}
              </Space>
            ),
          }))}
        />
      )}

      {/* Floating save bar */}
      {dirtyCount > 0 && (
        <FloatButton
          type="primary"
          icon={<CheckCircle size={20} weight="fill" />}
          style={{ right: 24, bottom: 24 }}
          onClick={handleSave}
          tooltip={`${dirtyCount} 项配置未保存`}
        />
      )}

      {/* Admin modal */}
      <Modal
        title="确认保存"
        open={adminModal}
        onOk={handleAdminConfirm}
        onCancel={() => { setAdminModal(false); setAdminToken('') }}
        okButtonProps={{ loading: saving }}
      >
        <p style={{ marginBottom: 12 }}>请输入 <Text code>TRADING_ADMIN_TOKEN</Text> 以确认保存配置修改。</p>
        <Input.Password
          ref={passwordRef}
          value={adminToken}
          onChange={(e) => setAdminToken(e.target.value)}
          placeholder="管理员口令"
          onPressEnter={handleAdminConfirm}
        />
      </Modal>

      {/* Footer actions */}
      {dirtyCount > 0 && (
        <div style={{ marginTop: 20, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button size="small" onClick={handleDiscard}>放弃修改</Button>
          <Button type="primary" icon={<CheckCircle size={16} weight="fill" />} onClick={handleSave} loading={saving}>
            保存并生效
          </Button>
        </div>
      )}
    </div>
  )
}
