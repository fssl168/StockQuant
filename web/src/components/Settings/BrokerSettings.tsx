import { SettingsField } from './SettingsField';
import type { SettingEntry } from './types';
import { XCircle } from '@phosphor-icons/react';

interface BrokerSettingsProps {
  values: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}

const BROKER_ITEMS: Omit<SettingEntry, 'value' | 'onChange'>[] = [
  { key: 'trading.broker', defaultValue: 'paper', valueType: 'select', label: '券商通道', secret: false, options: [
    { value: 'paper', label: '模拟盘 (Paper)' },
    { value: 'xtp', label: '中泰证券 XTP' },
    { value: 'qmt', label: '国信 QMT' },
    { value: 'ctp', label: '期货 CTP' },
  ]},
];

const XTP_ITEMS: Omit<SettingEntry, 'value' | 'onChange'>[] = [
  { key: 'trading.xtp_ip', defaultValue: '127.0.0.1', valueType: 'string', label: 'XTP 交易服务器', description: '券商提供的交易服务器 IP' },
  { key: 'trading.xtp_port', defaultValue: 6002, valueType: 'number', label: 'XTP 端口', min: 1, max: 65535 },
  { key: 'trading.xtp_key', defaultValue: '', valueType: 'password', label: '软件 KEY', description: '券商提供的软件 KEY', secret: true },
  { key: 'trading.xtp_account', defaultValue: '', valueType: 'string', label: '资金账号' },
];

const QMT_ITEMS: Omit<SettingEntry, 'value' | 'onChange'>[] = [
  { key: 'trading.qmt_path', defaultValue: '', valueType: 'string', label: 'QMT 安装路径', description: '迅投 QMT 量化软件的安装目录' },
  { key: 'trading.qmt_account', defaultValue: '', valueType: 'string', label: 'QMT 资金账号' },
];

const CTP_ITEMS: Omit<SettingEntry, 'value' | 'onChange'>[] = [
  { key: 'trading.ctp_broker_id', defaultValue: '', valueType: 'string', label: '期货公司代码' },
  { key: 'trading.ctp_user', defaultValue: '', valueType: 'string', label: 'CTP 账号' },
  { key: 'trading.ctp_password', defaultValue: '', valueType: 'password', label: 'CTP 密码', secret: true },
  { key: 'trading.ctp_front', defaultValue: 'tcp://127.0.0.1:51201', valueType: 'string', label: 'CTP 交易服务器' },
];

function getVal(values: Record<string, unknown>, key: string, fallback?: unknown): unknown {
  const v = values[key];
  if (v === null || v === undefined) return fallback;
  if (typeof v === 'object') return fallback ?? '';
  return v;
}

function renderFields(items: Omit<SettingEntry, 'value' | 'onChange'>[], values: Record<string, unknown>, onChange: (key: string, value: unknown) => void) {
  return items.map((item) => (
    <SettingsField
      key={item.key}
      item={{ ...item, value: getVal(values, item.key, item.defaultValue) } as SettingEntry}
      value={getVal(values, item.key, item.defaultValue)}
      disabled={false}
      onChange={onChange}
    />
  ));
}

export default function BrokerSettings({ values, onChange }: BrokerSettingsProps) {
  const broker = String(values['trading.broker'] ?? 'paper');

  const renderBrokerConfig = () => {
    if (broker === 'xtp') {
      return renderFields(XTP_ITEMS, values, onChange);
    }
    if (broker === 'qmt') {
      return renderFields(QMT_ITEMS, values, onChange);
    }
    if (broker === 'ctp') {
      return renderFields(CTP_ITEMS, values, onChange);
    }
    // paper
    return (
      <div className="rounded-xl border border-white/8 bg-elevated/50 p-4">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <XCircle size={16} style={{ color: 'var(--color-info)' }} />
          <span style={{ fontSize: 13, fontWeight: 600 }}>模拟盘模式</span>
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: 0 }}>
          当前使用模拟盘（Paper Broker），不涉及真实券商账户。
        </p>
        <div style={{ marginTop: 12 }}>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>功能说明：</p>
          <ul style={{ fontSize: 12, color: 'var(--text-secondary)', listStyle: 'disc', paddingLeft: 20, margin: 0 }}>
            <li>模拟盘使用实时行情进行模拟交易</li>
            <li>不涉及真实资金，风险可控</li>
            <li>适合策略测试和验证</li>
            <li>成交规则与实盘一致</li>
          </ul>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-3">
      <SettingsField
        item={{ ...BROKER_ITEMS[0], value: getVal(values, 'trading.broker', 'paper') } as SettingEntry}
        value={getVal(values, 'trading.broker', 'paper')}
        disabled={false}
        onChange={onChange}
      />

      {/* 未连接状态提示 */}
      {broker !== 'paper' && (
        <div className="rounded-xl border border-white/8 bg-elevated/50 p-3" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <XCircle size={14} />
            未连接
          </span>
          <button className="btn-secondary !py-1.5 !px-3 !text-xs" disabled>
            测试连接
          </button>
        </div>
      )}

      {renderBrokerConfig()}
    </div>
  );
}
