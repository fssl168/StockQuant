import { useState } from 'react'
import { Card, Input, InputNumber, Switch, Select, Button, Space, Divider, message } from 'antd'
import { SaveOutlined, SyncOutlined } from '@ant-design/icons'

const { Option } = Select

export default function Settings() {
  const [LLM_MODEL, setLLM_MODEL] = useState('gpt-4o')
  const [API_KEY, setAPI_KEY] = useState('')
  const [baseURL, setBaseURL] = useState('')
  const [fallbackModels, setFallbackModels] = useState(['gpt-3.5-turbo', 'claude-3-haiku'])

  const handleSave = () => {
    message.success('设置已保存')
  }

  const handleReset = () => {
    setLLM_MODEL('gpt-4o')
    setAPI_KEY('')
    setBaseURL('')
    message.info('已恢复默认设置')
  }

  return (
    <div style={{ maxWidth: 800 }}>
      <Card title="LLM 配置" extra={<Space>
        <Button icon={<SaveOutlined />} type="primary" onClick={handleSave}>保存</Button>
        <Button icon={<SyncOutlined />} onClick={handleReset}>重置</Button>
      </Space>}>
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <div>
            <label>主模型</label>
            <Select value={LLM_MODEL} onChange={setLLM_MODEL} style={{ width: '100%', marginTop: 8 }}>
              <Option value="gpt-4o">GPT-4o</Option>
              <Option value="gpt-4">GPT-4</Option>
              <Option value="gpt-3.5-turbo">GPT-3.5 Turbo</Option>
              <Option value="claude-3-opus">Claude 3 Opus</Option>
              <Option value="claude-3-sonnet">Claude 3 Sonnet</Option>
            </Select>
          </div>
          <div>
            <label>API Key</label>
            <Input.Password value={API_KEY} onChange={(e) => setAPI_KEY(e.target.value)} placeholder="sk-xxx" style={{ marginTop: 8 }} />
          </div>
          <div>
            <label>Base URL</label>
            <Input value={baseURL} onChange={(e) => setBaseURL(e.target.value)} placeholder="https://api.openai.com/v1" style={{ marginTop: 8 }} />
          </div>
        </Space>
      </Card>

      <Card title="通知渠道" style={{ marginTop: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          {['钉钉', '企业微信', '飞书', 'Telegram', 'Discord', '邮件', 'PushPlus', 'ServerChan', 'Webhook'].map((ch) => (
            <div key={ch}>
              <Space>
                <span>{ch}</span>
                <Switch defaultChecked={ch === '钉钉' || ch === '邮件'} size="small" />
              </Space>
            </div>
          ))}
        </Space>
      </Card>

      <Card title="数据源配置" style={{ marginTop: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <label>默认数据源</label>
            <Select defaultValue="akshare" style={{ width: '100%', marginTop: 8 }}>
              <Option value="akshare">AkShare</Option>
              <Option value="baostock">BaoStock</Option>
              <Option value="csv">CSV 文件</Option>
              <Option value="parquet">Parquet</Option>
            </Select>
          </div>
        </Space>
      </Card>

      <Card title="风控参数" style={{ marginTop: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <InputNumber label="最大仓位比例" defaultValue={0.8} min={0} max={1} step={0.05} style={{ width: '100%' }} />
          <InputNumber label="单笔最大亏损(%)" defaultValue={2} min={0} max={10} step={0.5} style={{ width: '100%' }} />
          <InputNumber label="总回撤止损(%)" defaultValue={15} min={0} max={50} step={1} style={{ width: '100%' }} />
          <InputNumber label="行业集中度上限(%)" defaultValue={30} min={0} max={100} step={5} style={{ width: '100%' }} />
        </Space>
      </Card>
    </div>
  )
}
