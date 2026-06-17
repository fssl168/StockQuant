import { useState, useCallback, useEffect, useRef } from 'react'
import {
  Collapse, Button, InputNumber, Switch, Select, Slider, Input, Space, Typography,
  Modal, Tag, Badge,
} from 'antd'
import {
  Warning, Sparkle, Rocket, Bell, Brain,
  Laptop, Coin, Wallet, Target, Clock,
  WifiHigh, FunnelSimple, ArrowsClockwise,
  CheckCircle, XCircle, ArrowCounterClockwise,
  Notebook,
} from '@phosphor-icons/react'
import LLMConfigForm from '@/components/Settings/LLMConfigForm'
import AgentToggles from '@/components/Settings/AgentToggles'
import NotifierForm from '@/components/Settings/NotifierForm'

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
  when?: { field: string; values: string[] }
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
    iconComponent: <Laptop size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />,
    items: [
      { key: 'trading.mode', value: 'simulator', defaultValue: 'simulator', value_type: 'select', label: '交易模式', description: '平台运行模式', secret: false, options: [{ value: 'backtest', label: '回测模式' }, { value: 'simulator', label: '模拟盘' }, { value: 'live', label: '实盘' }] },
      { key: 'system.log_level', value: 'INFO', defaultValue: 'INFO', value_type: 'select', label: '日志级别', description: '日志详细程度', secret: false, options: [{ value: 'DEBUG', label: 'DEBUG' }, { value: 'INFO', label: 'INFO' }, { value: 'WARNING', label: 'WARNING' }, { value: 'ERROR', label: 'ERROR' }] },
      { key: 'system.web_port', value: 8000, defaultValue: 8000, value_type: 'number', label: 'Web 端口', description: 'API 服务端口', secret: false, min: 1, max: 65535, step: 1 },
      { key: 'system.initial_capital', value: 1000000, defaultValue: 1000000, value_type: 'number', label: '初始资金', description: '回测/模拟盘初始资金', secret: false, min: 10000, max: 1_000_000_000, step: 100000 },
    ],
  },
  {
    key: 'data_source', label: '数据源', icon: 'Coin',
    iconComponent: <Coin size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />,
    items: [
      { key: 'data_provider.source', value: 'alphafeed', defaultValue: 'alphafeed', value_type: 'select', label: '默认数据源', description: '主用数据提供商', secret: false, options: [{ value: 'alphafeed', label: 'AlphaFeed (推荐)' }, { value: 'baostock', label: 'BaoStock' }, { value: 'akshare', label: 'AkShare (降级)' }, { value: 'csv', label: 'CSV' }, { value: 'parquet', label: 'Parquet' }] },
      { key: 'data_provider.alphafeed_key', value: '', defaultValue: '', value_type: 'password', label: 'AlphaFeed Key', description: 'AlphaFeed API 密钥', secret: true, when: { field: 'data_provider.source', values: ['alphafeed'] } },
      { key: 'data_provider.api_key', value: '', defaultValue: '', value_type: 'password', label: 'API Key', description: '数据源认证密钥', secret: true, when: { field: 'data_provider.source', values: ['akshare', 'parquet'] } },
      { key: 'data_provider.api_url', value: '', defaultValue: '', value_type: 'string', label: 'API URL', description: '数据源接口地址', secret: false, when: { field: 'data_provider.source', values: ['akshare', 'parquet'] } },
      { key: 'baostock.enabled', value: true, defaultValue: true, value_type: 'boolean', label: '启用 BaoStock', description: '使用 BaoStock 作为备用数据源', secret: false, when: { field: 'data_provider.source', values: ['baostock'] } },
      { key: 'data_provider.duckdb_path', value: '', defaultValue: '', value_type: 'string', label: 'DuckDB 路径', description: '本地分析数据库路径', secret: false },
    ],
  },
  {
    key: 'trading_cost', label: '交易成本', icon: 'Wallet',
    iconComponent: <Wallet size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />,
    items: [
      { key: 'system.commission_rate', value: 0.00025, defaultValue: 0.00025, value_type: 'float', label: '佣金费率', description: '买卖双向佣金', secret: false, min: 0, max: 0.003, step: 0.00001, scale: 100000, unit: '%', slider: true },
      { key: 'system.min_commission', value: 5, defaultValue: 5, value_type: 'number', label: '最低佣金', description: '单笔最低收费（元）', secret: false, min: 0, max: 50, step: 0.5 },
      { key: 'system.stamp_tax_rate', value: 0.0005, defaultValue: 0.0005, value_type: 'float', label: '印花税率', description: '卖出时征收', secret: false, min: 0, max: 0.01, step: 0.0001, scale: 10000, unit: '%', slider: true },
    ],
  },
  {
    key: 'execution_params', label: '执行参数', icon: 'Target',
    iconComponent: <Target size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />,
    items: [
      { key: 'system.slippage', value: 0, defaultValue: 0, value_type: 'float', label: '滑点', description: '固定滑点（元）', secret: false, min: 0, max: 1, step: 0.01, scale: 100, unit: '元', slider: true },
      { key: 'system.lot_size', value: 100, defaultValue: 100, value_type: 'number', label: '最小交易单位', description: 'A 股 100 股整数倍', secret: false, min: 100, max: 1000, step: 100 },
      { key: 'system.price_limit_ratio', value: 0.1, defaultValue: 0.1, value_type: 'float', label: '涨跌停比例', description: '主板 ±10% 创业板 ±20%', secret: false, min: 0.05, max: 0.3, step: 0.01, scale: 100, unit: '%', slider: true },
    ],
  },
  {
    key: 'trading_session', label: '交易时段', icon: 'Clock',
    iconComponent: <Clock size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />,
    items: [
      { key: 'system.morning_open', value: '09:30', defaultValue: '09:30', value_type: 'string', label: '早盘开盘', description: 'A 股早盘开始时间', secret: false },
      { key: 'system.morning_close', value: '11:30', defaultValue: '11:30', value_type: 'string', label: '早盘收盘', description: 'A 股早盘结束时间', secret: false },
      { key: 'system.afternoon_open', value: '13:00', defaultValue: '13:00', value_type: 'string', label: '午后开盘', description: 'A 股午后开始时间', secret: false },
      { key: 'system.afternoon_close', value: '15:00', defaultValue: '15:00', value_type: 'string', label: '午后收盘', description: 'A 股午后结束时间', secret: false },
    ],
  },
  {
    key: 'broker_channel', label: '券商通道', icon: 'Connection',
    iconComponent: <WifiHigh size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />,
    items: [
      { key: 'trading.broker', value: 'simulator', defaultValue: 'simulator', value_type: 'select', label: 'Broker 类型', description: '交易通道类型', secret: false, options: [{ value: 'simulator', label: '模拟器' }, { value: 'qmt', label: 'QMT' }, { value: 'xtp', label: 'XTP' }] },
      { key: 'trading.poll_interval_sec', value: 1, defaultValue: 1, value_type: 'number', label: '轮询间隔', description: '行情刷新间隔（秒）', secret: false, min: 0.1, max: 60, step: 0.1, when: { field: 'trading.broker', values: ['qmt'] } },
      { key: 'trading.auto_reconcile_minutes', value: 30, defaultValue: 30, value_type: 'number', label: '自动对账', description: '对账间隔（分钟）', secret: false, min: 5, max: 1440, step: 5, when: { field: 'trading.broker', values: ['qmt'] } },
    ],
  },
  {
    key: 'risk_control', label: '风控阈值', icon: 'Warning',
    iconComponent: <Warning size={16} weight="fill" style={{ color: 'var(--color-warning)' }} />,
    items: [
      { key: 'risk_control.max_stop_loss_pct', value: 0.08, defaultValue: 0.08, value_type: 'float', label: '单笔止损', description: '单笔最大亏损比例', secret: false, min: 0.01, max: 0.3, step: 0.01, scale: 100, unit: '%', slider: true, when: { field: 'trading.mode', values: ['simulator', 'live'] } },
      { key: 'risk_control.max_pos_per_stock', value: 0.3, defaultValue: 0.3, value_type: 'float', label: '单票仓位', description: '单只股票最大仓位占比', secret: false, min: 0.05, max: 1, step: 0.05, scale: 100, unit: '%', slider: true, when: { field: 'trading.mode', values: ['simulator', 'live'] } },
      { key: 'risk_control.max_total_pos', value: 0.9, defaultValue: 0.9, value_type: 'float', label: '总仓位上限', description: '最大总仓位占比', secret: false, min: 0.1, max: 1, step: 0.05, scale: 100, unit: '%', slider: true, when: { field: 'trading.mode', values: ['simulator', 'live'] } },
      { key: 'risk_control.max_daily_loss_pct', value: 0.02, defaultValue: 0.02, value_type: 'float', label: '日亏损熔断', description: '单日最大亏损触发熔断', secret: false, min: 0.005, max: 0.1, step: 0.005, scale: 100, unit: '%', slider: true, when: { field: 'trading.mode', values: ['simulator', 'live'] } },
      { key: 'risk_control.max_drawdown_pct', value: 0.15, defaultValue: 0.15, value_type: 'float', label: '回撤熔断', description: '累计最大回撤触发暂停', secret: false, min: 0.05, max: 0.5, step: 0.01, scale: 100, unit: '%', slider: true, when: { field: 'trading.mode', values: ['simulator', 'live'] } },
    ],
  },
  {
    key: 'ai_model', label: 'AI 模型', icon: 'MagicStick',
    iconComponent: <Brain size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />,
    items: [
      { key: 'decision.mode', value: 'semi_auto', defaultValue: 'semi_auto', value_type: 'select', label: '决策模式', description: 'AI 辅助决策模式', secret: false, options: [{ value: 'auto', label: '全自动' }, { value: 'semi_auto', label: '半自动' }, { value: 'read_only', label: '只读' }] },
      { key: 'ai.provider', value: 'openai', defaultValue: 'openai', value_type: 'select', label: 'AI 模型', description: '主模型', secret: false, options: [{ value: 'openai', label: 'OpenAI' }, { value: 'anthropic', label: 'Anthropic' }, { value: 'custom', label: '自定义' }] },
      { key: 'ai.model', value: 'gpt-4o', defaultValue: 'gpt-4o', value_type: 'string', label: '主模型', description: 'OpenAI / 兼容 API 模型名称', secret: false, when: { field: 'ai.provider', values: ['openai', 'custom'] } },
      { key: 'ai.api_key', value: '', defaultValue: '', value_type: 'password', label: 'API Key', description: 'OpenAI / 兼容 API 密钥', secret: true },
      { key: 'ai.api_base', value: '', defaultValue: '', value_type: 'string', label: 'API Base URL', description: '自定义 API 地址（留空用官方默认）', secret: false },
      { key: 'ai.temperature', value: 0.7, defaultValue: 0.7, value_type: 'float', label: 'Temperature', description: '生成温度 (0-2)', secret: false, min: 0, max: 2, step: 0.1, scale: 10, slider: true },
      { key: 'ai.max_tokens', value: 4096, defaultValue: 4096, value_type: 'number', label: 'Max Tokens', description: '单次最大生成 token 数', secret: false, min: 256, max: 128000, step: 256 },
      { key: 'ai.anthropic_model', value: 'claude-sonnet-4-20250514', defaultValue: 'claude-sonnet-4-20250514', value_type: 'string', label: 'Anthropic 模型', description: 'Claude 模型名称', secret: false, when: { field: 'ai.provider', values: ['anthropic'] } },
      { key: 'ai.anthropic_api_key', value: '', defaultValue: '', value_type: 'password', label: 'Anthropic API Key', description: 'Anthropic API 密钥', secret: true },
      { key: 'ai.anthropic_api_base', value: '', defaultValue: '', value_type: 'string', label: 'Anthropic API Base', description: '自定义 Anthropic API 地址', secret: false },
    ],
  },
  {
    key: 'ai_pipeline', label: 'AI 信息管线', icon: 'FlowArrow',
    iconComponent: <Brain size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />,
    items: [
      { key: 'ai_pipeline.collect_interval_sec', value: 300, defaultValue: 300, value_type: 'number', label: '采集频率', description: '信息采集间隔（秒）', secret: false, min: 60, max: 3600, step: 30 },
      { key: 'ai_pipeline.denoise_source_credit_threshold', value: 0.5, defaultValue: 0.5, value_type: 'float', label: '来源信用阈值', description: '低于此阈值的信源将被降权', secret: false, min: 0, max: 1, step: 0.05, scale: 100, unit: '', slider: true },
      { key: 'ai_pipeline.denoise_timeliness_hours', value: 24, defaultValue: 24, value_type: 'number', label: '时效降权', description: '超过此时长的信息将被降权（小时）', secret: false, min: 1, max: 168, step: 1 },
      { key: 'ai_pipeline.summarize_period', value: 'daily', defaultValue: 'daily', value_type: 'select', label: '总结周期', description: '信息总结频率', secret: false, options: [{ value: 'daily', label: '每日' }, { value: 'weekly', label: '每周' }, { value: 'monthly', label: '每月' }] },
      { key: 'ai_pipeline.elevate_min_articles', value: 3, defaultValue: 3, value_type: 'number', label: '升华触发数', description: '触发升华所需最少文章数', secret: false, min: 2, max: 20, step: 1 },
      { key: 'ai_pipeline.hallucination_mode', value: 'standard', defaultValue: 'standard', value_type: 'select', label: '反幻觉模式', description: '幻觉检测严格程度', secret: false, options: [{ value: 'strict', label: '严格' }, { value: 'standard', label: '标准' }, { value: 'relaxed', label: '宽松' }, { value: 'emergency', label: '紧急' }] },
      { key: 'ai_pipeline.memory_l2_retention_days', value: 30, defaultValue: 30, value_type: 'number', label: 'L2 保留天数', description: '短期记忆保留天数', secret: false, min: 1, max: 365, step: 1 },
      { key: 'ai_pipeline.memory_l3_confidence_threshold', value: 0.15, defaultValue: 0.15, value_type: 'float', label: 'L3 置信度阈值', description: '长期记忆最低置信度', secret: false, min: 0, max: 1, step: 0.05, scale: 100, unit: '', slider: true },
      { key: 'ai_pipeline.local_rule_engine_enabled', value: true, defaultValue: true, value_type: 'boolean', label: '本地规则引擎', description: 'Tick级决策使用本地规则引擎（无需LLM）', secret: false },
      { key: 'ai_pipeline.sentiment_method', value: 'auto', defaultValue: 'auto', value_type: 'select', label: '情感分析', description: '情感分析方法', secret: false, options: [{ value: 'auto', label: '自动降级' }, { value: 'keyword', label: '关键词规则' }, { value: 'huggingface', label: 'HuggingFace 模型' }] },
    ],
  },
  {
    key: 'evolution', label: '策略进化', icon: 'Rocket',
    iconComponent: null,
    items: [],
  },
  {
    key: 'notification', label: '通知推送', icon: 'Bell',
    iconComponent: null,
    items: [],
  },
  {
    key: 'fundamental_adapter', label: '基本面适配', icon: 'Document',
    iconComponent: <Notebook size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />,
    items: [
      { key: 'fundamental_adapter.enabled', value: false, defaultValue: false, value_type: 'boolean', label: '启用基本面', description: '', secret: false },
      { key: 'fundamental_adapter.apply_in_backtest', value: true, defaultValue: true, value_type: 'boolean', label: '回测中应用', description: '', secret: false },
      { key: 'fundamental_adapter.cache_ttl', value: 3600, defaultValue: 3600, value_type: 'number', label: '缓存时间（秒）', description: '', secret: false, min: 60, max: 86400, step: 60 },
    ],
  },
  {
    key: 'signal', label: '信号管理', icon: 'FunnelSimple',
    iconComponent: <FunnelSimple size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />,
    items: [
      { key: 'signal.dedup_cooldown_sec', value: 300, defaultValue: 300, value_type: 'number', label: '去重冷却', description: '重复信号冷却时间（秒）', secret: false, min: 0, max: 3600, step: 30 },
      { key: 'signal.dedup_audit_rejected', value: true, defaultValue: true, value_type: 'boolean', label: '审计拒绝信号', description: '', secret: false },
    ],
  },
  {
    key: 'history_sync', label: '历史同步', icon: 'ArrowsClockwise',
    iconComponent: <ArrowsClockwise size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />,
    items: [
      { key: 'history_sync.write_mode', value: 'append', defaultValue: 'append', value_type: 'select', label: '写入模式', description: '', secret: false, options: [{ value: 'append', label: '追加' }, { value: 'overwrite', label: '覆盖' }] },
      { key: 'history_sync.interval_minutes', value: 60, defaultValue: 60, value_type: 'number', label: '同步间隔（分钟）', description: '', secret: false, min: 5, max: 1440, step: 5 },
      { key: 'history_sync.lookback_days', value: 30, defaultValue: 30, value_type: 'number', label: '回看天数', description: '', secret: false, min: 1, max: 365, step: 1 },
    ],
  },
  {
    key: 'kafka_messaging', label: '消息总线', icon: 'Connection',
    iconComponent: <WifiHigh size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />,
    items: [
      { key: 'kafka.enabled', value: false, defaultValue: false, value_type: 'boolean', label: '启用 Kafka', description: '', secret: false },
      { key: 'kafka.bootstrap_servers', value: 'localhost:9092', defaultValue: 'localhost:9092', value_type: 'string', label: 'Bootstrap 服务器', description: '', secret: false },
      { key: 'kafka.consumer_group', value: 'stockquant', defaultValue: 'stockquant', value_type: 'string', label: '消费者组', description: '', secret: false },
    ],
  },
]

