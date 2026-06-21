import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Monitor from '@/pages/Monitor'

// Mock useWebSocket hook
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => ({
    messages: [],
    connected: false,
  }),
}))

// Mock monitor API
vi.mock('@/api/monitor', () => ({
  monitorApi: {
    getWatchlist: vi.fn(() => Promise.resolve(['sh600519'])),
    updateWatchlist: vi.fn(() => Promise.resolve(['sh600519', 'sh600000'])),
    removeFromWatchlist: vi.fn(() => Promise.resolve([])),
    start: vi.fn(() => Promise.resolve()),
    stop: vi.fn(() => Promise.resolve()),
    status: vi.fn(() => Promise.resolve({ running: false })),
    scan: vi.fn(() => Promise.resolve([{ symbol: 'sh600519', type: '放量突破', description: 'Test anomaly', time: '10:30:00' }])),
    brief: vi.fn(() => Promise.resolve('Market brief text')),
    summary: vi.fn(() => Promise.resolve({ summary: 'Daily summary text' })),
  },
}))

// Mock data API
vi.mock('@/api/data', () => ({
  dataApi: {
    fetchKline: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

// Mock client
vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { environment: 'calm', max_position_pct: 0.8, max_daily_loss_pct: 0.03, max_drawdown_pct: 0.1 } })),
    put: vi.fn(() => Promise.resolve()),
    delete: vi.fn(() => Promise.resolve()),
  },
}))

// Mock notificationStore
vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: vi.fn((selector?: any) => {
    const state = {
      notifications: [],
      add: vi.fn(),
      deleteNotification: vi.fn(),
    }
    return selector ? selector(state) : state
  }),
}))

// Mock StockTicker
vi.mock('@/components/Monitor/StockTicker', () => ({
  default: ({ symbol, price, change }: any) => (
    <div data-testid="stock-ticker">
      {symbol} - {price} - {change}%
    </div>
  ),
}))

// Mock RealtimeKline
vi.mock('@/components/Chart/RealtimeKline', () => ({
  default: () => <div data-testid="realtime-kline" />,
}))

// Mock SentimentPanel
vi.mock('@/components/Monitor/SentimentPanel', () => ({
  default: () => <div data-testid="sentiment-panel" />,
}))

// Mock SignalCard
vi.mock('@/components/AI/SignalCard', () => ({
  default: (props: any) => (
    <div data-testid="signal-card" data-type={props.type}>
      {props.title}
    </div>
  ),
}))

describe('Monitor E2E Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Page render', () => {
    it('should render monitor page with all required elements', async () => {
      render(<Monitor />)

      // Wait for page to load
      await waitFor(() => {
        expect(screen.getByText('实时盯盘')).toBeInTheDocument()
      })

      // Verify input exists
      expect(screen.getByPlaceholderText('输入股票代码 (e.g. sh600519)')).toBeInTheDocument()

      // Verify add button exists
      expect(screen.getByRole('button', { name: /添加/ })).toBeInTheDocument()
    })

    it('should load existing watchlist on mount', async () => {
      render(<Monitor />)

      // Wait for watchlist to load
      await waitFor(() => {
        expect(screen.getByText('sh600519')).toBeInTheDocument()
      })
    })
  })

  describe('Watchlist management flow', () => {
    it('should have add button and input for adding stocks', async () => {
      const user = userEvent.setup()
      render(<Monitor />)

      // Wait for watchlist to load
      await waitFor(() => {
        expect(screen.getByText('sh600519')).toBeInTheDocument()
      })

      // Find and fill the input
      const symbolInput = screen.getByPlaceholderText('输入股票代码 (e.g. sh600519)')
      await user.type(symbolInput, 'sh600000')

      // Click add button
      const addButton = screen.getByRole('button', { name: /添加/ })
      await user.click(addButton)

      // Verify the stock appears in the watchlist
      await waitFor(() => {
        expect(screen.getByText('sh600000')).toBeInTheDocument()
      })
    })
  })

  describe('Scan workflow', () => {
    it('should have scan button for anomaly detection', async () => {
      render(<Monitor />)

      await waitFor(() => {
        expect(screen.getByText('sh600519')).toBeInTheDocument()
      })

      // Verify scan button exists
      expect(screen.getByRole('button', { name: /扫描异动/ })).toBeInTheDocument()
    })
  })

  describe('Start/Stop monitoring flow', () => {
    it('should show start button when not running', async () => {
      render(<Monitor />)

      await waitFor(() => {
        expect(screen.getByText('实时盯盘')).toBeInTheDocument()
      })

      // Verify start button exists
      expect(screen.getByRole('button', { name: /开始扫描/ })).toBeInTheDocument()
      expect(screen.getByText('扫描已停止')).toBeInTheDocument()
    })
  })
})