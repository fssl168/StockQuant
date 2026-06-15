import { useState } from 'react'
import { Form, Input, InputNumber, Button, Card, Typography, Select, Row, Col, DatePicker } from 'antd'
import dayjs from 'dayjs'
import { Play, Code } from '@phosphor-icons/react'
import { useBacktestStore } from '@/stores/backtestStore'
import { useNotificationStore } from '@/stores/notificationStore'
import Editor from '@monaco-editor/react'

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
  const submitTask = useBacktestStore((s) => s.submitTask)
  const addNotification = useNotificationStore((s) => s.add)
  const [submitting, setSubmitting] = useState(false)

  const handleTemplateSelect = () => {
    form.setFieldValue('strategy_code', DEFAULT_CODE)
  }

  const handleSubmit = async (values: Record<string, unknown>) => {
    setSubmitting(true)
    try {
      await submitTask({
        strategy_name: values.strategy_name as string,
        symbols: String(values.symbols).split(',').map((s: string) => s.trim()),
        start_date: typeof values.start_date === 'string' ? values.start_date : dayjs.isDayjs(values.start_date) ? (values.start_date as dayjs.Dayjs).format('YYYY-MM-DD') : '',
        end_date: typeof values.end_date === 'string' ? values.end_date : dayjs.isDayjs(values.end_date) ? (values.end_date as dayjs.Dayjs).format('YYYY-MM-DD') : '',
        cash: values.cash as number,
        strategy_code: values.strategy_code as string,
        commission_type: 'ashare',
        slippage_type: 'none',
      })
      addNotification({ type: 'info', title: 'Backtest submitted', message: values.strategy_name as string, time: new Date().toLocaleTimeString() })
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

        <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>数据配置</span>} styles={{ body: { padding: 16 } }} style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="标的" name="symbols" rules={[{ required: true, message: '必填' }]}>
                <Input placeholder="逗号分隔: sh600519, sz000858" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="数据源" name="data_source">
                <Select defaultValue="baostock" style={{ width: '100%' }}>
                  <Option value="baostock">BaoStock</Option>
                  <Option value="akshare">AkShare</Option>
                  <Option value="csv">CSV</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="开始日期" name="start_date" rules={[{ required: true, message: '必填' }]}>
                <DatePicker style={{ width: '100%' }} format="YYYY-MM-DD" placeholder="选择开始日期" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="结束日期" name="end_date" rules={[{ required: true, message: '必填' }]}>
                <DatePicker style={{ width: '100%' }} format="YYYY-MM-DD" placeholder="选择结束日期" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="初始资金" name="cash" rules={[{ required: true }]}>
            <InputNumber min={10000} step={100000} style={{ width: '100%' }} formatter={(v) => `¥ ${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')} />
          </Form.Item>
        </Card>

        <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>执行参数</span>} styles={{ body: { padding: 16 } }} style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="佣金类型" name="commission_type">
                <Select>
                  <Option value="ashare">A 股</Option>
                  <Option value="none">无</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="滑点" name="slippage_type">
                <Select>
                  <Option value="none">无</Option>
                  <Option value="fixed">固定</Option>
                  <Option value="percent">百分比</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="风控熔断" name="max_drawdown">
                <InputNumber min={5} max={50} step={1} style={{ width: '100%' }} formatter={(v) => `${v}%`} parser={(v) => Number(v || '0') as any} defaultValue={15} />
              </Form.Item>
            </Col>
          </Row>
        </Card>

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
