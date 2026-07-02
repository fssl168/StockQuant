import { useEffect, useState } from 'react';
import { ShieldCheck, CurrencyCircleDollar, Percent, Fire } from '@phosphor-icons/react';

export interface RiskConfig {
  singleOrderRedLine: number;
  priceDeviationThreshold: number;
  emergencyCloseConfirm: boolean;
  tPlus1Check: boolean;
  priceLimitHint: boolean;
}

const STORAGE_KEY = 'stockquant-risk-config';

const DEFAULT_CONFIG: RiskConfig = {
  singleOrderRedLine: 500000,
  priceDeviationThreshold: 0.5,
  emergencyCloseConfirm: true,
  tPlus1Check: true,
  priceLimitHint: true,
};

export function loadRiskConfig(): RiskConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return { ...DEFAULT_CONFIG, ...parsed };
    }
  } catch { /* ignore */ }
  return DEFAULT_CONFIG;
}

function saveConfig(cfg: RiskConfig) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg));
  } catch { /* ignore */ }
}

interface RiskControlSettingsProps {
  values?: Record<string, unknown>;
  onChange?: (key: string, value: unknown) => void;
}

export default function RiskControlSettings(_props: RiskControlSettingsProps) {
  const [config, setConfig] = useState<RiskConfig>(() => loadRiskConfig());

  useEffect(() => {
    saveConfig(config);
  }, [config]);

  const update = (patch: Partial<RiskConfig>) => {
    setConfig((prev) => ({ ...prev, ...patch }));
  };

  const toggle = (key: keyof RiskConfig) => {
    if (typeof config[key] === 'boolean') {
      update({ [key]: !config[key] });
    }
  };

  return (
    <div className="space-y-3">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <ShieldCheck size={16} weight="fill" style={{ color: 'var(--color-cyan)' }} />
        <span style={{ fontSize: 13, fontWeight: 600 }}>风控参数</span>
      </div>

      {/* 单笔金额红线 */}
      <div className="rounded-xl border border-white/8 bg-elevated/50 p-4">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          <CurrencyCircleDollar size={14} />
          <span style={{ fontSize: 12, fontWeight: 600 }}>单笔金额红线</span>
        </div>
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '2px 0 8px' }}>
          单笔订单金额超过此阈值时弹窗二次确认（单位：元）
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            type="number"
            className="input-terminal"
            min={10000}
            max={100_000_000}
            step={50000}
            value={config.singleOrderRedLine}
            onChange={(e) => update({ singleOrderRedLine: parseInt(e.target.value) || 500000 })}
            style={{ width: 160 }}
          />
          <span style={{
            fontSize: 11,
            padding: '2px 8px',
            borderRadius: 4,
            background: 'rgba(255, 68, 102, 0.1)',
            border: '1px solid rgba(255, 68, 102, 0.3)',
            color: 'var(--color-danger)',
            fontFamily: 'var(--font-mono)',
          }}>
            ¥ {config.singleOrderRedLine.toLocaleString()}
          </span>
        </div>
      </div>

      {/* 价格偏差告警阈值 */}
      <div className="rounded-xl border border-white/8 bg-elevated/50 p-4">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          <Percent size={14} />
          <span style={{ fontSize: 12, fontWeight: 600 }}>价格偏差告警阈值</span>
        </div>
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '2px 0 8px' }}>
          委托价相对最新成交价偏差超过此阈值时告警（单位：%）
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            type="number"
            className="input-terminal"
            min={0.1}
            max={10}
            step={0.1}
            value={config.priceDeviationThreshold}
            onChange={(e) => update({ priceDeviationThreshold: parseFloat(e.target.value) || 0.5 })}
            style={{ width: 80 }}
          />
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>%</span>
          <span style={{
            fontSize: 11,
            padding: '2px 8px',
            borderRadius: 4,
            background: 'rgba(255, 170, 0, 0.1)',
            border: '1px solid rgba(255, 170, 0, 0.3)',
            color: 'var(--color-warning)',
            fontFamily: 'var(--font-mono)',
          }}>
            ±{config.priceDeviationThreshold.toFixed(1)}%
          </span>
        </div>
      </div>

      {/* 紧急平仓确认 */}
      <div className="rounded-xl border border-white/8 bg-elevated/50 p-4" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Fire size={14} />
            <span style={{ fontSize: 12, fontWeight: 600 }}>紧急平仓二次确认</span>
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '2px 0 0' }}>
            紧急平仓时弹窗要求二次确认，避免误操作
          </p>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            checked={config.emergencyCloseConfirm}
            onChange={() => toggle('emergencyCloseConfirm')}
          />
          <span className="text-sm text-secondary">{config.emergencyCloseConfirm ? '已启用' : '未启用'}</span>
        </label>
      </div>

      {/* T+1 校验 */}
      <div className="rounded-xl border border-white/8 bg-elevated/50 p-4" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: 12, fontWeight: 600 }}>T+1 校验</span>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '2px 0 0' }}>
            卖出当日买入的 A 股时显示限制提示（A 股 T+1 结算规则）
          </p>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            checked={config.tPlus1Check}
            onChange={() => toggle('tPlus1Check')}
          />
          <span className="text-sm text-secondary">{config.tPlus1Check ? '已启用' : '未启用'}</span>
        </label>
      </div>

      {/* 涨跌停价提示 */}
      <div className="rounded-xl border border-white/8 bg-elevated/50 p-4" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: 12, fontWeight: 600 }}>涨跌停价提示</span>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '2px 0 0' }}>
            委托价接近涨跌停板（±10%）时高亮提示
          </p>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            checked={config.priceLimitHint}
            onChange={() => toggle('priceLimitHint')}
          />
          <span className="text-sm text-secondary">{config.priceLimitHint ? '已启用' : '未启用'}</span>
        </label>
      </div>
    </div>
  );
}
