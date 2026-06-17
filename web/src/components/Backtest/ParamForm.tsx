import type { FormInstance } from 'antd'
import { Form, InputNumber, Card, Select, Row, Col, Slider } from 'antd'

const { Option } = Select

interface ParamFormProps {
  form: FormInstance
}

export default function ParamForm({ form: _form }: ParamFormProps) {
  return (
    <>
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

      <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>风控规则</span>} styles={{ body: { padding: 16 } }} style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item label="单票最大仓位" name={['risk_rules', 'max_position_pct']} initialValue={30}>
              <Slider min={0} max={100} step={5} marks={{ 0: '0%', 30: '30%', 50: '50%', 100: '100%' }} tooltip={{ formatter: (v) => `${v}%` }} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item label="单日最大亏损" name={['risk_rules', 'max_daily_loss_pct']} initialValue={5}>
              <Slider min={0} max={10} step={0.5} marks={{ 0: '0%', 5: '5%', 10: '10%' }} tooltip={{ formatter: (v) => `${v}%` }} />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item label="累计最大回撤熔断" name={['risk_rules', 'max_drawdown_pct']} initialValue={15}>
              <Slider min={5} max={50} step={1} marks={{ 5: '5%', 15: '15%', 30: '30%', 50: '50%' }} tooltip={{ formatter: (v) => `${v}%` }} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item label="订单频率限制" name={['risk_rules', 'max_orders_per_minute']} initialValue={10}>
              <InputNumber min={1} max={100} style={{ width: '100%' }} addonAfter="笔/分钟" />
            </Form.Item>
          </Col>
        </Row>
      </Card>
    </>
  )
}
