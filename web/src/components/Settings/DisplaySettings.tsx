/**
 * DisplaySettings — 显示偏好设置
 *
 * 持久化：
 *  - 机构模式 / 信息降噪 / 低活跃时段：layoutStore (persist to localStorage `stockquant-layout`)
 *  - 关键价位闪烁开关：localStorage `stockquant-display-config`
 */
import { useEffect, useState } from 'react'
import { Card, Switch, InputNumber, Typography, Space, Divider, Tag, Tooltip } from 'antd'
import { DesktopOutlined, EyeOutlined, ThunderboltOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { useLayoutStore } from '@/stores/layoutStore'

const { Text, Paragraph } = Typography

interface DisplaySettingsProps {
  /** 兼容 Settings 页面的统一 props（实际配置直接写入 layoutStore/localStorage） */
  values?: Record<string, unknown>
  onChange?: (key: string, value: unknown) => void
}

interface DisplayConfig {
  keyLevelFlash: boolean
}

const STORAGE_KEY = 'stockquant-display-config'

function loadConfig(): DisplayConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return { keyLevelFlash: true }
}

function saveConfig(cfg: DisplayConfig) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg))
  } catch { /* ignore */ }
}

export default function DisplaySettings(_props: DisplaySettingsProps) {
  const institutionalEnabled = useLayoutStore((s) => s.institutionalEnabled)
  const toggleInstitutional = useLayoutStore((s) => s.toggleInstitutional)
  const infoFilter = useLayoutStore((s) => s.infoFilter)

  const [displayCfg, setDisplayCfg] = useState<DisplayConfig>(() => loadConfig())

  useEffect(() => {
    saveConfig(displayCfg)
  }, [displayCfg])

  /** 直接更新 infoFilter 子字段（layoutStore 没有提供统一 setter，用 setState 透传） */
  const patchInfoFilter = (patch: Partial<typeof infoFilter>) => {
    useLayoutStore.setState({
      infoFilter: { ...infoFilter, ...patch },
    })
  }

  return (
    <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
      <DesktopOutlined /> 显示偏好
    </span>}>
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        {/* 机构模式 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Text style={{ fontSize: 12, fontWeight: 600 }}>
              <EyeOutlined /> 机构模式默认开启
            </Text>
            <Paragraph type="secondary" style={{ fontSize: 11, margin: 0 }}>
              开启后 Trading/AppLayout 进入机构级三栏布局，副屏显示指数与快速下单
            </Paragraph>
          </div>
          <Switch checked={institutionalEnabled} onChange={toggleInstitutional} />
        </div>

        <Divider style={{ margin: '4px 0' }} />

        {/* 信息降噪总开关 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Text style={{ fontSize: 12, fontWeight: 600 }}>信息降噪</Text>
            <Paragraph type="secondary" style={{ fontSize: 11, margin: 0 }}>
              开启后仅显示核心面板（depth / tick / volume_ratio），其余面板隐藏
            </Paragraph>
          </div>
          <Switch
            checked={infoFilter.enabled}
            onChange={(v) => patchInfoFilter({ enabled: v })}
          />
        </div>

        <Divider style={{ margin: '4px 0' }} />

        {/* 低活跃时段折叠 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Text style={{ fontSize: 12, fontWeight: 600 }}>
              <ClockCircleOutlined /> 低活跃时段折叠
            </Text>
            <Paragraph type="secondary" style={{ fontSize: 11, margin: 0 }}>
              午休等低活跃时段自动折叠非核心面板
            </Paragraph>
          </div>
          <Switch
            checked={infoFilter.collapseOnLowActivity}
            onChange={(v) => patchInfoFilter({ collapseOnLowActivity: v })}
            disabled={!infoFilter.enabled}
          />
        </div>

        <div>
          <Text style={{ fontSize: 12, fontWeight: 600 }}>低活跃时段配置</Text>
          <Paragraph type="secondary" style={{ fontSize: 11, margin: 0 }}>24 小时制，0-23</Paragraph>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
            <InputNumber
              min={0}
              max={23}
              value={infoFilter.lowActivityHours.start}
              onChange={(v) => patchInfoFilter({
                lowActivityHours: { ...infoFilter.lowActivityHours, start: v ?? 0 },
              })}
              disabled={!infoFilter.enabled || !infoFilter.collapseOnLowActivity}
              size="small"
              style={{ width: 80 }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>时至</Text>
            <InputNumber
              min={0}
              max={23}
              value={infoFilter.lowActivityHours.end}
              onChange={(v) => patchInfoFilter({
                lowActivityHours: { ...infoFilter.lowActivityHours, end: v ?? 0 },
              })}
              disabled={!infoFilter.enabled || !infoFilter.collapseOnLowActivity}
              size="small"
              style={{ width: 80 }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>时</Text>
            <Tag color="blue" style={{ margin: 0 }}>
              当前：{infoFilter.lowActivityHours.start}-{infoFilter.lowActivityHours.end}
            </Tag>
          </div>
        </div>

        <Divider style={{ margin: '4px 0' }} />

        {/* 关键价位闪烁 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Text style={{ fontSize: 12, fontWeight: 600 }}>
              <ThunderboltOutlined /> 关键价位闪烁
            </Text>
            <Paragraph type="secondary" style={{ fontSize: 11, margin: 0 }}>
              价格突破支撑/阻力位时容器闪烁提示（RealtimeKline 读取此配置）
            </Paragraph>
          </div>
          <Tooltip title="关闭后 RealtimeKline 不再触发闪烁动画">
            <Switch
              checked={displayCfg.keyLevelFlash}
              onChange={(v) => setDisplayCfg({ ...displayCfg, keyLevelFlash: v })}
            />
          </Tooltip>
        </div>
      </Space>
    </Card>
  )
}
