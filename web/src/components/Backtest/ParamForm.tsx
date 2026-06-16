import type { FormInstance } from 'antd'
import { Form, InputNumber, Card, Select, Row, Col } from 'antd'

const { Option } = Select

interface ParamFormProps {
  form: FormInstance
}

export default function ParamForm({ form: _form }: ParamFormProps) {
  return (
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
  )
}
