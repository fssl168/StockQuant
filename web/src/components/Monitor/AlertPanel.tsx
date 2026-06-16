import { Card, Space, Switch, InputNumber, Typography } from 'antd'

const { Text } = Typography

interface AlertPanelProps {
  enabled: boolean
  threshold: number
  volumeEnabled: boolean
  volumeMultiplier: number
  onEnabledChange: (v: boolean) => void
  onThresholdChange: (v: number) => void
  onVolumeEnabledChange: (v: boolean) => void
  onVolumeMultiplierChange: (v: number) => void
}

export default function AlertPanel({
  enabled,
  threshold,
  volumeEnabled,
  volumeMultiplier: _volumeMultiplier,
  onEnabledChange,
  onThresholdChange,
  onVolumeEnabledChange,
  onVolumeMultiplierChange: _onVolumeMultiplierChange,
}: AlertPanelProps) {
  return (
    <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600 }}>告警规则</span>} style={{ marginTop: 12 }}>
      <Space direction="vertical" style={{ width: '100%' }} size={10}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text style={{ fontSize: 12 }}>涨跌幅超限提醒</Text>
          <Switch size="small" checked={enabled} onChange={onEnabledChange} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <Text style={{ fontSize: 12 }}>阈值</Text>
          <InputNumber size="small" min={0.1} max={10} step={0.1} value={threshold} onChange={(v) => onThresholdChange(v ?? 3)} suffix="%" style={{ width: 80 }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text style={{ fontSize: 12 }}>成交量异常检测</Text>
          <Switch size="small" checked={volumeEnabled} onChange={onVolumeEnabledChange} />
        </div>
      </Space>
    </Card>
  )
}
