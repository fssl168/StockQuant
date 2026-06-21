import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, Button, Card, Typography, Select, Progress, InputNumber, Row, Col, Collapse, Tag } from 'antd'
import dayjs from 'dayjs'
import { Play, Code, Clock, ArrowRight } from '@phosphor-icons/react'
import { useBacktestStore } from '@/stores/backtestStore'
import { useStrategyStore } from '@/stores/strategyStore'
import type { Strategy } from '@/types'
import { useNotificationStore } from '@/stores/notificationStore'
import { useWebSocket } from '@/hooks/useWebSocket'
import Editor from '@monaco-editor/react'
import DataSelector from '@/components/Backtest/DataSelector'
import ParamForm from '@/components/Backtest/ParamForm'

const { Title, Text } = Typography
const { Option } = Select

const DEFAULT_CODE = `from stockquant.strategy import BaseStrategy
from stockquant.indicators import EMA

class DualMACrossover(BaseStrategy):
    name = "Dual MA Crossover"
    parameters = {"fast": 5, "slow": 20, "position_size": 0.1}

    def on_start(self):
        self.ma_fast = EMA(self.data, period=self.parameters["fast"])
        self.ma_slow = EMA(self.data, period=self.parameters["slow"])

    def on_bar(self):
        if self.ma_fast[0] > self.ma_slow[0] and self.ma_fast[-1] <= self.ma_slow[-1]:
            self.order_market(self.data.close[0], int(self.portfolio.cash * self.parameters["position_size"] / self.data.close[0]))
        elif self.ma_fast[0] < self.ma_slow[0] and self.ma_fast[-1] >= self.ma_slow[-1]:
            self.close_all()
`