const isVisible = (item: SettingEntry, allValues: Record<string, unknown>): boolean => {
  if (!item.when) return true
  const fieldValue = allValues[item.when.field]
  return item.when.values.includes(String(fieldValue))
}

export default function Settings() {
  const [viewMode, setViewMode] = useState<'wizard' | 'expert'>('expert')
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [dirtyKeys, setDirtyKeys] = useState<Set<string>>(new Set())
  const [adminModal, setAdminModal] = useState(false)
  const [adminToken, setAdminToken] = useState('')
  const [saving, setSaving] = useState(false)
  const [allExpanded, setAllExpanded] = useState(true)
  const [activeKeys, setActiveKeys] = useState<string[]>([])
  const passwordRef = useRef<any>(null)

  useEffect(() => {
    const initial: Record<string, unknown> = {}
    GROUPS.forEach((g) => g.items.forEach((item) => { initial[item.key] = item.value }))
    // Also include default values for extracted component keys
    initial['decision.mode'] = 'semi_auto'
    initial['ai.provider'] = 'openai'
    initial['ai.model'] = 'gpt-4o'
    initial['ai.api_key'] = ''
    initial['ai.api_base'] = ''
    initial['ai.temperature'] = 0.7
    initial['ai.max_tokens'] = 4096
    initial['ai.anthropic_model'] = 'claude-sonnet-4-20250514'
    initial['ai.anthropic_api_key'] = ''
    initial['ai.anthropic_api_base'] = ''
    initial['evolution.enabled'] = false
    initial['evolution.llm_provider'] = 'openai'
    initial['evolution.llm_model'] = 'gpt-4o'
    initial['evolution.anthropic_model'] = 'claude-3-opus'
    initial['evolution.llm_temperature'] = 0.5
    initial['evolution.max_tokens'] = 4096
    initial['evolution.api_key'] = ''
    initial['evolution.api_base'] = ''
    initial['evolution.llm_retry'] = 3
    initial['notification.dingtalk_webhook'] = ''
    initial['notification.wechat_webhook'] = ''
    initial['notification.telegram_bot_token'] = ''
    initial['notification.email_enabled'] = false

    // 从后端加载配置覆盖本地默认值
    fetch('/api/settings')
      .then(res => res.json())
      .then(data => {
        if (data?.settings) {
          setValues({ ...initial, ...data.settings })
        } else {
          setValues(initial)
        }
      })
      .catch(() => {
        setValues(initial)
      })
  }, [])

  const handleValueChange = useCallback((key: string, newVal: unknown) => {
    setValues((prev) => ({ ...prev, [key]: newVal }))
    setDirtyKeys((prev) => {
      const next = new Set(prev)
      // Check against defaults from all sources
      const allDefaults: Record<string, unknown> = {}
      GROUPS.forEach((g) => g.items.forEach((item) => { allDefaults[item.key] = item.defaultValue }))
      allDefaults['ai.provider'] = 'openai'
      allDefaults['ai.model'] = 'gpt-4o'
      allDefaults['ai.api_key'] = ''
      allDefaults['ai.api_base'] = ''
      allDefaults['ai.temperature'] = 0.7
      allDefaults['ai.max_tokens'] = 4096
      allDefaults['ai.anthropic_model'] = 'claude-sonnet-4-20250514'
      allDefaults['ai.anthropic_api_key'] = ''
      allDefaults['ai.anthropic_api_base'] = ''
      allDefaults['evolution.enabled'] = false
      allDefaults['evolution.llm_provider'] = 'openai'
      allDefaults['evolution.llm_model'] = 'gpt-4o'
      allDefaults['evolution.anthropic_model'] = 'claude-3-opus'
      allDefaults['evolution.llm_temperature'] = 0.5
      allDefaults['evolution.max_tokens'] = 4096
      allDefaults['evolution.api_key'] = ''
      allDefaults['evolution.api_base'] = ''
      allDefaults['evolution.llm_retry'] = 3
      allDefaults['notification.dingtalk_webhook'] = ''
      allDefaults['notification.wechat_webhook'] = ''
      allDefaults['notification.telegram_bot_token'] = ''
      allDefaults['notification.email_enabled'] = false
      if (newVal !== allDefaults[key]) next.add(key)
      else next.delete(key)
      return next
    })
  }, [values])

  const SENSITIVE_PATTERNS = ['key', 'secret', 'password', 'token', 'webhook']

  const hasSensitiveChanges = () => {
    for (const k of dirtyKeys) {
      const lower = k.toLowerCase()
      if (SENSITIVE_PATTERNS.some((p) => lower.includes(p))) return true
    }
    return false
  }

  const handleSave = () => {
    if (hasSensitiveChanges()) {
      setAdminModal(true)
    } else {
      handleAdminConfirm()
    }
  }

  const handleAdminConfirm = async () => {
    setSaving(true)
    try {
      // 收集修改的配置项
      const updates: Record<string, unknown> = {}
      dirtyKeys.forEach(k => { updates[k] = values[k] })

      if (Object.keys(updates).length > 0) {
        const token = localStorage.getItem('auth_token')
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        }
        if (adminToken) {
          headers['X-Admin-Token'] = adminToken
        }
        const res = await fetch('/api/settings/save', {
          method: 'POST',
          headers,
          body: JSON.stringify({ settings: updates }),
        })
        if (!res.ok) {
          console.error('保存配置失败:', res.statusText)
        }
      }

      setDirtyKeys(new Set())
      setAdminModal(false)
      setAdminToken('')
    } catch (e) {
      console.error('保存配置异常:', e)
    } finally {
      setSaving(false)
    }
  }

  const handleDiscard = () => {
    const initial: Record<string, unknown> = {}
    GROUPS.forEach((g) => g.items.forEach((item) => { initial[item.key] = item.value }))
    initial['decision.mode'] = 'semi_auto'
    initial['ai.provider'] = 'openai'
    initial['ai.model'] = 'gpt-4o'
    initial['ai.api_key'] = ''
    initial['ai.api_base'] = ''
    initial['ai.temperature'] = 0.7
    initial['ai.max_tokens'] = 4096
    initial['ai.anthropic_model'] = 'claude-sonnet-4-20250514'
    initial['ai.anthropic_api_key'] = ''
    initial['ai.anthropic_api_base'] = ''
    initial['evolution.enabled'] = false
    initial['evolution.llm_provider'] = 'openai'
    initial['evolution.llm_model'] = 'gpt-4o'
    initial['evolution.anthropic_model'] = 'claude-3-opus'
    initial['evolution.llm_temperature'] = 0.5
    initial['evolution.max_tokens'] = 4096
    initial['evolution.api_key'] = ''
    initial['evolution.api_base'] = ''
    initial['evolution.llm_retry'] = 3
    initial['notification.dingtalk_webhook'] = ''
    initial['notification.wechat_webhook'] = ''
    initial['notification.telegram_bot_token'] = ''
    initial['notification.email_enabled'] = false
    setValues(initial)
    setDirtyKeys(new Set())
  }

  const getVal = (key: string, fallback?: unknown) => {
    const v = values[key]
    if (v === null || v === undefined) return fallback
    if (typeof v === 'object') return fallback ?? ''
    return v
  }

  const renderControl = (item: SettingEntry) => {
    const val = getVal(item.key, item.value)

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
    <div style={{ maxWidth: 1000, paddingBottom: dirtyCount > 0 ? 64 : 0 }}>
      {/* Banner */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(59,130,246,0.12) 0%, rgba(59,130,246,0.04) 100%)',
        border: '1px solid rgba(59,130,246,0.2)',
        borderRadius: 8,
        padding: '14px 20px',
        marginBottom: 20,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        backdropFilter: 'blur(8px)',
      }}>
        <div>
          <Title level={5} style={{ margin: 0, fontWeight: 600, fontSize: 14, color: 'var(--color-text-primary)' }}>
            <Sparkle size={16} weight="fill" style={{ color: 'var(--color-brand-primary)', marginRight: 8 }} />
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
          <Space size={8} align="center">
            <Text style={{ fontSize: 13, fontWeight: viewMode === 'wizard' ? 600 : 400 }}>向导模式</Text>
            <Switch
              size="small"
              checked={viewMode === 'expert'}
              onChange={(checked) => {
                setViewMode(checked ? 'expert' : 'wizard')
                setActiveKeys([])
              }}
            />
            <Text style={{ fontSize: 13, fontWeight: viewMode === 'expert' ? 600 : 400 }}>专家模式</Text>
          </Space>
          {viewMode === 'expert' && (
            <Button size="small" type="link" onClick={() => {
              setAllExpanded(!allExpanded)
              setActiveKeys(allExpanded ? [] : GROUPS.map((g) => g.key))
            }}>
              {allExpanded ? '全部折叠' : '全部展开'}
            </Button>
          )}
        </Space>
        <Space>
          {dirtyCount > 0 && (
            <Tag color="orange" style={{ margin: 0 }}>
              <Badge count={dirtyCount} overflowCount={99} /> 未保存
            </Tag>
          )}
        </Space>
      </div>

      {/* Wizard Mode - simplified: only AI模型, 交易, 通知 */}
      {viewMode === 'wizard' && (
        <Collapse
          bordered={false}
          expandIconPosition="right"
          activeKey={activeKeys.length > 0 ? activeKeys : ['ai_model', 'broker_channel', 'notification']}
          onChange={(keys) => setActiveKeys(keys as string[])}
          style={{ background: 'transparent' }}
          items={GROUPS.filter((g) => ['ai_model', 'broker_channel', 'notification'].includes(g.key)).map((g) => {
            if (g.key === 'ai_model') {
              return {
                key: g.key,
                label: (
                  <Space style={{ fontSize: 13, fontWeight: 600 }}>
                    <Brain size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> {g.label}
                    <Tag color="default" style={{ fontSize: 11, margin: 0 }}>6</Tag>
                  </Space>
                ),
                children: <LLMConfigForm values={values} onChange={handleValueChange} />,
              }
            }
            if (g.key === 'notification') {
              return {
                key: g.key,
                label: (
                  <Space style={{ fontSize: 13, fontWeight: 600 }}>
                    <Bell size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> {g.label}
                    <Tag color="default" style={{ fontSize: 11, margin: 0 }}>4</Tag>
                  </Space>
                ),
                children: <NotifierForm values={values} onChange={handleValueChange} />,
              }
            }
            const visibleItems = g.items.filter((item) => isVisible(item, values))
            if (visibleItems.length === 0) return null
            return {
              key: g.key,
              label: (
                <Space style={{ fontSize: 13, fontWeight: 600 }}>
                  {g.iconComponent} {g.label}
                  <Tag color="default" style={{ fontSize: 11, margin: 0 }}>{visibleItems.length}</Tag>
                </Space>
              ),
              children: (
                <Space direction="vertical" style={{ width: '100%' }} size={10}>
                  {visibleItems.map((item) => {
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
                            <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 1 }}>{item.description}</div>
                          )}
                        </div>
                        {renderControl(item)}
                        {isDirty ? (
                          <CheckCircle size={14} weight="fill" style={{ color: 'var(--color-warning)', cursor: 'pointer' }} />
                        ) : (
                          <XCircle size={14} weight="fill" style={{ color: 'var(--color-bg-elevated)' }} />
                        )}
                      </div>
                    )
                  })}
                </Space>
              ),
            }
          }).filter((item): item is NonNullable<typeof item> => item !== null)}
        />
      )}

      {/* Expert Mode */}
      {viewMode === 'expert' && (
        <Collapse
          bordered={false}
          expandIconPosition="right"
          activeKey={activeKeys.length > 0 ? activeKeys : (allExpanded ? GROUPS.map((g) => g.key) : [])}
          onChange={(keys) => setActiveKeys(keys as string[])}
          style={{ background: 'transparent' }}
          items={GROUPS.map((g) => {
            // Handle extracted component groups
            if (g.key === 'ai_model') {
              return {
                key: g.key,
                label: (
                  <Space style={{ fontSize: 13, fontWeight: 600 }}>
                    <Brain size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> {g.label}
                    <Tag color="default" style={{ fontSize: 11, margin: 0 }}>9</Tag>
                  </Space>
                ),
                children: <LLMConfigForm values={values} onChange={handleValueChange} />,
              }
            }
            if (g.key === 'evolution') {
              return {
                key: g.key,
                label: (
                  <Space style={{ fontSize: 13, fontWeight: 600 }}>
                    <Rocket size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> {g.label}
                    <Tag color="default" style={{ fontSize: 11, margin: 0 }}>9</Tag>
                  </Space>
                ),
                children: <AgentToggles values={values} onChange={handleValueChange} />,
              }
            }
            if (g.key === 'notification') {
              return {
                key: g.key,
                label: (
                  <Space style={{ fontSize: 13, fontWeight: 600 }}>
                    <Bell size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> {g.label}
                    <Tag color="default" style={{ fontSize: 11, margin: 0 }}>4</Tag>
                  </Space>
                ),
                children: <NotifierForm values={values} onChange={handleValueChange} />,
              }
            }

            const visibleItems = g.items.filter((item) => isVisible(item, values))
            if (visibleItems.length === 0) return null
            return {
              key: g.key,
              label: (
                <Space style={{ fontSize: 13, fontWeight: 600 }}>
                  {g.iconComponent} {g.label}
                  <Tag color="default" style={{ fontSize: 11, margin: 0 }}>{visibleItems.length}</Tag>
                </Space>
              ),
              children: (
                <Space direction="vertical" style={{ width: '100%' }} size={10}>
                  {visibleItems.map((item) => {
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
                          <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 1 }}>{item.description}</div>
                        )}
                      </div>
                      {renderControl(item)}
                      {isDirty ? (
                        <CheckCircle size={14} weight="fill" style={{ color: 'var(--color-warning)', cursor: 'pointer' }} />
                      ) : (
                        <XCircle size={14} weight="fill" style={{ color: 'var(--color-bg-elevated)' }} />
                      )}
                    </div>
                  )
                })}
              </Space>
            ),
          }
          }).filter((item): item is NonNullable<typeof item> => item !== null)}
        />
      )}

      {/* Floating save bar */}
      {dirtyCount > 0 && (
        <div style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 100,
          background: 'var(--color-bg-elevated, #fff)',
          borderTop: '1px solid var(--color-border, #f0f0f0)',
          boxShadow: '0 -4px 12px rgba(0, 0, 0, 0.12)',
          padding: '12px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <Text style={{ fontSize: 13 }}>
            <Warning size={14} weight="fill" style={{ color: 'var(--color-warning)', marginRight: 6, verticalAlign: 'middle' }} />
            有未保存的更改
            <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>({dirtyCount} 项)</Text>
          </Text>
          <Space>
            <Button onClick={handleDiscard} icon={<ArrowCounterClockwise size={14} />}>放弃</Button>
            <Button type="primary" icon={<CheckCircle size={16} weight="fill" />} onClick={handleSave} loading={saving}>
              保存
            </Button>
          </Space>
        </div>
      )}

      {/* Admin token confirmation modal - only for sensitive settings */}
      <Modal
        title="确认修改敏感设置"
        open={adminModal}
        onOk={handleAdminConfirm}
        onCancel={() => { setAdminModal(false); setAdminToken('') }}
        okButtonProps={{ loading: saving }}
        okText="确认保存"
        cancelText="取消"
      >
        <p style={{ marginBottom: 12 }}>检测到修改涉及敏感配置（API 密钥、密码、令牌等），请输入 <Text code>TRADING_ADMIN_TOKEN</Text> 以确认操作。</p>
        <Input.Password
          ref={passwordRef}
          value={adminToken}
          onChange={(e) => setAdminToken(e.target.value)}
          placeholder="管理员口令"
          onPressEnter={handleAdminConfirm}
        />
      </Modal>
    </div>
  )
}
