/**
 * SoundSettings — 声音偏好设置
 *
 * 持久化：localStorage `stockquant-sound-config`
 * 运行时：直接调用 soundManager
 */
import { useEffect, useState } from 'react'
import { Card, Switch, Slider, Button, Space, Typography, Divider, Tag, message } from 'antd'
import { SoundOutlined, BellOutlined, ThunderboltOutlined, WarningOutlined, InfoCircleOutlined } from '@ant-design/icons'
import { soundManager } from '@/utils/soundManager'

const { Text, Paragraph } = Typography

interface SoundSettingsProps {
  /** 兼容 Settings 页面的统一 props（values/onChange），实际配置直接写入 localStorage */
  values?: Record<string, unknown>
  onChange?: (key: string, value: unknown) => void
}

interface SoundConfig {
  muted: boolean
  volume: number // 0-100
}

const STORAGE_KEY = 'stockquant-sound-config'

function loadConfig(): SoundConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return { muted: false, volume: 80 }
}

function saveConfig(cfg: SoundConfig) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg))
  } catch { /* ignore */ }
}

const PRESET_SOUNDS = [
  { key: 'risk', label: '高风险', icon: <WarningOutlined />, color: '#ef4444' },
  { key: 'opportunity', label: '机会', icon: <ThunderboltOutlined />, color: '#10b981' },
  { key: 'info', label: '信息', icon: <InfoCircleOutlined />, color: '#3b82f6' },
  { key: 'critical', label: '紧急', icon: <BellOutlined />, color: '#a855f7' },
] as const

export default function SoundSettings(_props: SoundSettingsProps) {
  const [config, setConfig] = useState<SoundConfig>(() => loadConfig())

  // 应用配置到 soundManager
  useEffect(() => {
    soundManager.setMute(config.muted)
    soundManager.setVolume(config.volume / 100)
  }, [config.muted, config.volume])

  const update = (patch: Partial<SoundConfig>) => {
    const next = { ...config, ...patch }
    setConfig(next)
    saveConfig(next)
  }

  const handlePreview = (key: typeof PRESET_SOUNDS[number]['key']) => {
    try {
      soundManager.play(key)
    } catch (e) {
      message.warning('播放失败：' + (e as Error).message)
    }
  }

  return (
    <Card size="small" title={<span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
      <SoundOutlined /> 声音偏好
    </span>}>
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Text style={{ fontSize: 12, fontWeight: 600 }}>静音</Text>
            <Paragraph type="secondary" style={{ fontSize: 11, margin: 0 }}>关闭所有音效提示</Paragraph>
          </div>
          <Switch checked={config.muted} onChange={(v) => update({ muted: v })} />
        </div>

        <Divider style={{ margin: '4px 0' }} />

        <div>
          <Text style={{ fontSize: 12, fontWeight: 600 }}>音量</Text>
          <Paragraph type="secondary" style={{ fontSize: 11, margin: 0 }}>影响所有音效的播放音量</Paragraph>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 8 }}>
            <Slider
              min={0}
              max={100}
              step={5}
              value={config.volume}
              onChange={(v) => update({ volume: v })}
              style={{ flex: 1 }}
              disabled={config.muted}
            />
            <Tag color="blue" style={{ fontFamily: 'var(--font-mono)', margin: 0 }}>{config.volume}%</Tag>
          </div>
        </div>

        <Divider style={{ margin: '4px 0' }} />

        <div>
          <Text style={{ fontSize: 12, fontWeight: 600 }}>音效试听</Text>
          <Paragraph type="secondary" style={{ fontSize: 11, margin: 0 }}>
            点击播放对应级别音效（MP3 缺失时自动降级为 Web Audio 蜂鸣）
          </Paragraph>
          <Space wrap size={8} style={{ marginTop: 8 }}>
            {PRESET_SOUNDS.map((s) => (
              <Button
                key={s.key}
                size="small"
                icon={s.icon}
                onClick={() => handlePreview(s.key)}
                disabled={config.muted}
                style={{ borderColor: s.color, color: s.color }}
              >
                {s.label}
              </Button>
            ))}
          </Space>
        </div>
      </Space>
    </Card>
  )
}
