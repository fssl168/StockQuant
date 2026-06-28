/**
 * RiskControlSettings — 风控参数设置
 *
 * 持久化：localStorage `stockquant-risk-config`
 * 消费方：InstitutionalOrderPanel 通过 loadRiskConfig() 读取
 */
import { useEffect, useState } from 'react'
import { Card, Switch, InputNumber, Typography, Space, Divider, Tag, Tooltip } from 'antd'
import { SafetyCertificateOutlined, DollarOutlined, PercentageOutlined, AlertOutlined } from '@ant-design/icons'

const { Text, Paragraph } = Typography

interface RiskControlSettingsProps {
  /** 兼容 Settings 页面的统一 props（实际配置直接写入 localStorage） */
  values?: Record<string, unknown>
  onChange?: (key: string, value: unknown) => void
}

export interface RiskConfig {
  /** 单笔金额红线（元） */
  singleOrderRedLine: number
  /** 价格偏差告警阈值（%） */
  priceDeviationThreshold: number
  /** 紧急平仓确认开关 */
  emergencyCloseConfirm: boolean
  /** T+1 校验开关 */
  tPlus1Check: boolean
  /** 涨跌停价提示开关 */
  priceLimitHint: boolean
}

const STORAGE_KEY = 'stockquant-risk-config'

const DEFAULT_CONFIG: RiskConfig = {
  singleOrderRedLine: 500000,
  priceDeviationThreshold: 0.5,
  emergencyCloseConfirm: true,
  tPlus1Check: true,
  priceLimitHint: true,
}

/** 供 InstitutionalOrderPanel 等外部读取的入口 */
export function loadRiskConfig(): RiskConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      return { ...DEFAULT_CONFIG, ...parsed }
    }
  } catch { /* ignore */ }
  return DEFAULT_CONFIG
}

function saveConfig(cfg: RiskConfig) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg))
  } catch { /* ignore */ }
}

export default function RiskControlSettings(_props: RiskControlSettingsProps) {
  const [config, setConfig] = useState<RiskConfig>(() => loadRiskConfig())

  useEffect(() => {
    saveConfig(config)
  }, [config])

  const update = (patch: Partial<RiskConfig>) => {
    setConfig((prev) => ({ ...prev, ...patch }))
  }

  return (
    <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
      <SafetyCertificateOutlined /> 风控参数
    </span>}>
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        {/* 单笔金额红线 */}
        <div>
          <Text style={{ fontSize: 12, fontWeight: 600 }}>
            <DollarOutlined /> 单笔金额红线
          </Text>
          <Paragraph type="secondary" style={{ fontSize: 11, margin: 0 }}>
            单笔订单金额超过此阈值时弹窗二次确认（单位：元）
          </Paragraph>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
            <InputNumber
              min={10000}
              max={100_000_000}
              step={50000}
              value={config.singleOrderRedLine}
              onChange={(v) => update({ singleOrderRedLine: v ?? 500000 })}
              size="small"
              style={{ width: 180 }}
              formatter={(value) => `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
              parser={(value) => Number(value?.replace(/[^\d]/g, '') || 0)}
            />
            <Tag color="red">¥ {config.singleOrderRedLine.toLocaleString()}</Tag>
          </div>
        </div>

        <Divider style={{ margin: '4px 0' }} />

        {/* 价格偏差告警阈值 */}
        <div>
          <Text style={{ fontSize: 12, fontWeight: 600 }}>
            <PercentageOutlined /> 价格偏差告警阈值
          </Text>
          <Paragraph type="secondary" style={{ fontSize: 11, margin: 0 }}>
            委托价相对最新成交价偏差超过此阈值时告警（单位：%）
          </Paragraph>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
            <InputNumber
              min={0.1}
              max={10}
              step={0.1}
              value={config.priceDeviationThreshold}
              onChange={(v) => update({ priceDeviationThreshold: v ?? 0.5 })}
              size="small"
              style={{ width: 100 }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>%</Text>
            <Tag color="orange">±{config.priceDeviationThreshold.toFixed(1)}%</Tag>
          </div>
        </div>

        <Divider style={{ margin: '4px 0' }} />

        {/* 紧急平仓确认 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Text style={{ fontSize: 12, fontWeight: 600 }}>
              <AlertOutlined /> 紧急平仓二次确认
            </Text>
            <Paragraph type="secondary" style={{ fontSize: 11, margin: 0 }}>
              紧急平仓时弹窗要求二次确认，避免误操作
            </Paragraph>
          </div>
          <Tooltip title="建议保持开启">
            <Switch
              checked={config.emergencyCloseConfirm}
              onChange={(v) => update({ emergencyCloseConfirm: v })}
            />
          </Tooltip>
        </div>

        <Divider style={{ margin: '4px 0' }} />

        {/* T+1 校验 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Text style={{ fontSize: 12, fontWeight: 600 }}>T+1 校验</Text>
            <Paragraph type="secondary" style={{ fontSize: 11, margin: 0 }}>
              卖出当日买入的 A 股时显示限制提示（A 股 T+1 结算规则）
            </Paragraph>
          </div>
          <Switch
            checked={config.tPlus1Check}
            onChange={(v) => update({ tPlus1Check: v })}
          />
        </div>

        <Divider style={{ margin: '4px 0' }} />

        {/* 涨跌停价提示 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Text style={{ fontSize: 12, fontWeight: 600 }}>涨跌停价提示</Text>
            <Paragraph type="secondary" style={{ fontSize: 11, margin: 0 }}>
              委托价接近涨跌停板（±10%）时高亮提示
            </Paragraph>
          </div>
          <Switch
            checked={config.priceLimitHint}
            onChange={(v) => update({ priceLimitHint: v })}
          />
        </div>
      </Space>
    </Card>
  )
}