const TEMPLATES: Array<{ label: string; value: string; class_name: string; default_params: Record<string, number>; code: string }> = [
  {
    label: 'Dual MA Crossover',
    value: 'ma_crossover',
    class_name: 'DualMACrossoverStrategy',
    default_params: { fast_period: 5, slow_period: 20 },
    code: `from stockquant.strategy import BaseStrategy
from stockquant.indicators import EMA

class DualMACrossoverStrategy(BaseStrategy):
    name = "Dual MA Crossover"
    parameters = {"fast_period": 5, "slow_period": 20, "position_size": 0.1}

    def on_start(self):
        self._ma_fast = []
        self._ma_slow = []

    def on_bar(self, bars):
        for symbol, bar in bars.items():
            if symbol not in self._ma_fast:
                self._ma_fast[symbol] = []
                self._ma_slow[symbol] = []
            self._ma_fast[symbol].append(bar.close)
            self._ma_slow[symbol].append(bar.close)
            if len(self._ma_fast[symbol]) < self.parameters["fast_period"]:
                continue
            if len(self._ma_slow[symbol]) < self.parameters["slow_period"]:
                continue
            fast_now = sum(self._ma_fast[symbol][-self.parameters["fast_period"]:]) / self.parameters["fast_period"]
            slow_now = sum(self._ma_slow[symbol][-self.parameters["slow_period"]:]) / self.parameters["slow_period"]
            fast_prev = sum(self._ma_fast[symbol][-self.parameters["fast_period"]-1:-1]) / self.parameters["fast_period"]
            slow_prev = sum(self._ma_slow[symbol][-self.parameters["slow_period"]-1:-1]) / self.parameters["slow_period"]
            if fast_prev <= slow_prev and fast_now > slow_now:
                self.order_market(bar.close, 100)
            elif fast_prev >= slow_prev and fast_now < slow_now:
                self.close_all()
`,
  },
  {
    label: 'RSI Reversal',
    value: 'rsi_reversal',
    class_name: 'RSIReversalStrategy',
    default_params: { rsi_period: 14, overbought: 70, oversold: 30 },
    code: `from stockquant.strategy import BaseStrategy
from stockquant.indicators import RSI

class RSIReversalStrategy(BaseStrategy):
    name = "RSI Reversal"
    parameters = {"rsi_period": 14, "overbought": 70, "oversold": 30, "position_size": 0.2}

    def on_start(self):
        self._rsi = None

    def on_bar(self, bars):
        for symbol, bar in bars.items():
            if self._rsi is None:
                self._rsi = []
            self._rsi.append(bar.close)
            if len(self._rsi) < self.parameters["rsi_period"] + 1:
                continue
            values = self._rsi[-self.parameters["rsi_period"]-1:]
            diffs = [(values[i] - values[i-1]) / values[i-1] * 100 for i in range(1, len(values))]
            avg_gain = sum(d for d in diffs if d > 0) / self.parameters["rsi_period"]
            avg_loss = abs(sum(d for d in diffs if d < 0)) / self.parameters["rsi_period"]
            rs = avg_gain / avg_loss if avg_loss != 0 else 100
            rsi = 100 - 100 / (1 + rs)
            if rsi < self.parameters["oversold"]:
                self.order_market(bar.close, 100)
            elif rsi > self.parameters["overbought"]:
                self.close_all()
`,
  },
  {
    label: 'Bollinger Bounce',
    value: 'bollinger',
    class_name: 'BollingerBounceStrategy',
    default_params: { boll_period: 20, boll_std: 2 },
    code: `from stockquant.strategy import BaseStrategy

class BollingerBounceStrategy(BaseStrategy):
    name = "Bollinger Bounce"
    parameters = {"boll_period": 20, "boll_std": 2, "position_size": 0.1}

    def on_start(self):
        self._prices = []

    def on_bar(self, bars):
        for symbol, bar in bars.items():
            if symbol not in self._prices:
                self._prices[symbol] = []
            self._prices[symbol].append(bar.close)
            p = self._prices[symbol][-self.parameters["boll_period"]:]
            if len(p) < self.parameters["boll_period"]:
                continue
            ma = sum(p) / len(p)
            std = (sum((x - ma) ** 2 for x in p) / len(p)) ** 0.5
            upper = ma + self.parameters["boll_std"] * std
            lower = ma - self.parameters["boll_std"] * std
            if bar.close <= lower:
                self.order_market(bar.close, 100)
            elif bar.close >= upper:
                self.close_all()
`,
  },
  {
    label: 'MACD Divergence',
    value: 'macd',
    class_name: 'MACDDivergenceStrategy',
    default_params: { fast_period: 12, slow_period: 26, signal_period: 9 },
    code: `from stockquant.strategy import BaseStrategy

class MACDDivergenceStrategy(BaseStrategy):
    name = "MACD Divergence"
    parameters = {"fast_period": 12, "slow_period": 26, "signal_period": 9, "position_size": 0.1}

    def on_start(self):
        self._prices = []
        self._ema_fast = []
        self._ema_slow = []

    def _ema(self, values, period):
        if not values:
            return values[-1] if values else 0
        k = 2 / (period + 1)
        ema = values[0]
        for v in values[1:]:
            ema = v * k + ema * (1 - k)
        return ema

    def on_bar(self, bars):
        for symbol, bar in bars.items():
            if symbol not in self._prices:
                self._prices[symbol] = []
                self._ema_fast = []
                self._ema_slow = []
            self._prices[symbol].append(bar.close)
            p = self._prices[symbol]
            if len(p) < self.parameters["slow_period"]:
                continue
            self._ema_fast.append(self._ema(p[-self.parameters["slow_period"]:], self.parameters["fast_period"]))
            self._ema_slow.append(self._ema(p[-self.parameters["slow_period"]:], self.parameters["slow_period"]))
            if len(self._ema_fast) < self.parameters["signal_period"] + 1:
                continue
            hist_diff = self._ema_fast[-1] - self._ema_slow[-1]
            hist_diff_prev = self._ema_fast[-2] - self._ema_slow[-2]
            signal = sum(self._ema_fast[-i] - self._ema_slow[-i] for i in range(1, self.parameters["signal_period"]+1)) / self.parameters["signal_period"]
            signal_prev = sum(self._ema_fast[-i-1] - self._ema_slow[-i-1] for i in range(1, self.parameters["signal_period"]+1)) / self.parameters["signal_period"]
            if hist_diff_prev < 0 and hist_diff >= 0 and signal_prev < 0:
                self.order_market(bar.close, 100)
            elif hist_diff_prev > 0 and hist_diff <= 0:
                self.close_all()
`,
  },
  {
    label: 'Dual Thrust',
    value: 'dual_thrust',
    class_name: 'DualThrustStrategy',
    default_params: { lookback: 4, k1: 0.5, k2: 0.5 },
    code: `from stockquant.strategy import BaseStrategy

class DualThrustStrategy(BaseStrategy):
    name = "Dual Thrust"
    parameters = {"lookback": 4, "k1": 0.5, "k2": 0.5, "position_size": 0.1}

    def on_start(self):
        self._range = 0

    def on_bar(self, bars):
        for symbol, bar in bars.items():
            if self._range == 0:
                self._range = 0
                for _ in range(min(self.parameters["lookback"], len(bar.history))):
                    self._range = max(self._range, bar.high - bar.low)
            upper = bar.open + self.parameters["k1"] * self._range
            lower = bar.open - self.parameters["k2"] * self._range
            if bar.close > upper:
                self.order_market(bar.close, 100)
            elif bar.close < lower:
                self.close_all()
`,
  },
  {
    label: 'Mean Reversion',
    value: 'mean_reversion',
    class_name: 'MeanReversionStrategy',
    default_params: { ma_period: 20, std_threshold: 2.0 },
    code: `from stockquant.strategy import BaseStrategy

class MeanReversionStrategy(BaseStrategy):
    name = "Mean Reversion"
    parameters = {"ma_period": 20, "std_threshold": 2.0, "position_size": 0.1}

    def on_start(self):
        self._prices = []

    def on_bar(self, bars):
        for symbol, bar in bars.items():
            if symbol not in self._prices:
                self._prices[symbol] = []
            self._prices[symbol].append(bar.close)
            p = self._prices[symbol][-self.parameters["ma_period"]:]
            if len(p) < self.parameters["ma_period"]:
                continue
            ma = sum(p) / len(p)
            std = (sum((x - ma) ** 2 for x in p) / len(p)) ** 0.5
            upper = ma + self.parameters["std_threshold"] * std
            lower = ma - self.parameters["std_threshold"] * std
            if bar.close < lower:
                self.order_market(bar.close, 100)
            elif bar.close > upper:
                self.close_all()
`,
  },
  {
    label: 'Momentum',
    value: 'momentum',
    class_name: 'MomentumStrategy',
    default_params: { roc_period: 10, macd_fast: 12, macd_slow: 26, macd_signal: 9 },
    code: `from stockquant.strategy import BaseStrategy

class MomentumStrategy(BaseStrategy):
    name = "Momentum"
    parameters = {"roc_period": 10, "macd_fast": 12, "macd_slow": 26, "macd_signal": 9, "position_size": 0.1}

    def on_start(self):
        self._prices = []

    def _roc(self, values, period):
        if len(values) < period + 1:
            return 0
        return (values[-1] - values[-period-1]) / values[-period-1]

    def on_bar(self, bars):
        for symbol, bar in bars.items():
            if symbol not in self._prices:
                self._prices[symbol] = []
            self._prices[symbol].append(bar.close)
            p = self._prices[symbol]
            roc = self._roc(p, self.parameters["roc_period"])
            if roc > 0.05:
                self.order_market(bar.close, 100)
            elif roc < -0.05:
                self.close_all()
`,
  },
]

