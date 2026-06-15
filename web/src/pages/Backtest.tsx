import { useState } from 'react'
import { Form, Input, InputNumber, Button, Select, Card, Divider, Alert } from 'antd'
import { PlayCircleOutlined } from '@ant-design/icons'
import { useBacktestStore } from '@/stores/backtestStore'
import { useNotificationStore } from '@/stores/notificationStore'

const { Option } = Select

export default function Backtest() {
  const [form] = Form.useForm()
  const submitTask = useBacktestStore((s) => s.submitTask)
  const addNotification = useNotificationStore((s) => s.add)

  const handleSubmit = async (values: Record<string, unknown>) => {
    try {
      await submitTask({
        strategy_name: values.strategy_name as string,
        symbols: (values.symbols as string[]).split(',').map((s) => s.trim()),
        start_date: values.start_date as string,
        end_date: values.end_date as string,
        cash: values.cash as number,
        strategy_code: values.strategy_code as string,
        commission_type: 'ashare',
        slippage_type: 'none',
      })
      addNotification({ type: 'info', title: '回测已提交', message: values.strategy_name, time: new Date().toLocaleTimeString() })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '提交失败'
      console.error(msg)
    }
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <Card title="回测配置">
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item label="策略名称" name="strategy_name" rules={[{ required: true }]}>
            <Input placeholder="如：双均线策略" />
          </Form.Item>

          <Form.Item label="股票代码" name="symbols" rules={[{ required: true }]}>
            <Input placeholder="多个代码用逗号分隔，如：sh600519,sz000858" />
          </Form.Item>

          <Form.Item label="时间范围">
            <Form.Item name="start_date" style={{ display: 'inline-block', width: 'calc(50% - 8px)' }} rules={[{ required: true }]}>
              <Input placeholder="起始日期 YYYY-MM-DD" />
            </Form.Item>
            <Form.Item name="end_date" style={{ display: 'inline-block', width: 'calc(50% - 8px)', marginLeft: 16 }} rules={[{ required: true }]}>
              <Input placeholder="结束日期 YYYY-MM-DD" />
            </Form.Item>
          </Form.Item>

          <Form.Item label="初始资金" name="cash" rules={[{ required: true }]}>
            <InputNumber min={10000} step={100000} defaultValue={1000000} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item label="策略代码" name="strategy_code">
            <Input.TextArea rows={10} placeholder="粘贴 Python 策略代码..." />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" icon={<PlayCircleOutlined />} size="large" block>
              启动回测
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
