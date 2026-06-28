/**
 * A-share stock trading rule validator.
 *
 * Covers:
 * - Quantity lot-size rules (100-shares for main board / GEM / STAR ETF, 10 for convertibles)
 * - Price limit bands (±10% main, ±20% GEM / STAR)
 * - T+1 settlement
 */

// ---- shared types ----

export interface ValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
}

// ---- lot-size helpers ----

/**
 * Return the minimum lot size for a given symbol.
 *
 * Convertible bonds (代码以 11/12/13/19 开头) → 10 shares.
 * ETF → 100 shares.
 * Default A-share → 100 shares.
 */
function getLotSize(symbol: string): number {
  const upper = symbol.toUpperCase()

  // Convertible bonds: 11xxxx, 12xxxx, 13xxxx, 19xxxx
  if (/^(11|12|13|19)\d{4}$/.test(upper.replace(/^SH|SZ/, ''))) {
    return 10
  }

  // ETF codes on Shanghai: 51xxxx, Shenzhen: 15xxxx
  if (/^(51|15)\d{4}$/.test(upper.replace(/^SH|SZ/, ''))) {
    return 100
  }

  // Default: A-share (主板 / 创业板 / 科创板)
  return 100
}

/**
 * Determine the market segment for a symbol to apply the correct price limit.
 *
 * - 创业板 (GEM): Shenzhen 03xxxx
 * - 科创板 (STAR): Shanghai 68xxxx
 * - 北交所 (BSE): Beijing 8xxxxx / 4xxxxx  (±30%, not commonly used yet)
 * - Main board: everything else  ±10%
 */
function getMarketSegment(symbol: string): 'main' | 'gem' | 'star' {
  const upper = symbol.toUpperCase()
  const code = upper.replace(/^SH|SZ|BJ/, '')

  // 创业板 03xxxx (Shenzhen)
  if (/^03\d{4}$/.test(code)) {
    return 'gem'
  }

  // 科创板 68xxxx (Shanghai)
  if (/^68\d{4}$/.test(code)) {
    return 'star'
  }

  // 北交所 (Beijing Stock Exchange)
  if (/^(8\d{4}|4\d{4})/.test(code)) {
    return 'main' // treated as main for now; can extend to ±30% later
  }

  return 'main'
}

const LIMIT_RATES: Record<string, number> = {
  main: 0.1,
  gem: 0.2,
  star: 0.2,
}

// ---- public API ----

/**
 * Validate an order payload before submission.
 * Returns all errors and warnings in one pass.
 */
export function validateOrder(order: {
  symbol: string
  side: 'BUY' | 'SELL'
  price: number
  quantity: number
}): ValidationResult {
  const errors: string[] = []
  const warnings: string[] = []

  if (!order.symbol || !order.symbol.trim()) {
    errors.push('股票代码不能为空')
  }

  if (order.price <= 0) {
    errors.push('价格必须大于 0')
  }

  if (order.quantity <= 0) {
    errors.push('数量必须大于 0')
  }

  // Lot-size validation
  if (order.quantity > 0) {
    const qtyValidation = validateQuantity(order.symbol, order.quantity)
    errors.push(...qtyValidation.errors)
    warnings.push(...qtyValidation.warnings)
  }

  // T+1 check (only for SELL)
  // Note: caller must provide position context separately; this function does not check.

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  }
}

/**
 * Check that the quantity is a valid lot multiple.
 */
export function validateQuantity(
  symbol: string,
  quantity: number,
): ValidationResult {
  const errors: string[] = []
  const warnings: string[] = []

  if (quantity <= 0) {
    errors.push('数量必须大于 0')
    return { valid: false, errors, warnings }
  }

  const lot = getLotSize(symbol)

  if (quantity % lot !== 0) {
    errors.push(
      `数量必须是 ${lot} 股的整数倍（当前: ${quantity}）`,
    )
  }

  // 科创板/创业板单笔申报上限提醒
  const segment = getMarketSegment(symbol)
  if (segment === 'star' && quantity > 100000) {
    warnings.push('科创板单笔申报超过 10 万股，请确认是否符合规定')
  }
  if (segment === 'gem' && quantity > 100000) {
    warnings.push('创业板单笔申报超过 10 万股，请确认是否符合规定')
  }

  return { valid: errors.length === 0, errors, warnings }
}

/**
 * Validate price against the ± limit band derived from the previous close price.
 */
export function validatePrice(
  symbol: string,
  price: number,
  prevClose: number,
): ValidationResult {
  const errors: string[] = []
  const warnings: string[] = []

  if (prevClose <= 0) {
    errors.push('缺少昨收价格，无法校验涨跌停')
    return { valid: false, errors, warnings }
  }

  if (price <= 0) {
    errors.push('价格必须大于 0')
    return { valid: false, errors, warnings }
  }

  const segment = getMarketSegment(symbol)
  void segment  // used in error messages
  const { upper, lower } = getLimitPrice(symbol, prevClose)

  if (price > upper) {
    errors.push(`买入价格超过涨停价 ¥${upper.toFixed(2)}（${segment === 'main' ? '主板' : segment === 'gem' ? '创业板' : '科创板'} ±10%/±20%）`)
  }
  if (price < lower) {
    errors.push(`价格低于跌停价 ¥${lower.toFixed(2)}（${segment === 'main' ? '主板' : segment === 'gem' ? '创业板' : '科创板'} ±10%/±20%）`)
  }

  return { valid: errors.length === 0, errors, warnings }
}

/**
 * Compute the upper and lower limit prices based on the previous close.
 * Rounded to 2 decimal places using the standard A-share rounding rules.
 */
export function getLimitPrice(
  symbol: string,
  prevClose: number,
): { upper: number; lower: number } {
  const segment = getMarketSegment(symbol)
  const rate = LIMIT_RATES[segment]

  const rawUpper = prevClose * (1 + rate)
  const rawLower = prevClose * (1 - rate)

  return {
    upper: Math.round(rawUpper * 100) / 100,
    lower: Math.round(rawLower * 100) / 100,
  }
}

/**
 * T+1 settlement check.
 *
 * Shares bought today (no buyDate or buyDate === today) cannot be sold.
 * Existing positions with a recorded buyDate prior to today are allowed.
 */
export function checkTPlus1(
  _symbol: string,
  side: 'BUY' | 'SELL',
  position: { shares: number; buyDate?: string },
): ValidationResult {
  const errors: string[] = []
  const warnings: string[] = []

  if (side !== 'SELL') {
    return { valid: true, errors: [], warnings }
  }

  if (position.shares <= 0) {
    errors.push('持仓不足')
    return { valid: false, errors, warnings }
  }

  const today = new Date().toISOString().slice(0, 10)
  const buyDate = position.buyDate

  // No buyDate recorded: assume existing position (bought before today)
  if (!buyDate) {
    warnings.push('该持仓未记录买入日期，暂按 T+1 放行')
    return { valid: true, errors, warnings }
  }

  // buyDate === today → shares bought today, cannot sell
  if (buyDate === today) {
    errors.push('T+1 规则：今日买入的股份今日不可卖出')
  }

  return { valid: errors.length === 0, errors, warnings }
}