interface TemplateInfo {
  class_name: string
  default_params: Record<string, number>
}

const TEMPLATE_MAP: Record<string, TemplateInfo & { code: string }> = {
  'ma_crossover': { class_name: 'DualMACrossoverStrategy', default_params: { fast_period: 5, slow_period: 20 }, code: TEMPLATES[0].code },
  'rsi_reversal': { class_name: 'RSIReversalStrategy', default_params: { rsi_period: 14, overbought: 70, oversold: 30 }, code: TEMPLATES[1].code },
  'bollinger': { class_name: 'BollingerBounceStrategy', default_params: { boll_period: 20, boll_std: 2 }, code: TEMPLATES[2].code },
  'macd': { class_name: 'MACDDivergenceStrategy', default_params: { fast_period: 12, slow_period: 26, signal_period: 9 }, code: TEMPLATES[3].code },
  'dual_thrust': { class_name: 'DualThrustStrategy', default_params: { lookback: 4, k1: 0.5, k2: 0.5 }, code: TEMPLATES[4].code },
  'mean_reversion': { class_name: 'MeanReversionStrategy', default_params: { ma_period: 20, std_threshold: 2.0 }, code: TEMPLATES[5].code },
  'momentum': { class_name: 'MomentumStrategy', default_params: { roc_period: 10, macd_fast: 12, macd_slow: 26, macd_signal: 9 }, code: TEMPLATES[6].code },
}

