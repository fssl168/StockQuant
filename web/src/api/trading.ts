import client from './client'
import { Order, OrderSide, OrderType, AccountInfo, Position, TradeRecord } from '../types'

const USE_MOCK = !import.meta.env.VITE_API_URL

const MOCK_DELAY = 500

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// ── Seeded PRNG for reproducible mock data ───────────────────

function mulberry32(a: number) {
  return function() {
    let t = a += 0x6D2B79F5
    t = Math.imul(t ^ t >>> 15, t | 1)
    t ^= t + Math.imul(t ^ t >>> 7, t | 61)
    return ((t ^ t >>> 14) >>> 0) / 4294967296
  }
}

const SEED = 42
let rng = mulberry32(SEED)

function nextRandom() {
  return rng()
}

// ── Mock Data Generators ──────────────────────────────────────

let mockOrderId = 100

function generateMockOrders(): Order[] {
  const now = new Date()
  return [
    {
      id: `ORD-${++mockOrderId}`,
      symbol: 'sh600519',
      side: 'BUY',
      type: 'LIMIT',
      price: 1720,
      quantity: 100,
      filledQty: 100,
      filledAvgPrice: 1720.5,
      status: 'FILLED',
      createdAt: new Date(now.getTime() - 3600000).toISOString(),
      updatedAt: new Date(now.getTime() - 3590000).toISOString(),
    },
    {
      id: `ORD-${++mockOrderId}`,
      symbol: 'sz000858',
      side: 'BUY',
      type: 'LIMIT',
      price: 148,
      quantity: 200,
      filledQty: 200,
      filledAvgPrice: 148.2,
      status: 'FILLED',
      createdAt: new Date(now.getTime() - 7200000).toISOString(),
      updatedAt: new Date(now.getTime() - 7180000).toISOString(),
    },
    {
      id: `ORD-${++mockOrderId}`,
      symbol: 'sh601318',
      side: 'SELL',
      type: 'LIMIT',
      price: 47.5,
      quantity: 500,
      filledQty: 300,
      filledAvgPrice: 47.4,
      status: 'PARTIAL_FILLED',
      createdAt: new Date(now.getTime() - 1800000).toISOString(),
      updatedAt: now.toISOString(),
    },
    {
      id: `ORD-${++mockOrderId}`,
      symbol: 'sh600519',
      side: 'BUY',
      type: 'STOP',
      price: 1750,
      quantity: 100,
      filledQty: 0,
      filledAvgPrice: 0,
      status: 'PENDING',
      createdAt: new Date(now.getTime() - 600000).toISOString(),
      updatedAt: now.toISOString(),
    },
  ]
}

let mockTradeId = 200

function generateMockTrades(): TradeRecord[] {
  const now = new Date()
  return Array.from({ length: 12 }, (_, i) => ({
    id: `TRD-${++mockTradeId}`,
    orderId: `ORD-${100 + i}`,
    symbol: ['sh600519', 'sz000858', 'sh601318'][i % 3],
    side: (i % 4 < 2 ? 'BUY' : 'SELL') as OrderSide,
    price: [1720.5, 148.2, 47.4, 1721.0, 147.8, 48.0][i % 6],
    quantity: [100, 200, 100, 50, 300, 200][i % 6],
    commission: Number((nextRandom() * 10 + 1).toFixed(2)),
    timestamp: new Date(now.getTime() - (i + 1) * 300000).toISOString(),
  }))
}

const mockPositions: Position[] = [
  { symbol: 'sh600519', name: '贵州茅台', shares: 100, cost: 1680, price: 1725.5, pnl: 4550, pnlPct: 2.71 },
  { symbol: 'sz000858', name: '五粮液', shares: 200, cost: 150, price: 146.8, pnl: -640, pnlPct: -2.13 },
  { symbol: 'sh601318', name: '中国平安', shares: 500, cost: 46.2, price: 48.5, pnl: 1150, pnlPct: 4.98 },
]

const mockAccount: AccountInfo = {
  totalEquity: 1234567,
  cash: 456789,
  frozenCash: 12000,
  marketValue: 777778,
  availableCash: 444789,
  dailyPnl: 12345,
  dailyPnlPct: 1.02,
}

