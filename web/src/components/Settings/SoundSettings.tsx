import { useEffect, useState } from 'react';
import { SpeakerX, Warning, Lightning, Info, Bell } from '@phosphor-icons/react';
import { soundManager } from '@/utils/soundManager';

const STORAGE_KEY = 'stockquant-sound-config';

interface SoundConfig {
  muted: boolean;
  volume: number; // 0-100
}

function loadConfig(): SoundConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return { muted: false, volume: 80 };
}

function saveConfig(cfg: SoundConfig) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg));
  } catch { /* ignore */ }
}

const PRESET_SOUNDS = [
  { key: 'risk' as const, label: '高风险', icon: Warning, color: '#ef4444' },
  { key: 'opportunity' as const, label: '机会', icon: Lightning, color: '#10b981' },
  { key: 'info' as const, label: '信息', icon: Info, color: '#3b82f6' },
  { key: 'critical' as const, label: '紧急', icon: Bell, color: '#a855f7' },
] as const;

interface SoundSettingsProps {
  values?: Record<string, unknown>;
  onChange?: (key: string, value: unknown) => void;
}

export default function SoundSettings(_props: SoundSettingsProps) {
  const [config, setConfig] = useState<SoundConfig>(() => loadConfig());

  useEffect(() => {
    soundManager.setMute(config.muted);
    soundManager.setVolume(config.volume / 100);
  }, [config.muted, config.volume]);

  const update = (patch: Partial<SoundConfig>) => {
    const next = { ...config, ...patch };
    setConfig(next);
    saveConfig(next);
  };

  const handlePreview = (key: typeof PRESET_SOUNDS[number]['key']) => {
    try {
      soundManager.play(key);
    } catch (e) {
      // silently fail — Web Audio fallback
    }
  };

  return (
    <div className="space-y-3">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <SpeakerX size={16} weight="fill" style={{ color: 'var(--color-cyan)' }} />
        <span style={{ fontSize: 13, fontWeight: 600 }}>声音偏好</span>
      </div>

      {/* Muted toggle */}
      <div className="rounded-xl border border-white/8 bg-elevated/50 p-4" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: 12, fontWeight: 600 }}>静音</span>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '2px 0 0' }}>关闭所有音效提示</p>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            checked={config.muted}
            onChange={(e) => update({ muted: e.target.checked })}
          />
          <span className="text-sm text-secondary">{config.muted ? '已启用' : '未启用'}</span>
        </label>
      </div>

      {/* Volume */}
      <div className="rounded-xl border border-white/8 bg-elevated/50 p-4">
        <span style={{ fontSize: 12, fontWeight: 600 }}>音量</span>
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '2px 0 8px' }}>影响所有音效的播放音量</p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={config.volume}
            onChange={(e) => update({ volume: parseInt(e.target.value) })}
            disabled={config.muted}
            style={{ flex: 1, accentColor: 'var(--color-cyan)' }}
          />
          <span style={{
            fontSize: 12,
            fontFamily: 'var(--font-mono)',
            padding: '4px 10px',
            borderRadius: 6,
            background: 'rgba(0, 212, 255, 0.1)',
            border: '1px solid rgba(0, 212, 255, 0.3)',
            color: 'var(--color-cyan)',
          }}>{config.volume}%</span>
        </div>
      </div>

      {/* Preview sounds */}
      <div className="rounded-xl border border-white/8 bg-elevated/50 p-4">
        <span style={{ fontSize: 12, fontWeight: 600 }}>音效试听</span>
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '2px 0 8px' }}>点击播放对应级别音效</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {PRESET_SOUNDS.map((s) => (
            <button
              key={s.key}
              onClick={() => handlePreview(s.key)}
              disabled={config.muted}
              style={{
                padding: '6px 12px',
                borderRadius: 8,
                border: `1px solid ${s.color}40`,
                background: 'transparent',
                color: s.color,
                fontSize: 12,
                cursor: config.muted ? 'not-allowed' : 'pointer',
                opacity: config.muted ? 0.5 : 1,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <s.icon size={14} weight="fill" />
              {s.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
