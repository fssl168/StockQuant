import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, Button, Card, Typography, Select } from 'antd'
import dayjs from 'dayjs'
import { Play, Code } from '@phosphor-icons/react'
import { useBacktestStore } from '@/stores/backtestStore'
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

const TEMPLATES = [
  { label: 'Dual MA Crossover', value: 'ma_crossover' },
  { label: 'RSI Reversal', value: 'rsi_reversal' },
  { label: 'Bollinger Bounce', value: 'bollinger' },
  { label: 'MACD Divergence', value: 'macd' },
  { label: 'Dual Thrust', value: 'dual_thrust' },
  { label: 'Mean Reversion', value: 'mean_reversion' },
  { label: 'Momentum', value: 'momentum' },
]

export default function Backtest() {
  const [form] = Form.useForm()
  const navigate = useNavigate()
  const submitTask = useBacktestStore((s) => s.submitTask)
  const addNotification = useNotificationStore((s) => s.add)
  const [submitting, setSubmitting] = useState(false)
  const [progressTaskId, setProgressTaskId] = useState<string | null>(null)
  const { messages: wsMessages } = useWebSocket(
    progressTaskId ? `/ws/backtest/${progressTaskId}` : null
  )

  // 监听 WS 进度消息
  useEffect(() => {
    if (wsMessages.length === 0) return
    const latest = wsMessages[wsMessages.length - 1]
    if (latest.type === 'complete' && progressTaskId) {
      navigate(`/backtest/${progressTaskId}`)
      setProgressTaskId(null)
    }
  }, [wsMessages, progressTaskId, navigate])

  const handleTemplateSelect = () => {
    form.setFieldValue('strategy_code', DEFAULT_CODE)
  }

  const handleSubmit = async (values: Record<string, unknown>) => {
    setSubmitting(true)
    try {
      const riskRules = values.risk_rules as Record<string, number> | undefined
      const result = await submitTask({
        strategy_name: values.strategy_name as string,
        symbols: String(values.symbols).split(',').map((s: string) => s.trim()),
        start_date: typeof values.start_date === 'string' ? values.start_date : dayjs.isDayjs(values.start_date) ? (values.start_date as dayjs.Dayjs).format('YYYY-MM-DD') : '',
        end_date: typeof values.end_date === 'string' ? values.end_date : dayjs.isDayjs(values.end_date) ? (values.end_date as dayjs.Dayjs).format('YYYY-MM-DD') : '',
        cash: values.cash as number,
        strategy_code: values.strategy_code as string,
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
      addNotification({ type: 'info', title: 'Backtest submitted', message: values.strategy_name as string, time: new Date().toLocaleTimeString() })
      // Navigate to result page
      const taskId = (result as unknown as { task_id?: string })?.task_id ?? 'latest'
      setProgressTaskId(taskId)
      // 如果 WS 不可用，2 秒后直接跳转
      setTimeout(() => {
        setProgressTaskId((currentId) => {
          if (currentId) {
            navigate(`/backtest/${taskId}`)
          }
          return null
        })
      }, 2000)
    } catch (err: unknown) {
      console.error(err instanceof Error ? err.message : 'Submission failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: 1000 }}>
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

          <Form.Item label="策略模板" name="template">
            <Select placeholder="选择模板（可选）" onChange={handleTemplateSelect} style={{ width: '100%' }}>
              {TEMPLATES.map((t) => <Option key={t.value} value={t.value}>{t.label}</Option>)}
            </Select>
          </Form.Item>

          <Form.Item label="策略代码" name="strategy_code" rules={[{ required: true, message: '必填' }]}>
            <div style={{ border: '1px solid var(--color-border-default)', borderRadius: 6, overflow: 'hidden' }}>
              <Editor
                height={300}
                defaultLanguage="python"
                defaultValue={DEFAULT_CODE}
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