// In-memory mutable state for mock CRUD
let orders = generateMockOrders()
let trades = generateMockTrades()

// ── Mock Implementations ──────────────────────────────────────

async function mockGetAccount(): Promise<AccountInfo> {
  await delay(MOCK_DELAY)
  return { ...mockAccount }
}

async function mockGetOrders(): Promise<Order[]> {
  await delay(MOCK_DELAY)
  return [...orders]
}

async function mockPlaceOrder(req: {
  symbol: string
  side: OrderSide
  type: OrderType
  price: number
  quantity: number
}): Promise<Order> {
  await delay(800)

  // Input validation
  if (req.quantity <= 0) {
    throw new Error('数量必须大于0')
  }
  if (req.price <= 0) {
    throw new Error('价格必须大于0')
  }

  const now = new Date().toISOString()
  const newOrder: Order = {
    id: `ORD-${++mockOrderId}`,
    symbol: req.symbol,
    side: req.side,
    type: req.type,
    price: req.price,
    quantity: req.quantity,
    filledQty: req.type === 'MARKET' ? req.quantity : 0,
    filledAvgPrice: req.type === 'MARKET' ? req.price * (1 + (nextRandom() - 0.5) * 0.002) : 0,
    status: req.type === 'MARKET' ? 'FILLED' : 'SUBMITTED',
    createdAt: now,
    updatedAt: now,
  }
  orders = [newOrder, ...orders]

  // Auto-fill MARKET orders into trades
  if (req.type === 'MARKET') {
    trades = [
      {
        id: `TRD-${++mockTradeId}`,
        orderId: newOrder.id,
        symbol: req.symbol,
        side: req.side,
        price: newOrder.filledAvgPrice,
        quantity: req.quantity,
        commission: Number((req.price * req.quantity * 0.00025).toFixed(2)),
        timestamp: now,
      },
      ...trades,
    ]
  }

  return newOrder
}

async function mockCancelOrder(orderId: string): Promise<void> {
  await delay(400)
  orders = orders.map((o) =>
    o.id === orderId && (o.status === 'PENDING' || o.status === 'SUBMITTED')
      ? { ...o, status: 'CANCELLED' as const, updatedAt: new Date().toISOString() }
      : o,
  )
}

async function mockGetPositions(): Promise<Position[]> {
  await delay(MOCK_DELAY)
  return [...mockPositions]
}

async function mockGetTrades(): Promise<TradeRecord[]> {
  await delay(MOCK_DELAY)
  return [...trades]
}

// ── API Functions ────────────────────────────────────────────

export async function getAccount(): Promise<AccountInfo> {
  if (USE_MOCK) return mockGetAccount()
  return client.get<AccountInfo>('/trading/account') as any
}

export async function getOrders(): Promise<Order[]> {
  if (USE_MOCK) return mockGetOrders()
  return client.get<Order[]>('/trading/orders') as any
}

export async function placeOrder(req: {
  symbol: string
  side: OrderSide
  type: OrderType
  price: number
  quantity: number
}): Promise<Order> {
  if (USE_MOCK) return mockPlaceOrder(req)
  return client.post<Order>('/trading/order', req) as any
}

export async function cancelOrder(orderId: string): Promise<void> {
  if (USE_MOCK) return mockCancelOrder(orderId)
  await client.delete(`/trading/order/${orderId}`)
}

export async function getPositions(): Promise<Position[]> {
  if (USE_MOCK) return mockGetPositions()
  return client.get<Position[]>('/trading/positions') as any
}

export async function getTrades(): Promise<TradeRecord[]> {
  if (USE_MOCK) return mockGetTrades()
  return client.get<TradeRecord[]>('/trading/trades') as any
}

// ── Test Helpers ─────────────────────────────────────────────
// Exported for test isolation — resets PRNG seed and mutable state

export function __resetSeed(): void {
  rng = mulberry32(SEED)
  orders = generateMockOrders()
  trades = generateMockTrades()
}