export default function Backtest() {
  const [form] = Form.useForm()
  const navigate = useNavigate()
  const submitTask = useBacktestStore((s) => s.submitTask)
  const fetchStrategies = useStrategyStore((s) => s.fetchStrategies)
  const strategies = useStrategyStore((s) => s.strategies)
  const addNotification = useNotificationStore((s) => s.add)
  const fetchTasks = useBacktestStore((s) => s.fetchTasks)
  const tasks = useBacktestStore((s) => s.tasks)
  const [submitting, setSubmitting] = useState(false)
  const [progress, setProgress] = useState<number | null>(null)
  const [progressTaskId, setProgressTaskId] = useState<string | null>(null)
  const [savedStrategyCode, setSavedStrategyCode] = useState<string>('')
  const [editorValue, setEditorValue] = useState(DEFAULT_CODE)
  const [editorKey, setEditorKey] = useState(0)
  const [dynamicParams, setDynamicParams] = useState<Record<string, number>>({})
  const { messages: wsMessages } = useWebSocket(
    progressTaskId ? `/ws/backtest/${progressTaskId}` : null
  )

  // 当前选中的模板参数定义
  const selectedTemplate = Form.useWatch('template', form)
  const paramDefs = useMemo(() => {
    if (!selectedTemplate) return {}
    return TEMPLATE_MAP[selectedTemplate]?.default_params ?? {}
  }, [selectedTemplate])

  useEffect(() => { fetchStrategies() }, [fetchStrategies])
  useEffect(() => { fetchTasks() }, [fetchTasks])

  // 监听 WS 进度消息
  useEffect(() => {
    if (wsMessages.length === 0) return
    const latest = wsMessages[wsMessages.length - 1]
    if (latest.type === 'progress' && typeof (latest as any).data?.progress === 'number') {
      setProgress(Math.min(100, Math.max(0, (latest as any).data.progress)))
    }
    if (latest.type === 'complete' && progressTaskId) {
      setProgress(100)
      // 短暂展示 100% 后跳转
      setTimeout(() => {
        navigate(`/backtest/${progressTaskId}`)
        setProgressTaskId(null)
        setProgress(null)
      }, 500)
    }
  }, [wsMessages, progressTaskId, navigate])

  const handleTemplateSelect = (templateValue: string) => {
    const tmpl = TEMPLATE_MAP[templateValue]
    if (tmpl) {
      setEditorValue(tmpl.code)
      setEditorKey((k) => k + 1)
      form.setFieldValue('strategy_code', tmpl.code)
      form.setFieldValue('strategy_class', tmpl.class_name)
      // 用模板默认参数初始化动态参数
      setDynamicParams({ ...tmpl.default_params })
    }
  }

  /** Load a saved strategy: set name, code, and try to match template for params */
  const handleSavedStrategySelect = (strategyId: string) => {
    const saved = strategies.find((s: Strategy) => s.id === strategyId)
    if (!saved) return
    setSavedStrategyCode(saved.code)
    setEditorValue(saved.code)
    setEditorKey((k) => k + 1)
    form.setFieldValue('strategy_name', saved.name)
    form.setFieldValue('strategy_code', saved.code)
    // Try to match name/class from code to auto-select template
    const codeUpper = saved.code.toUpperCase()
    for (const [key, tmpl] of Object.entries(TEMPLATE_MAP)) {
      if (codeUpper.includes(tmpl.class_name.toUpperCase())) {
        form.setFieldValue('template', key)
        form.setFieldValue('strategy_class', tmpl.class_name)
        break
      }
    }
  }

  const handleSubmit = async (values: Record<string, unknown>) => {
    setSubmitting(true)
    try {
      const riskRules = values.risk_rules as Record<string, number> | undefined
      const template = values.template as string | undefined
      const tmpl = template ? TEMPLATE_MAP[template] : null
      const savedStrategyId = values.saved_strategy_id as string | undefined

      // If a saved strategy is selected, use its code; otherwise use the template code or user-edited code
      let finalCode = values.strategy_code as string
      if (savedStrategyId) {
        finalCode = savedStrategyCode || finalCode
      } else if (template && tmpl) {
        finalCode = tmpl.code
      }

      const params: Record<string, number> = {}
      // 优先使用动态参数表单的值，其次用模板默认值
      if (tmpl) {
        for (const [k, v] of Object.entries(tmpl.default_params)) {
          params[k] = v
        }
      }
      // 动态参数表单覆盖模板默认值
      for (const [k, v] of Object.entries(dynamicParams)) {
        if (typeof v === 'number' && !isNaN(v)) params[k] = v
      }

      const result = await submitTask({
        strategy_name: values.strategy_name as string,
        strategy_class: tmpl?.class_name,
        strategy_params: Object.keys(params).length > 0 ? params : undefined,
        symbols: String(values.symbols).split(',').map((s: string) => s.trim()),
        start_date: typeof values.start_date === 'string' ? values.start_date : dayjs.isDayjs(values.start_date) ? (values.start_date as dayjs.Dayjs).format('YYYY-MM-DD') : '',
        end_date: typeof values.end_date === 'string' ? values.end_date : dayjs.isDayjs(values.end_date) ? (values.end_date as dayjs.Dayjs).format('YYYY-MM-DD') : '',
        cash: values.cash as number,
        strategy_code: finalCode,
        saved_strategy_id: savedStrategyId || undefined,
        commission_type: 'ashare',
        slippage_type: 'none',
        benchmark: (values.benchmark as string) || undefined,
        risk_rules: riskRules ? {
          max_position_pct: (riskRules.max_position_pct ?? 30) / 100,
          max_daily_loss_pct: (riskRules.max_daily_loss_pct ?? 5) / 100,
          max_drawdown_pct: (riskRules.max_drawdown_pct ?? 15) / 100,
          max_orders_per_minute: riskRules.max_orders_per_minute ?? 10,
        } : undefined,
      } as any)

      const taskId = result?.task_id || result?.task_id || 'latest'
      addNotification({ type: 'info', title: '回测已提交', message: values.strategy_name as string, time: new Date().toLocaleTimeString() })
      setProgress(0)
      setProgressTaskId(taskId)

      // 如果 WS 不可用，2 秒后直接跳转
      setTimeout(() => {
        setProgressTaskId((currentId) => {
          if (currentId) {
            navigate(`/backtest/${taskId}`)
          }
          setProgress(null)
          return null
        })
      }, 2000)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '提交失败'
      console.error('Backtest submit failed:', msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: 1000 }}>
      {/* 回测历史列表 */}
      {tasks.length > 0 && (
        <Collapse
          size="small"
          style={{ marginBottom: 16 }}
          items={[{
            key: 'history',
            label: <span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Clock size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />
              历史回测 ({tasks.length})
            </span>,
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {tasks.slice(0, 10).map((t: any) => (
                  <div
                    key={t.task_id}
                    onClick={() => navigate(`/backtest/${t.task_id}`)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '6px 10px', borderRadius: 6, cursor: 'pointer',
                      background: 'var(--color-bg-hover)',
                      border: '1px solid var(--color-border-default)',
                      transition: 'border-color 0.2s',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--color-brand-primary)')}
                    onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--color-border-default)')}
                  >
                    <span style={{ flex: 1, fontSize: 12, fontWeight: 500 }}>{t.strategy_name || '未命名'}</span>
                    <Tag color={t.status === 'completed' ? 'green' : t.status === 'running' ? 'blue' : 'red'} style={{ margin: 0, fontSize: 10 }}>
                      {t.status === 'completed' ? '完成' : t.status === 'running' ? '运行中' : '失败'}
                    </Tag>
                    <span style={{ fontSize: 10, color: 'var(--color-text-tertiary)' }}>
                      {t.created_at ? new Date(t.created_at).toLocaleString() : ''}
                    </span>
                    <ArrowRight size={12} style={{ color: 'var(--color-text-tertiary)' }} />
                  </div>
                ))}
              </div>
            ),
          }]}
        />
      )}

      <Title level={4} style={{ marginBottom: 4, fontWeight: 600 }}>新回测</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24, fontSize: 13 }}>
        配置策略参数，启动回测验证
      </Text>

      <Form form={form} layout="vertical" onFinish={handleSubmit} initialValues={{ cash: 1_000_000, commission_type: 'ashare', slippage_type: 'none' }}>
        <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Code size={16} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> 策略配置
        </span>} styles={{ body: { padding: 16 } }} style={{ marginBottom: 16 }}>
          <Form.Item label="策略名称" name="strategy_name" rules={[{ required: true, message: '必填' }]}>
            <Input placeholder="e.g. Dual MA Crossover" />
          </Form.Item>

          <Form.Item label="选择已保存策略" name="saved_strategy_id">
            <Select
              placeholder="选择已保存策略（可选）"
              onChange={handleSavedStrategySelect}
              allowClear
              style={{ width: '100%' }}
            >
              {strategies.map((s: Strategy) => (
                <Option key={s.id} value={s.id}>{s.name}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item label="策略模板" name="template">
            <Select placeholder="选择模板（可选）" onChange={handleTemplateSelect} style={{ width: '100%' }}>
              {TEMPLATES.map((t) => <Option key={t.value} value={t.value}>{t.label}</Option>)}
            </Select>
          </Form.Item>

          {/* 隐藏字段：后端策略类名 */}
          <Form.Item name="strategy_class">
            <Input style={{ display: 'none' }} />
          </Form.Item>

          {/* 策略参数动态表单 */}
          {Object.keys(paramDefs).length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <Text type="secondary" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: 8 }}>
                策略参数
              </Text>
              <Row gutter={[12, 8]}>
                {Object.entries(paramDefs).map(([key, defaultVal]) => (
                  <Col xs={12} sm={8} key={key}>
                    <InputNumber
                      size="small"
                      style={{ width: '100%' }}
                      addonBefore={key}
                      value={dynamicParams[key] ?? defaultVal}
                      step={Number.isInteger(defaultVal) ? 1 : 0.1}
                      onChange={(v) => {
                        if (v !== null && !isNaN(v)) {
                          setDynamicParams((prev) => ({ ...prev, [key]: v }))
                        }
                      }}
                    />
                  </Col>
                ))}
              </Row>
            </div>
          )}

          <Form.Item label="策略代码" name="strategy_code" rules={[{ required: true, message: '必填' }]}>
            <div style={{ border: '1px solid var(--color-border-default)', borderRadius: 6, overflow: 'hidden' }}>
              <Editor
                key={editorKey}
                height={300}
                defaultLanguage="python"
                value={editorValue}
                theme="vs-dark"
                options={{
                  fontSize: 13, lineHeight: 20, minimap: { enabled: false },
                  scrollBeyondLastLine: false, automaticLayout: true, tabSize: 4,
                  padding: { top: 8, bottom: 8 },
                }}
              />
            </div>
          </Form.Item>
        </Card>

        <DataSelector form={form} />

        <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>基准对比</span>} styles={{ body: { padding: 16 } }} style={{ marginBottom: 16 }}>
          <Form.Item label="基准指数" name="benchmark" initialValue="">
            <Select style={{ width: '100%' }}>
              <Option value="">无基准</Option>
              <Option value="hs300">沪深300</Option>
              <Option value="zz500">中证500</Option>
              <Option value="cyb">创业板指</Option>
            </Select>
          </Form.Item>
        </Card>

        <ParamForm form={form} />

        {progress !== null && (
          <Card size="small" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Progress
                percent={progress}
                strokeColor={{ from: '#3b82f6', to: '#8b5cf6' }}
                style={{ flex: 1 }}
                format={(p) => `${p}%`}
              />
              <Text type="secondary" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                {progress < 100 ? '回测运行中…' : '回测完成，正在跳转…'}
              </Text>
            </div>
          </Card>
        )}

        <Form.Item style={{ marginBottom: 0 }}>
          <Button
            type="primary"
            icon={<Play size={20} weight="fill" />}
            htmlType="submit"
            size="large"
            block
            loading={submitting}
          >
            运行回测
          </Button>
        </Form.Item>
      </Form>
    </div>
  )
}
