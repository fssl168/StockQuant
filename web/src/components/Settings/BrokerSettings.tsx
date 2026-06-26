import { Card, Form, Input, Select, Space, Typography, Button, Alert, Tag, Divider, InputNumber } from 'antd'
import { ApiOutlined, CheckCircleOutlined, DisconnectOutlined, ExperimentOutlined } from '@ant-design/icons'
import type { SettingEntry } from './types'

const { Text: AntText } = Typography

interface BrokerSettingsProps {
  values: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
}

const BROKER_ITEMS: SettingEntry[] = [
  { key: 'trading.broker', value: 'paper', defaultValue: 'paper', valueType: 'select', label: '券商通道', options: [
    { value: 'paper', label: '模拟盘 (Paper)' },
    { value: 'xtp', label: '中泰证券 XTP' },
    { value: 'qmt', label: '国信 QMT' },
    { value: 'ctp', label: '期货 CTP' },
  ]},
]

const XTP_ITEMS: SettingEntry[] = [
  { key: 'trading.xtp_ip', value: '127.0.0.1', defaultValue: '127.0.0.1', valueType: 'string', label: 'XTP 交易服务器', description: '券商提供的交易服务器 IP' },
  { key: 'trading.xtp_port', value: 6002, defaultValue: 6002, valueType: 'number', label: 'XTP 端口', min: 1, max: 65535 },
  { key: 'trading.xtp_key', value: '', defaultValue: '', valueType: 'string', label: '软件 KEY', description: '券商提供的软件 KEY', secret: true },
  { key: 'trading.xtp_account', value: '', defaultValue: '', valueType: 'string', label: '资金账号' },
]

const QMT_ITEMS: SettingEntry[] = [
  { key: 'trading.qmt_path', value: '', defaultValue: '', valueType: 'string', label: 'QMT 安装路径', description: '迅投 QMT 量化软件的安装目录' },
  { key: 'trading.qmt_account', value: '', defaultValue: '', valueType: 'string', label: 'QMT 资金账号' },
]

const CTP_ITEMS: SettingEntry[] = [
  { key: 'trading.ctp_broker_id', value: '', defaultValue: '', valueType: 'string', label: '期货公司代码' },
  { key: 'trading.ctp_user', value: '', defaultValue: '', valueType: 'string', label: 'CTP 账号' },
  { key: 'trading.ctp_password', value: '', defaultValue: '', valueType: 'string', label: 'CTP 密码', secret: true },
  { key: 'trading.ctp_front', value: 'tcp://127.0.0.1:51201', defaultValue: 'tcp://127.0.0.1:51201', valueType: 'string', label: 'CTP 交易服务器' },
]

function renderField(item: SettingEntry, value: unknown, onChange: (v: unknown) => void) {
  if (item.valueType === 'select') {
    return (
      <Select value={value as string} onChange={onChange} style={{ width: '100%' }}>
        {item.options?.map(opt => (
          <Select.Option key={opt.value} value={opt.value}>{opt.label}</Select.Option>
        ))}
      </Select>
    )
  }
  if (item.secret) {
    return <Input.Password value={value as string} onChange={e => onChange(e.target.value)} placeholder="请输入" />
  }
  if (item.valueType === 'number') {
    return <InputNumber value={value as number} onChange={onChange} min={item.min} max={item.max} style={{ width: '100%' }} />
  }
  return <Input value={value as string} onChange={e => onChange(e.target.value)} placeholder="请输入" />
}

export default function BrokerSettings({ values, onChange }: BrokerSettingsProps) {
  const broker = values['trading.broker'] as string || 'paper'
  
  const renderSection = (title: string, icon: React.ReactNode, items: SettingEntry[]) => (
    <Card size="small" title={<Space>{icon}<AntText>{title}</AntText></Space>} style={{ marginBottom: 16 }}>
      <Form layout="vertical">
        {items.filter(item => isVisible(item, values)).map(item => (
          <Form.Item 
            key={item.key} 
            label={<AntText strong style={{ fontSize: 13 }}>{item.label}</AntText>}
            tooltip={item.description}
            style={{ marginBottom: 12 }}
          >
            {renderField(item, values[item.key] ?? item.defaultValue, (v) => onChange(item.key, v))}
          </Form.Item>
        ))}
      </Form>
    </Card>
  )

  const renderBrokerConfig = () => {
    switch (broker) {
      case 'xtp':
        return renderSection('中泰 XTP 配置', <ApiOutlined />, XTP_ITEMS)
      case 'qmt':
        return renderSection('国信 QMT 配置', <ApiOutlined />, QMT_ITEMS)
      case 'ctp':
        return renderSection('期货 CTP 配置', <ApiOutlined />, CTP_ITEMS)
      default:
        return (
          <Card size="small" style={{ marginBottom: 16 }}>
            <Alert
              message="模拟盘模式"
              description="当前使用模拟盘（Paper Broker），不涉及真实券商账户。"
              type="info"
              showIcon
            />
            <Divider />
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <AntText type="secondary">功能说明：</AntText>
              </div>
              <div>• 模拟盘使用实时行情进行模拟交易</div>
              <div>• 不涉及真实资金，风险可控</div>
              <div>• 适合策略测试和验证</div>
              <div>• 成交规则与实盘一致</div>
            </Space>
          </Card>
        )
    }
  }

  return (
    <div style={{ maxWidth: 800 }}>
      <Card size="small" title={<Space><ApiOutlined /><AntText>券商通道</AntText></Space>} style={{ marginBottom: 16 }}>
        <Form layout="vertical">
          <Form.Item label={<AntText strong style={{ fontSize: 13 }}>选择券商</AntText>}>
            {renderField(BROKER_ITEMS[0], broker, (v) => onChange('trading.broker', v))}
          </Form.Item>
        </Form>
        
        {/* 连接状态指示 */}
        {broker !== 'paper' && (
          <>
            <Divider />
            <Space>
              <Tag icon={<DisconnectOutlined />} color="default">未连接</Tag>
              <Button size="small" icon={<CheckCircleOutlined />}>测试连接</Button>
            </Space>
          </>
        )}
      </Card>

      {renderBrokerConfig()}

      {/* 模拟测试说明 */}
      <Card size="small" title={<Space><ExperimentOutlined /><AntText>模拟测试</AntText></Space>} style={{ marginBottom: 16 }}>
        <Alert
          message="模拟账户验证"
          description="所有券商均支持使用模拟账户进行测试。在券商客户端中开通模拟交易权限后，使用模拟账号登录即可进行真实 API 调用测试。"
          type="info"
          showIcon
        />
      </Card>
    </div>
  )
}

function isVisible(item: SettingEntry, allValues: Record<string, unknown>): boolean {
  if (!item.when) return true
  return item.when.values.includes(allValues[item.when.field] as string)
}
