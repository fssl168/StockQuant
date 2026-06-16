import { Typography, Tag } from 'antd'

const { Text } = Typography

interface StockTickerProps {
  symbol: string
  name: string
  price: number
  change: number
  volume?: number
}

export default function StockTicker({ symbol, name, price, change, volume }: StockTickerProps) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '8px 12px',
      borderRadius: 6,
      background: 'var(--color-bg-elevated)',
      border: '1px solid var(--color-border-default)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Text style={{ fontFamily: 'var(--font-mono)', fontWeight: 500, fontSize: 12 }}>{symbol}</Text>
        <Text style={{ color: 'var(--color-text-secondary)', fontSize: 12 }}>{name}</Text>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Text style={{
          fontFamily: 'var(--font-mono)',
          fontWeight: 500,
          color: change >= 0 ? 'var(--color-success)' : 'var(--color-danger)',
          fontSize: 13,
        }}>
          {price.toFixed(2)}
        </Text>
        <Tag color={change >= 0 ? 'green' : 'red'} style={{ fontFamily: 'var(--font-mono)', fontSize: 11, margin: 0 }}>
          {change >= 0 ? '+' : ''}{change.toFixed(2)}%
        </Tag>
        {volume !== undefined && (
          <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-text-tertiary)' }}>
            {volume >= 10000 ? `${(volume / 10000).toFixed(0)}万` : volume.toLocaleString()}
          </Text>
        )}
      </div>
    </div>
  )
}
