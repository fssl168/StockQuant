import type { FormInstance } from 'antd'
import { Form, Input, InputNumber, Card, Select, Row, Col, DatePicker } from 'antd'

const { Option } = Select

interface DataSelectorProps {
  form: FormInstance
}

export default function DataSelector({ form: _form }: DataSelectorProps) {
  return (
    <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>数据配置</span>} styles={{ body: { padding: 16 } }} style={{ marginBottom: 16 }}>
      <Row gutter={16}>
        <Col span={12}>
          <Form.Item label="标的" name="symbols" rules={[{ required: true, message: '必填' }]}>
            <Input placeholder="逗号分隔: sh600519, sz000858" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item label="数据源" name="data_source">
            <Select defaultValue="alphafeed" style={{ width: '100%' }}>
              <Option value="alphafeed">AlphaFeed</Option>
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
  )
}
