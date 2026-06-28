/**
 * Institutional-grade order panel for A-share trading.
 *
 * Features:
 * - Mode switch: institutional / retail
 * - Symbol input with auto-complete from watchlist
 * - Side toggle (BUY / SELL)
 * - Quantity input with A-share lot-size validation
 * - Price input with limit price hints (涨停 / 跌停)
 * - Price deviation check (> 0.5% from last trade → confirmation modal)
 * - Max order value check (configurable, default 500k)
 * - Estimated fees (commission + stamp tax + transfer fee)
 * - A-share rule warnings (T+1, limit price range)
 * - Full validation before submission
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Card,
  InputNumber,
  Radio,
  Select,
  Typography,
  Button,
  Space,
  Divider,
  Tag,
  Alert,
  Modal,
  message,
  Segmented,
  Tooltip,
  Badge,
} from 'antd'
import {
  ShoppingCart,
  Warning,
  ArrowUpRight,
  ArrowDownLeft,
  Info,
  Lightning,
  TrendUp,
  TrendDown,
} from '@phosphor-icons/react'
import {
  validateOrder,
  validateQuantity,
  validatePrice,
  getLimitPrice,
  checkTPlus1,
  type ValidationResult,
} from './ashareValidator'
import { loadRiskConfig } from '@/components/Settings/RiskControlSettings'
import type { OrderSide, OrderType, Position } from '@/types'

const { Text } = Typography

// ---- symbol autocomplete list (can be wired to API later) ----
const SYMBOL_MAP: Record<string, string> = {
  sh600519: '贵州茅台',
  sh601318: '中国平安',
  sz000858: '五粮液',
  sz000001: '平安银行',
  sh600036: '招商银行',
  sz300750: '宁德时代',
  sh688981: '中芯国际',
  sh601012: '隆基绿能',
}

const SYMBOL_LIST = Object.entries(SYMBOL_MAP)
  .map(([symbol, name]) => ({ label: `${symbol}  ${name}`, value: symbol }))

// ---- constants ----
const PRICE_DEVIATION_PCT = 0.5

interface InstitutionalOrderPanelProps {
  /** Override default placeOrder callback */
  placeOrder?: (order: {
    symbol: string
    side: OrderSide
    type: OrderType
    price: number
    quantity: number
  }) => Promise<{ id: string }>

  /** Max order value before confirmation; 0 to disable
   *  未传入时从 localStorage 读取 RiskControlSettings 配置
   */
  maxOrderValue?: number

  /** Last traded price for deviation check
   *  未传入时从 positions 中根据 symbol 查找
   */
  lastTradePrice?: number

  /** Position for T+1 check
   *  未传入时从 positions 中根据 symbol 查找
   */
  position?: { shares: number; buyDate?: string }

  /** 持仓列表，用于根据 symbol 自动查找 lastTradePrice 和 position */
  positions?: Position[]
}

