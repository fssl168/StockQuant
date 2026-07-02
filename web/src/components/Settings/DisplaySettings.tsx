import { useEffect, useState } from 'react';
import { Desktop, Eye, Clock, Lightning } from '@phosphor-icons/react';
import { useLayoutStore } from '@/stores/layoutStore';

const STORAGE_KEY = 'stockquant-display-config';

interface DisplayConfig {
  keyLevelFlash: boolean;
}

function loadConfig(): DisplayConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return { keyLevelFlash: true };
}

function saveConfig(cfg: DisplayConfig) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg));
  } catch { /* ignore */ }
}

interface DisplaySettingsProps {
  values?: Record<string, unknown>;
  onChange?: (key: string, value: unknown) => void;
}

export default function DisplaySettings(_props: DisplaySettingsProps) {
  const institutionalEnabled = useLayoutStore((s) => s.institutionalEnabled);
  const toggleInstitutional = useLayoutStore((s) => s.toggleInstitutional);
  const infoFilter = useLayoutStore((s) => s.infoFilter);

  const [displayCfg, setDisplayCfg] = useState<DisplayConfig>(() => loadConfig());

  useEffect(() => {
    saveConfig(displayCfg);
  }, [displayCfg]);

  const patchInfoFilter = (patch: Partial<typeof infoFilter>) => {
    useLayoutStore.setState({
      infoFilter: { ...infoFilter, ...patch },
    });
  };

  const toggle = (key: keyof DisplayConfig) => {
    setDisplayCfg((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="space-y-3">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <Desktop size={16} weight="fill" style={{ color: 'var(--color-cyan)' }} />
        <span style={{ fontSize: 13, fontWeight: 600 }}>显示偏好</span>
      </div>

      {/* 机构模式 */}
      <div className="rounded-xl border border-white/8 bg-elevated/50 p-4" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Eye size={14} />
            <span style={{ fontSize: 12, fontWeight: 600 }}>机构模式</span>
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '2px 0 0' }}>
            进入机构级三栏布局，副屏显示指数与快速下单
          </p>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            checked={institutionalEnabled}
            onChange={toggleInstitutional}
          />
          <span className="text-sm text-secondary">{institutionalEnabled ? '已启用' : '未启用'}</span>
        </label>
      </div>

      {/* 信息降噪 */}
      <div className="rounded-xl border border-white/8 bg-elevated/50 p-4" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: 12, fontWeight: 600 }}>信息降噪</span>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '2px 0 0' }}>
            仅显示核心面板（depth / tick / volume_ratio），其余面板隐藏
          </p>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            checked={infoFilter.enabled}
            onChange={(e) => patchInfoFilter({ enabled: e.target.checked })}
          />
          <span className="text-sm text-secondary">{infoFilter.enabled ? '已启用' : '未启用'}</span>
        </label>
      </div>

      {/* 低活跃时段折叠 */}
      <div className="rounded-xl border border-white/8 bg-elevated/50 p-4">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Clock size={14} />
              <span style={{ fontSize: 12, fontWeight: 600 }}>低活跃时段折叠</span>
            </div>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '2px 0 0' }}>
              午休等低活跃时段自动折叠非核心面板
            </p>
          </div>
          <label className="inline-flex cursor-pointer items-center gap-3">
            <input
              type="checkbox"
              checked={infoFilter.collapseOnLowActivity}
              onChange={(e) => patchInfoFilter({ collapseOnLowActivity: e.target.checked })}
              disabled={!infoFilter.enabled}
            />
            <span className="text-sm text-secondary">{infoFilter.collapseOnLowActivity ? '已启用' : '未启用'}</span>
          </label>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            type="number"
            className="input-terminal"
            min={0}
            max={23}
            value={infoFilter.lowActivityHours.start}
            onChange={(e) => patchInfoFilter({ lowActivityHours: { ...infoFilter.lowActivityHours, start: parseInt(e.target.value) || 0 } })}
            disabled={!infoFilter.enabled || !infoFilter.collapseOnLowActivity}
            style={{ width: 72 }}
          />
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>时至</span>
          <input
            type="number"
            className="input-terminal"
            min={0}
            max={23}
            value={infoFilter.lowActivityHours.end}
            onChange={(e) => patchInfoFilter({ lowActivityHours: { ...infoFilter.lowActivityHours, end: parseInt(e.target.value) || 0 } })}
            disabled={!infoFilter.enabled || !infoFilter.collapseOnLowActivity}
            style={{ width: 72 }}
          />
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>时</span>
          <span style={{
            fontSize: 11,
            padding: '2px 8px',
            borderRadius: 4,
            background: 'rgba(0, 212, 255, 0.1)',
            border: '1px solid rgba(0, 212, 255, 0.3)',
            color: 'var(--color-cyan)',
            fontFamily: 'var(--font-mono)',
          }}>
            {infoFilter.lowActivityHours.start}-{infoFilter.lowActivityHours.end}
          </span>
        </div>
      </div>

      {/* 关键价位闪烁 */}
      <div className="rounded-xl border border-white/8 bg-elevated/50 p-4" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Lightning size={14} />
            <span style={{ fontSize: 12, fontWeight: 600 }}>关键价位闪烁</span>
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '2px 0 0' }}>
            价格突破支撑/阻力位时容器闪烁提示
          </p>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            checked={displayCfg.keyLevelFlash}
            onChange={() => toggle('keyLevelFlash')}
          />
          <span className="text-sm text-secondary">{displayCfg.keyLevelFlash ? '已启用' : '未启用'}</span>
        </label>
      </div>
    </div>
  );
}
