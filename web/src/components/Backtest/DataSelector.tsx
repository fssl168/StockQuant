import type { FormInstance } from 'antd'
import { Form, Input, InputNumber, Card, Select, Row, Col, DatePicker, Upload, Button, message } from 'antd'
import { UploadSimple } from '@phosphor-icons/react'

const { Option } = Select

interface DataSelectorProps {
  form: FormInstance
}

export default function DataSelector({ form }: DataSelectorProps) {
  const selectedSource = Form.useWatch('data_source', form)

  const handleUpload = async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`

      const resp = await fetch('/api/data/upload-csv', {
        method: 'POST',
        headers,
        body: formData,
      })
      if (!resp.ok) throw new Error('上传失败')
      const result = await resp.json()
      message.success(`CSV 已上传: ${result.filename || file.name}`)
      // 自动填充标的和时间范围
      if (result.symbols?.length) {
        form.setFieldValue('symbols', result.symbols.join(', '))
      }
    } catch (e: any) {
      message.error(`上传失败: ${e?.message || '未知错误'}`)
    }
    return false // prevent default upload behavior
  }

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
              <Option value="csv">CSV 文件</Option>
            </Select>
          </Form.Item>
        </Col>
      </Row>

      {selectedSource === 'csv' && (
        <Form.Item label="上传 CSV 文件">
          <Upload
            accept=".csv"
            showUploadList={false}
            beforeUpload={(file) => { handleUpload(file); return false }}
          >
            <Button size="small" icon={<UploadSimple size={14} />}>
              选择 CSV 文件
            </Button>
          </Upload>
          <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 4 }}>
            CSV 格式要求：date, open, high, low, close, volume 列，可选 symbol 列
          </div>
        </Form.Item>
      )}

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
