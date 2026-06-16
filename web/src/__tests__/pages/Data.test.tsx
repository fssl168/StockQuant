import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import Data from '@/pages/Data'

vi.mock('@/stores/dataStore', () => ({
  useDataStore: vi.fn((selector: any) => {
    const state = {
      sources: [],
      cacheStats: null,
      loading: false,
      fetchSources: vi.fn(),
      fetchCacheStats: vi.fn(),
    }
    return selector ? selector(state) : state
  }),
}))

vi.mock('echarts-for-react', () => ({
  default: () => <div data-testid="echarts" />,
}))

describe('Data Page', () => {
  it('should render page title', () => {
    render(<Data />)
    expect(screen.getByText('数据管理')).toBeInTheDocument()
  })

  it('should render subtitle', () => {
    render(<Data />)
    expect(screen.getByText('数据源配置、缓存管理与采集日志')).toBeInTheDocument()
  })

  it('should render cache stats cards', () => {
    render(<Data />)
    expect(screen.getByText('缓存大小')).toBeInTheDocument()
    expect(screen.getByText('命中率')).toBeInTheDocument()
    expect(screen.getByText('标的数')).toBeInTheDocument()
    // 最后更新 appears in both cache stats card and data source table header
    expect(screen.getAllByText('最后更新').length).toBeGreaterThanOrEqual(1)
  })

  it('should render K-line query section', () => {
    render(<Data />)
    expect(screen.getByText('K 线查询')).toBeInTheDocument()
  })

  it('should render stock symbol input', () => {
    render(<Data />)
    expect(screen.getByPlaceholderText('股票代码 (e.g. sh600519)')).toBeInTheDocument()
  })

  it('should render query button', () => {
    render(<Data />)
    expect(screen.getByRole('button', { name: /查询/ })).toBeInTheDocument()
  })

  it('should render data source table', () => {
    render(<Data />)
    expect(screen.getByText('数据源配置')).toBeInTheDocument()
  })

  it('should render collection log table', () => {
    render(<Data />)
    expect(screen.getByText('采集日志')).toBeInTheDocument()
  })
})