export default function InstitutionalOrderPanel({
  placeOrder: externalPlaceOrder,
  maxOrderValue,
  lastTradePrice: externalLastTradePrice,
  position: externalPosition,
  positions = [],
}: InstitutionalOrderPanelProps) {
  // --- state ---
  const [mode, setMode] = useState<'institutional' | 'retail'>('retail')
  const [symbol, setSymbol] = useState('')
  const [side, setSide] = useState<OrderSide>('BUY')
  const [orderType, setOrderType] = useState<OrderType>('LIMIT')
  const [price, setPrice] = useState<number | null>(null)
  const [quantity, setQuantity] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // 读取风控配置：若外部未传 maxOrderValue，从 localStorage 读取
  const riskConfig = useMemo(() => loadRiskConfig(), [])
  const effectiveMaxOrderValue = maxOrderValue ?? riskConfig.singleOrderRedLine

  // 根据 symbol 从 positions 中查找持仓和最新价
  const matchedPosition = useMemo(() => {
    if (externalPosition) return externalPosition
    if (!positions || positions.length === 0) return { shares: 0 }
    const found = positions.find((p) => p.symbol === symbol)
    if (!found) return { shares: 0 }
    return { shares: found.shares, buyDate: undefined }
  }, [externalPosition, positions, symbol])

  const lastTradePrice = useMemo(() => {
    if (externalLastTradePrice != null) return externalLastTradePrice
    if (!positions || positions.length === 0 || !symbol) return undefined
    const found = positions.find((p) => p.symbol === symbol)
    return found?.price
  }, [externalLastTradePrice, positions, symbol])

  const position = matchedPosition

  // Validation warnings / errors
  const [orderResult, setOrderResult] = useState<ValidationResult>({
    valid: true,
    errors: [],
    warnings: [],
  })
  const [qtyResult, setQtyResult] = useState<ValidationResult>({
    valid: true,
    errors: [],
    warnings: [],
  })
  const [priceResult, setPriceResult] = useState<ValidationResult>({
    valid: true,
    errors: [],
    warnings: [],
  })
  const tPlus1Result = useMemo<ValidationResult>(() => {
    if (side !== 'SELL' || !symbol || !position || position.shares <= 0) {
      return { valid: true, errors: [], warnings: [] }
    }
    return checkTPlus1(symbol, side, position)
  }, [symbol, side, position])

  // Modals
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deviationModalOpen, setDeviationModalOpen] = useState(false)
  const [maxValueModalOpen, setMaxValueModalOpen] = useState(false)

  // Auto-complete filter
  const [searchText, setSearchText] = useState('')

  // --- derived values ---
  const orderValue = useMemo(
    () => (price || 0) * (quantity || 0),
    [price, quantity],
  )

  const limitPrices = useMemo(() => {
    if (!symbol || !lastTradePrice || lastTradePrice <= 0) return null
    return getLimitPrice(symbol, lastTradePrice)
  }, [symbol, lastTradePrice])

  const fees = useMemo(() => {
    const amount = orderValue
    const commission = Math.max(amount * 0.00025, 5)
    const stampTax = side === 'SELL' ? amount * 0.0005 : 0
    const transferFee = amount * 0.00001
    return { commission, stampTax, transferFee, total: commission + stampTax + transferFee }
  }, [orderValue, side])

  const deviationPct = useMemo(() => {
    if (!price || !lastTradePrice || lastTradePrice <= 0) return 0
    return Math.abs(price - lastTradePrice) / lastTradePrice * 100
  }, [price, lastTradePrice])

  // --- revalidate on input change ---
  const runValidations = useCallback(() => {
    if (!symbol || !quantity || quantity <= 0) {
      setOrderResult({ valid: true, errors: [], warnings: [] })
      setQtyResult({ valid: true, errors: [], warnings: [] })
      setPriceResult({ valid: true, errors: [], warnings: [] })
      return
    }

    const oResult = validateOrder({
      symbol,
      side,
      price: price || 0,
      quantity,
    })
    setOrderResult(oResult)

    const qResult = validateQuantity(symbol, quantity)
    setQtyResult(qResult)

    if (price && price > 0 && lastTradePrice && lastTradePrice > 0) {
      const pResult = validatePrice(symbol, price, lastTradePrice)
      setPriceResult(pResult)
    }
  }, [symbol, side, price, quantity, lastTradePrice])

  useEffect(() => {
    runValidations()
  }, [runValidations])

  // --- autocomplete handler ---
  const filteredSymbols = useMemo(() => {
    if (!searchText.trim()) return SYMBOL_LIST
    const lower = searchText.toLowerCase()
    return SYMBOL_LIST.filter(
      (s) => s.value.includes(lower) || s.label.includes(lower),
    )
  }, [searchText])

  // --- submission ---
  const handleSubmit = async () => {
    // Final gate: all validations must pass
    if (!orderResult.valid || !qtyResult.valid || !priceResult.valid) {
      message.error('请修正所有错误后再提交')
      return
    }

    const value = price! * quantity!

    // Max order value gate
    if (effectiveMaxOrderValue > 0 && value > effectiveMaxOrderValue) {
      setMaxValueModalOpen(true)
      return
    }

    // Price deviation gate
    if (
      lastTradePrice &&
      lastTradePrice > 0 &&
      deviationPct > PRICE_DEVIATION_PCT
    ) {
      setDeviationModalOpen(true)
      return
    }

    setConfirmOpen(true)
  }

  const handleConfirmSubmit = async () => {
    setConfirmOpen(false)
    setSubmitting(true)
    try {
      const fn = externalPlaceOrder ?? (() => Promise.reject(new Error('未提供 placeOrder 回调')))
      await fn({
        symbol,
        side,
        type: orderType,
        price: price ?? 0,
        quantity: quantity!,
      })
      message.success('下单成功')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '下单失败'
      message.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  // --- build summary for confirm modal ---
  const confirmLines = useMemo(() => {
    const lines: { label: string; value: string }[] = [
      { label: '股票', value: symbol || '--' },
      { label: '方向', value: side === 'BUY' ? '买入' : '卖出' },
      { label: '类型', value: orderType === 'MARKET' ? '市价' : orderType === 'LIMIT' ? '限价' : '止损' },
      {
        label: '价格',
        value: orderType === 'MARKET' ? '市价' : `¥${(price ?? 0).toFixed(2)}`,
      },
      { label: '数量', value: `${quantity ?? 0} 股` },
      { label: '预估金额', value: `¥${orderValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}` },
    ]

    if (limitPrices) {
      lines.push(
        {
          label: '涨停价',
          value: `¥${limitPrices.upper.toFixed(2)}`,
        },
        {
          label: '跌停价',
          value: `¥${limitPrices.lower.toFixed(2)}`,
        },
      )
    }

    lines.push(
      { label: '佣金', value: `¥${fees.commission.toFixed(2)}` },
      { label: '印花税', value: `¥${fees.stampTax.toFixed(2)}` },
      { label: '过户费', value: `¥${fees.transferFee.toFixed(2)}` },
      { label: '总费用', value: `¥${fees.total.toFixed(2)}` },
    )

    return lines
  }, [
    symbol,
    side,
    orderType,
    price,
    quantity,
    orderValue,
    limitPrices,
    fees,
  ])

  return (
    <div>
      <Card
        size="small"
        title={
          <span
            style={{
              fontSize: 12,
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <ShoppingCart size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />
            下单
            {mode === 'institutional' && (
              <Badge count="机构" size="small" style={{ marginLeft: 8 }} />
            )}
          </span>
        }
        style={{ marginBottom: 12 }}
      >
        <Space direction="vertical" style={{ width: '100%' }} size={10}>
          {/* Mode switch */}
          <Segmented
            size="small"
            value={mode}
            onChange={(v) => setMode(v as 'institutional' | 'retail')}
            options={[
              { label: '机构', value: 'institutional' },
              { label: '散户', value: 'retail' },
            ]}
            style={{ width: '100%' }}
          />

          {/* Symbol with auto-complete */}
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>股票代码</Text>
            <Select
              value={symbol || undefined}
              onChange={(v) => {
                setSymbol(v)
                setSearchText('')
                // Auto-fill last trade price if available
              }}
              size="small"
              style={{ width: '100%', marginTop: 4 }}
              showSearch
              filterOption={false}
              onFocus={() => setSearchText(symbol)}
              onBlur={() => setTimeout(() => setSearchText(''), 200)}
              placeholder="输入代码或名称搜索"
              options={filteredSymbols}
              suffixIcon={<Lightning size={14} />}
              tokenSeparators={[',']}
            />
          </div>

          {/* Side + Type row */}
          <Space size={8} style={{ width: '100%', justifyContent: 'space-between' }}>
            <div style={{ flex: 1 }}>
              <Text type="secondary" style={{ fontSize: 11 }}>方向</Text>
              <Radio.Group
                value={side}
                onChange={(e) => setSide(e.target.value)}
                optionType="button"
                buttonStyle="solid"
                size="small"
                style={{ width: '100%', marginTop: 4 }}
                options={[
                  { label: '买入', value: 'BUY' },
                  { label: '卖出', value: 'SELL' },
                ]}
              />
            </div>
            <div style={{ flex: 1 }}>
              <Text type="secondary" style={{ fontSize: 11 }}>类型</Text>
              <Select
                value={orderType}
                onChange={(v) => setOrderType(v as OrderType)}
                size="small"
                style={{ width: '100%', marginTop: 4 }}
                options={[
                  { label: '市价', value: 'MARKET' },
                  { label: '限价', value: 'LIMIT' },
                  { label: '止损', value: 'STOP' },
                ]}
              />
            </div>
          </Space>

          {/* Price with limit hints */}
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>
              价格 {orderType === 'MARKET' ? '(市价)' : ''}
            </Text>
            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              <InputNumber
                value={price}
                onChange={(v) => setPrice(v ?? null)}
                disabled={orderType === 'MARKET'}
                size="small"
                min={0}
                step={0.01}
                precision={2}
                style={{ flex: 1 }}
                formatter={(v) => `¥ ${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
              />
              {limitPrices && orderType !== 'MARKET' && (
                <Space direction="vertical" size={0} style={{ width: 110 }}>
                  <Tooltip title="涨停价">
                    <Tag color="red" style={{ fontSize: 9, margin: 0, textAlign: 'center' }}>
                      <TrendUp size={10} /> {limitPrices.upper.toFixed(2)}
                    </Tag>
                  </Tooltip>
                  <Tooltip title="跌停价">
                    <Tag color="green" style={{ fontSize: 9, margin: 0, textAlign: 'center' }}>
                      <TrendDown size={10} /> {limitPrices.lower.toFixed(2)}
                    </Tag>
                  </Tooltip>
                </Space>
              )}
            </div>
          </div>

          {/* Quantity with lot-size validation */}
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>数量（股）</Text>
            <InputNumber
              value={quantity}
              onChange={(v) => setQuantity(v ?? null)}
              size="small"
              min={10}
              step={100}
              style={{ width: '100%', marginTop: 4 }}
              formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
            />
            {qtyResult.warnings.length > 0 && (
              <Text type="secondary" style={{ fontSize: 10 }}>
                A 股最小单位 100 股
              </Text>
            )}
          </div>

          {/* Estimated amount */}
          <div
            style={{
              padding: '8px 12px',
              borderRadius: 6,
              background: 'var(--color-bg-elevated)',
              border: '1px solid var(--color-border-default)',
              display: 'flex',
              justifyContent: 'space-between',
            }}
          >
            <Text style={{ fontSize: 12 }}>预估金额</Text>
            <Text
              strong
              style={{
                fontFamily: 'var(--font-mono)',
                color: side === 'BUY' ? '#ef4444' : '#10b981',
              }}
            >
              ¥{orderValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </Text>
          </div>

          {/* Validation errors */}
          {orderResult.errors.length > 0 && (
            <Alert
              type="error"
              showIcon
              message={orderResult.errors.join('；')}
              style={{ fontSize: 11 }}
            />
          )}
          {qtyResult.errors.length > 0 && (
            <Alert
              type="error"
              showIcon
              message={qtyResult.errors.join('；')}
              style={{ fontSize: 11 }}
            />
          )}
          {priceResult.errors.length > 0 && (
            <Alert
              type="error"
              showIcon
              message={priceResult.errors.join('；')}
              style={{ fontSize: 11 }}
            />
          )}

          {/* Warnings */}
          {orderResult.warnings.length > 0 && (
            <Alert
              type="warning"
              showIcon
              message={`警告: ${orderResult.warnings.join('；')}`}
              style={{ fontSize: 11 }}
            />
          )}
          {tPlus1Result.errors.length > 0 && (
            <Alert
              type="error"
              showIcon
              icon={<Warning />}
              message={tPlus1Result.errors.join('；')}
              description="T+1 规则：今日买入的股份今日不可卖出"
              style={{ fontSize: 11 }}
            />
          )}
          {tPlus1Result.warnings.length > 0 && (
            <Alert
              type="info"
              showIcon
              icon={<Info />}
              message={tPlus1Result.warnings.join('；')}
              style={{ fontSize: 11 }}
            />
          )}

          {/* Submit button */}
          <Button
            type="primary"
            block
            size="large"
            icon={
              side === 'BUY' ? (
                <ArrowUpRight weight="bold" size={16} />
              ) : (
                <ArrowDownLeft weight="bold" size={16} />
              )
            }
            loading={submitting}
            disabled={!orderResult.valid || !qtyResult.valid || !priceResult.valid}
            onClick={handleSubmit}
            style={{ fontWeight: 600 }}
          >
            {side === 'BUY' ? '买入' : '卖出'} {symbol || '--'}
          </Button>
        </Space>
      </Card>

      {/* --- Fee estimate (always visible in institutional mode) --- */}
      {mode === 'institutional' && (fees.commission > 0 || fees.stampTax > 0) && (
        <Card
          size="small"
          title={
            <span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
              <TrendUp size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />
              费用明细
            </span>
          }
          style={{ marginBottom: 12 }}
        >
          <Space direction="vertical" style={{ width: '100%' }} size={4}>
            <div key="commission" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                佣金（万 2.5，最低 5 元）
              </Text>
              <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                ¥{fees.commission.toFixed(2)}
              </Text>
            </div>
            <div key="stamp" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                印花税（卖出千 1）
              </Text>
              <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                ¥{fees.stampTax.toFixed(2)}
              </Text>
            </div>
            <div key="transfer" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                过户费（十万 1）
              </Text>
              <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                ¥{fees.transferFee.toFixed(2)}
              </Text>
            </div>
            <Divider style={{ margin: '4px 0' }} />
            <div key="total" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <Text strong style={{ fontSize: 12 }}>总费用</Text>
              <Text strong style={{ fontFamily: 'var(--font-mono)', color: '#f59e0b', fontSize: 12 }}>
                ¥{fees.total.toFixed(2)}
              </Text>
            </div>
          </Space>
        </Card>
      )}

      {/* --- Confirm Modal --- */}
      <Modal
        title="确认下单"
        open={confirmOpen}
        onOk={handleConfirmSubmit}
        onCancel={() => setConfirmOpen(false)}
        okText="确认下单"
        cancelText="取消"
        confirmLoading={submitting}
        okType={side === 'BUY' ? 'primary' : 'danger'}
      >
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          {confirmLines.map((line) => (
            <div key={line.label} style={{ display: 'flex', justifyContent: 'space-between' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>{line.label}</Text>
              <Text
                strong
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                  color: line.label === '预估金额'
                    ? side === 'BUY'
                      ? '#ef4444'
                      : '#10b981'
                    : undefined,
                }}
              >
                {line.value}
              </Text>
            </div>
          ))}
          <Divider style={{ margin: '4px 0' }} />
          <div
            style={{
              fontSize: 11,
              color: 'var(--color-text-secondary)',
              padding: '6px 10px',
              borderRadius: 6,
              background: 'rgba(139,92,246,0.06)',
              border: '1px solid rgba(139,92,246,0.12)',
            }}
          >
            <div>A 股规则：T+1 交易，买入当日不可卖出</div>
            <div>最小交易单位：100 股</div>
          </div>
        </Space>
      </Modal>

      {/* --- Price deviation confirmation --- */}
      <Modal
        title={
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Warning size={16} color="#f59e0b" weight="fill" />
            价格偏离警告
          </span>
        }
        open={deviationModalOpen}
        onCancel={() => setDeviationModalOpen(false)}
        onOk={handleConfirmSubmit}
        okText="确认提交"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <Alert
            type="warning"
            showIcon
            message={`委托价格偏离昨成交 > ${PRICE_DEVIATION_PCT}%`}
            description={
              <div style={{ fontSize: 12 }}>
                <div>昨成交: ¥{lastTradePrice?.toFixed(2)}</div>
                <div>委托: ¥{price?.toFixed(2)} (偏离 {deviationPct.toFixed(2)}%)</div>
                <div style={{ marginTop: 4, color: '#f59e0b' }}>
                  请确认价格设置是否正确，避免错误成交。
                </div>
              </div>
            }
            style={{ fontSize: 12 }}
          />
        </Space>
      </Modal>

      {/* --- Max order value confirmation --- */}
      <Modal
        title={
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Warning size={16} color="#f59e0b" weight="fill" />
            订单金额超限
          </span>
        }
        open={maxValueModalOpen}
        onCancel={() => setMaxValueModalOpen(false)}
        onOk={handleConfirmSubmit}
        okText="确认提交"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <Alert
            type="warning"
            showIcon
            message={`订单金额 ¥${orderValue.toLocaleString()} 超过限额 ¥${effectiveMaxOrderValue.toLocaleString()}`}
            description={
              <div style={{ fontSize: 12 }}>
                机构模式下单金额超过预设限额。请确认是否需要继续提交。
              </div>
            }
            style={{ fontSize: 12 }}
          />
        </Space>
      </Modal>
    </div>
  )
}
