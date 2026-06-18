import { useState, useEffect, useMemo } from 'react'
import { Card, Typography, Table, Button, Tag, Space, Divider, Tabs, Descriptions, List, Alert, Select } from 'antd'
import { CheckCircle, ArrowRight, TrendUp, Circle, ChartPie, Heartbeat } from '@phosphor-icons/react'
import ReactECharts from 'echarts-for-react'
import ComparisonChart from '@/components/Comparison/ComparisonChart'
import { backtestApi } from '@/api/dashboard'
import client from '@/api/client'

const { Title, Text, Paragraph } = Typography

interface BacktestItem {
  task_id: string
  strategy_name: string
  status: string
  metrics: Record<string, number | string>
  created_at: string
}

interface ComparisonResult {
  strategies: Array<{
    name: string
    metrics: Record<string, number>
    portfolio_weights?: Record<string, number>
    recommendations?: string[]
  }>
  summary?: string
}

interface OptimizeResult {
  weights: Record<string, number>
  expectedReturn: number
  expectedVolatility: number
  expectedSharpe: number
  maxDrawdown: number
  correlationMatrix: Record<string, Record<string, number>>
}

interface LifecycleResult {
  strategyId: string
  advice: 'enable' | 'disable' | 'adjust'
  reason: string
  metrics: {
    recentReturn: number
    recentSharpe: number
    recentMaxDrawdown: number
  }
  suggestions: string[]
}

const METRIC_COLS = [
  {
    title: '策略名称',
    dataIndex: 'name',
    key: 'name',
    width: 160,
    fixed: 'left' as const,
    render: (name: string) => <Text strong style={{ color: '#fafafa' }}>{name}</Text>,
  },
  {
    title: '总收益率',
    dataIndex: 'total_return',
    key: 'total_return',
    width: 110,
    sorter: (a: any, b: any) => (a.total_return || 0) - (b.total_return || 0),
    render: (v: number) => v != null ? (
      <Text style={{ color: v >= 0 ? '#10b981' : '#ef4444', fontFamily: 'var(--font-mono)' }}>
        {(v * 100).toFixed(2)}%
      </Text>
    ) : <Text type="secondary">-</Text>,
  },
  {
    title: '夏普比率',
    dataIndex: 'sharpe_ratio',
    key: 'sharpe_ratio',
    width: 90,
    sorter: (a: any, b: any) => (a.sharpe_ratio || 0) - (b.sharpe_ratio || 0),
    render: (v: number) => v != null ? (
      <Text style={{ fontFamily: 'var(--font-mono)' }}>{v.toFixed(2)}</Text>
    ) : <Text type="secondary">-</Text>,
  },
  {
    title: '最大回撤',
    dataIndex: 'max_drawdown',
    key: 'max_drawdown',
    width: 110,
    sorter: (a: any, b: any) => (a.max_drawdown || 0) - (b.max_drawdown || 0),
    render: (v: number) => v != null ? (
      <Text style={{ color: '#ef4444', fontFamily: 'var(--font-mono)' }}>
        {(v * 100).toFixed(2)}%
      </Text>
    ) : <Text type="secondary">-</Text>,
  },
  {
    title: '胜率',
    dataIndex: 'win_rate',
    key: 'win_rate',
    width: 90,
    sorter: (a: any, b: any) => (a.win_rate || 0) - (b.win_rate || 0),
    render: (v: number) => v != null ? (
      <Text style={{ fontFamily: 'var(--font-mono)' }}>{(v * 100).toFixed(1)}%</Text>
    ) : <Text type="secondary">-</Text>,
  },
  {
    title: 'SQN',
    dataIndex: 'sqn',
    key: 'sqn',
    width: 70,
    render: (v: number) => v != null ? (
      <Text style={{ fontFamily: 'var(--font-mono)' }}>{v.toFixed(2)}</Text>
    ) : <Text type="secondary">-</Text>,
  },
  {
    title: '交易次数',
    dataIndex: 'total_trades',
    key: 'total_trades',
    width: 90,
    render: (v: number) => v != null ? <Text style={{ fontFamily: 'var(--font-mono)' }}>{v}</Text> : <Text type="secondary">-</Text>,
  },
]

export default function Comparison() {
  const [backtests, setBacktests] = useState<BacktestItem[]>([])
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [comparisonData, setComparisonData] = useState<ComparisonResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [chartLoading, setChartLoading] = useState(false)
  const [optimizeResult, setOptimizeResult] = useState<OptimizeResult | null>(null)
  const [optimizeLoading, setOptimizeLoading] = useState(false)
  const [lifecycleResult, setLifecycleResult] = useState<LifecycleResult | null>(null)
  const [lifecycleLoading, setLifecycleLoading] = useState(false)
  const [lifecycleStrategyId, setLifecycleStrategyId] = useState<string>('')
  const [activeTab, setActiveTab] = useState('compare')

  useEffect(() => {
    backtestApi.list()
      .then((r: any[]) => {
        if (Array.isArray(r)) setBacktests(r.slice(0, 50))
      })
      .catch((e: any) => console.warn('[Comparison] 获取回测列表失败:', e?.message))
  }, [])

  const selectedBacktests = useMemo(
    () => backtests.filter((b) => selectedIds.includes(b.task_id)),
    [backtests, selectedIds],
  )

  const handleCompare = async () => {
    if (selectedIds.length < 2) return
    setLoading(true)
    setChartLoading(true)
    try {
      const res = await client.post('/comparison', { strategy_ids: selectedIds }) as any
      // 拦截器返回裸数据，直接传给 setState
      setComparisonData(res)
    } catch (e) {
      console.error('对比请求失败:', e)
    } finally {
      setLoading(false)
      setChartLoading(false)
    }
  }

  const handleSelectAll = () => {
    if (selectedIds.length === backtests.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(backtests.map((b) => b.task_id))
    }
  }

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    )
  }

  const handleOptimize = async () => {
    if (selectedIds.length < 2) return
    setOptimizeLoading(true)
    try {
      const res = await client.post('/comparison/optimize', { strategy_ids: selectedIds }) as any
      setOptimizeResult(res)
    } catch (e) {
      console.error('组合优化请求失败:', e)
    } finally {
      setOptimizeLoading(false)
    }
  }

  const handleLifecycle = async () => {
    if (!lifecycleStrategyId) return
    setLifecycleLoading(true)
    try {
      const res = await client.get(`/comparison/lifecycle/${lifecycleStrategyId}`) as any
      setLifecycleResult(res)
    } catch (e) {
      console.error('生命周期建议请求失败:', e)
    } finally {
      setLifecycleLoading(false)
    }
  }

  // Build chart strategies from comparison data or selected backtests
  const chartStrategies = useMemo(() => {
    if (comparisonData?.strategies) {
      return comparisonData.strategies.map((s) => ({
        name: s.name,
        metrics: {
          total_return: s.metrics.total_return,
          sharpe_ratio: s.metrics.sharpe_ratio,
          max_drawdown: s.metrics.max_drawdown,
          win_rate: s.metrics.win_rate,
          profit_loss_ratio: s.metrics.profit_loss_ratio,
        },
      }))
    }
    // Fallback: use selected backtests with their metrics
    return selectedBacktests.map((b) => ({
      name: b.strategy_name,
      metrics: {
        total_return: (b.metrics as any)['Annualized Return'],
        sharpe_ratio: (b.metrics as any)['Sharpe Ratio'],
        max_drawdown: (b.metrics as any)['Max Drawdown'],
        win_rate: (b.metrics as any)['Win Rate'],
        profit_loss_ratio: (b.metrics as any)['Profit/Loss Ratio'],
      },
    }))
  }, [comparisonData, selectedBacktests])

  // Build table data from comparison data or selected backtests
  const tableData = useMemo(() => {
    if (comparisonData?.strategies) {
      return comparisonData.strategies.map((s) => ({
        key: s.name,
        name: s.name,
        total_return: s.metrics.total_return,
        sharpe_ratio: s.metrics.sharpe_ratio,
        max_drawdown: s.metrics.max_drawdown,
        win_rate: s.metrics.win_rate,
        sqn: s.metrics.sqn,
        total_trades: s.metrics.total_trades,
        _portfolio_weights: s.portfolio_weights,
        _recommendations: s.recommendations,
      }))
    }
    return selectedBacktests.map((b) => ({
      key: b.task_id,
      name: b.strategy_name,
      total_return: (b.metrics as any)['Annualized Return'],
      sharpe_ratio: (b.metrics as any)['Sharpe Ratio'],
      max_drawdown: (b.metrics as any)['Max Drawdown'],
      win_rate: (b.metrics as any)['Win Rate'],
      sqn: null,
      total_trades: null,
      _portfolio_weights: null,
      _recommendations: null,
    }))
  }, [comparisonData, selectedBacktests])

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ marginBottom: 20 }}>
        <Title level={5} style={{ margin: 0, color: 'var(--color-text-primary)', fontWeight: 600, letterSpacing: '0.03em' }}>
          策略对比 <Text type="secondary" style={{ fontWeight: 400, fontSize: 12 }}>F027</Text>
        </Title>
        <Paragraph type="secondary" style={{ margin: '4px 0 0', fontSize: 12 }}>
          选择至少 2 个回测结果，对比策略表现
        </Paragraph>
      </div>

      {/* Backtest selection card */}
      <Card
        size="small"
        title={
          <span style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.03em' }}>
            选择回测任务
            {selectedIds.length > 0 && (
              <Tag color="blue" style={{ marginLeft: 8 }}>已选 {selectedIds.length}</Tag>
            )}
          </span>
        }
        styles={{ body: { padding: '0 16px 12px' } }}
        style={{ marginBottom: 16 }}
      >
        {/* Select all / clear row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0' }}>
          <Space>
            <Button size="small" onClick={handleSelectAll}>
              {selectedIds.length === backtests.length ? '取消全选' : '全选'}
            </Button>
          </Space>
          <Text type="secondary" style={{ fontSize: 11 }}>
            已选 {selectedIds.length} / {backtests.length} 个任务
          </Text>
        </div>

        <Table
          dataSource={backtests}
          columns={[
            {
              title: '策略名称',
              dataIndex: 'strategy_name',
              key: 'name',
              render: (name: string) => <Text strong>{name}</Text>,
            },
            {
              title: '状态',
              dataIndex: 'status',
              key: 'status',
              width: 80,
              render: (s: string) => (
                <Tag color={s === 'completed' ? 'green' : s === 'running' ? 'blue' : 'default'}>
                  {s === 'completed' ? <CheckCircle size={10} weight="bold" style={{ marginRight: 2 }} /> : <Circle size={10} weight="bold" style={{ marginRight: 2 }} />}
                  {s}
                </Tag>
              ),
            },
            {
              title: '收益率',
              key: 'return',
              width: 110,
              render: (_: any, r: any) => {
                const ret = r.metrics?.['Annualized Return']
                if (!ret) return <Text type="secondary">-</Text>
                const num = typeof ret === 'string' ? parseFloat(ret) : ret
                return (
                  <Text style={{ color: num >= 0 ? '#10b981' : '#ef4444', fontFamily: 'var(--font-mono)' }}>
                    {num >= 0 ? '+' : ''}{num.toFixed(1)}%
                  </Text>
                )
              },
            },
            {
              title: '选择',
              key: 'select',
              width: 70,
              render: (_: any, r: any) => (
                <Button
                  size="small"
                  type={selectedIds.includes(r.task_id) ? 'primary' : 'default'}
                  onClick={() => toggleSelect(r.task_id)}
                  icon={selectedIds.includes(r.task_id) ? <CheckCircle size={12} weight="fill" /> : undefined}
                >
                  {selectedIds.includes(r.task_id) ? '已选' : '选择'}
                </Button>
              ),
            },
          ]}
          rowKey="task_id"
          pagination={{ pageSize: 10, size: 'small' }}
          size="small"
          rowSelection={undefined}
        />
      </Card>

      {/* Compare button */}
      <div style={{ textAlign: 'center', marginBottom: 20 }}>
        <Button
          type="primary"
          size="large"
          icon={<TrendUp size={18} />}
          loading={loading}
          disabled={selectedIds.length < 2}
          onClick={handleCompare}
          style={{
            borderRadius: 8,
            fontWeight: 600,
            minWidth: 160,
          }}
        >
          开始对比 {selectedIds.length >= 2 && `(${selectedIds.length} 个策略)`}
        </Button>
      </div>

      {/* Results area */}
      {tableData.length >= 2 && (
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'compare',
              label: '策略对比',
              children: (
                <>
                  {/* Chart */}
                  <Card
                    size="small"
                    title={<span style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.03em' }}>可视化对比</span>}
                    styles={{ body: { padding: '12px' } }}
                    style={{ marginBottom: 16 }}
                  >
                    {chartLoading ? (
                      <div style={{ height: 350, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#71717a' }}>
                        加载中...
                      </div>
                    ) : (
                      <ComparisonChart strategies={chartStrategies} height={350} />
                    )}
                  </Card>

                  {/* Metrics table */}
                  <Card
                    size="small"
                    title={<span style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.03em' }}>指标对比</span>}
                    styles={{ body: { padding: 0 } }}
                    style={{ marginBottom: 16 }}
                  >
                    <Table
                      dataSource={tableData}
                      columns={METRIC_COLS}
                      pagination={false}
                      size="small"
                      scroll={{ x: 800 }}
                      locale={{ emptyText: <Text type="secondary">暂无数据</Text> }}
                    />
                  </Card>

                  {/* Portfolio weights */}
                  {tableData.some((row) => row._portfolio_weights) && (
                    <Card
                      size="small"
                      title={<span style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.03em' }}>投资组合权重</span>}
                      styles={{ body: { padding: '12px' } }}
                      style={{ marginBottom: 16 }}
                    >
                      {tableData.map((row) => (
                        row._portfolio_weights && (
                          <div key={row.name} style={{ marginBottom: 12 }}>
                            <Text strong style={{ color: '#fafafa', fontSize: 12 }}>{row.name}</Text>
                            <Divider style={{ margin: '6px 0 8px' }} />
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                              {Object.entries(row._portfolio_weights as Record<string, number>).map(([symbol, weight]) => (
                                <Tag key={symbol} color="blue" style={{ fontSize: 11 }}>
                                  {symbol}: {(weight * 100).toFixed(1)}%
                                </Tag>
                              ))}
                            </div>
                          </div>
                        )
                      ))}
                    </Card>
                  )}

                  {/* Recommendations */}
                  {tableData.some((row) => row._recommendations && row._recommendations.length > 0) && (
                    <Card
                      size="small"
                      title={<span style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.03em' }}>AI 建议</span>}
                      styles={{ body: { padding: '12px 16px' } }}
                      style={{ marginBottom: 16 }}
                    >
                      {tableData.map((row) => (
                        row._recommendations && row._recommendations.length > 0 && (
                          <div key={row.name} style={{ marginBottom: 12 }}>
                            <Text strong style={{ color: '#fafafa', fontSize: 12 }}>{row.name}</Text>
                            {row._recommendations.map((rec: string, idx: number) => (
                              <div key={idx} style={{ display: 'flex', gap: 8, marginTop: 4, alignItems: 'flex-start' }}>
                                <ArrowRight size={14} weight="bold" style={{ color: '#3b82f6', marginTop: 2, flexShrink: 0 }} />
                                <Text style={{ fontSize: 12 }}>{rec}</Text>
                              </div>
                            ))}
                          </div>
                        )
                      ))}
                    </Card>
                  )}
                </>
              ),
            },
            {
              key: 'optimize',
              label: '组合优化',
              children: (
                <>
                  <div style={{ textAlign: 'center', marginBottom: 16 }}>
                    <Button
                      type="primary"
                      icon={<ChartPie size={16} />}
                      loading={optimizeLoading}
                      disabled={selectedIds.length < 2}
                      onClick={handleOptimize}
                      style={{ borderRadius: 8, fontWeight: 600, minWidth: 160 }}
                    >
                      开始优化 {selectedIds.length >= 2 && `(${selectedIds.length} 个策略)`}
                    </Button>
                    {selectedIds.length < 2 && (
                      <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
                        请先选择至少 2 个回测任务
                      </Text>
                    )}
                  </div>

                  {optimizeResult && (
                    <>
                      {/* Weight Pie Chart */}
                      <Card
                        size="small"
                        title={<span style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.03em' }}>最优权重分配</span>}
                        styles={{ body: { padding: '12px' } }}
                        style={{ marginBottom: 16 }}
                      >
                        <ReactECharts
                          option={{
                            tooltip: { trigger: 'item', formatter: '{b}: {d}%' },
                            legend: { bottom: 0, textStyle: { color: '#a1a1aa', fontSize: 11 } },
                            series: [{
                              type: 'pie',
                              radius: ['40%', '70%'],
                              avoidLabelOverlap: true,
                              itemStyle: { borderRadius: 6, borderColor: '#1a1a2e', borderWidth: 2 },
                              label: { show: true, formatter: '{b}\n{d}%', color: '#e4e4e7', fontSize: 11 },
                              data: Object.entries(optimizeResult.weights).map(([name, value]) => ({
                                name,
                                value: Number((value * 100).toFixed(1)),
                              })),
                            }],
                            color: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'],
                          }}
                          style={{ height: 300 }}
                        />
                      </Card>

                      {/* Expected Metrics */}
                      <Card
                        size="small"
                        title={<span style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.03em' }}>组合期望指标</span>}
                        styles={{ body: { padding: '12px 16px' } }}
                        style={{ marginBottom: 16 }}
                      >
                        <Descriptions column={2} size="small" colon={false}>
                          <Descriptions.Item label={<Text type="secondary" style={{ fontSize: 12 }}>期望收益</Text>}>
                            <Text style={{ color: (optimizeResult.expectedReturn ?? 0) >= 0 ? '#10b981' : '#ef4444', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                              {((optimizeResult.expectedReturn ?? 0) * 100).toFixed(2)}%
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={<Text type="secondary" style={{ fontSize: 12 }}>期望波动率</Text>}>
                            <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                              {((optimizeResult.expectedVolatility ?? 0) * 100).toFixed(2)}%
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={<Text type="secondary" style={{ fontSize: 12 }}>期望夏普</Text>}>
                            <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: (optimizeResult.expectedSharpe ?? 0) >= 1 ? '#10b981' : '#f59e0b' }}>
                              {(optimizeResult.expectedSharpe ?? 0).toFixed(2)}
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={<Text type="secondary" style={{ fontSize: 12 }}>最大回撤</Text>}>
                            <Text style={{ color: '#ef4444', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                              {((optimizeResult.maxDrawdown ?? 0) * 100).toFixed(2)}%
                            </Text>
                          </Descriptions.Item>
                        </Descriptions>
                      </Card>

                      {/* Correlation Matrix */}
                      <Card
                        size="small"
                        title={<span style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.03em' }}>相关性矩阵</span>}
                        styles={{ body: { padding: 0 } }}
                        style={{ marginBottom: 16 }}
                      >
                        {(() => {
                          const corrMatrix = optimizeResult.correlationMatrix
                          if (!corrMatrix || Object.keys(corrMatrix).length === 0) {
                            return <div style={{ padding: 16 }}><Text type="secondary">暂无相关性数据</Text></div>
                          }
                          const names = Object.keys(corrMatrix)
                          const columns = [
                            { title: '', dataIndex: 'rowName', key: 'rowName', width: 120, fixed: 'left' as const, render: (v: string) => <Text strong style={{ fontSize: 11 }}>{v}</Text> },
                            ...names.map((name) => ({
                              title: <Text style={{ fontSize: 11 }}>{name.length > 8 ? name.slice(0, 8) + '…' : name}</Text>,
                              dataIndex: name,
                              key: name,
                              width: 90,
                              render: (v: number) => {
                                const color = v >= 0.7 ? '#ef4444' : v >= 0.3 ? '#f59e0b' : '#10b981'
                                return <Text style={{ color, fontFamily: 'var(--font-mono)', fontSize: 12 }}>{v.toFixed(2)}</Text>
                              },
                            })),
                          ]
                          const dataSource = names.map((rowName) => {
                            const row: Record<string, any> = { rowName, key: rowName }
                            const rowData = corrMatrix[rowName]
                            if (typeof rowData === 'object' && rowData !== null) {
                              names.forEach((colName) => {
                                row[colName] = (rowData as Record<string, number>)[colName] ?? 0
                              })
                            }
                            return row
                          })
                          return (
                            <Table
                              dataSource={dataSource}
                              columns={columns}
                              pagination={false}
                              size="small"
                              scroll={{ x: 120 + names.length * 90 }}
                              locale={{ emptyText: <Text type="secondary">暂无数据</Text> }}
                            />
                          )
                        })()}
                      </Card>
                    </>
                  )}

                  {!optimizeResult && selectedIds.length >= 2 && (
                    <div style={{ textAlign: 'center', padding: 40, color: '#71717a' }}>
                      点击"开始优化"按钮，获取最优组合权重
                    </div>
                  )}
                </>
              ),
            },
            {
              key: 'lifecycle',
              label: '生命周期建议',
              children: (
                <>
                  <Card
                    size="small"
                    title={<span style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.03em' }}>策略生命周期建议</span>}
                    styles={{ body: { padding: '12px 16px' } }}
                    style={{ marginBottom: 16 }}
                  >
                    <Space style={{ marginBottom: 12, width: '100%' }}>
                      <Select
                        placeholder="选择策略"
                        value={lifecycleStrategyId || undefined}
                        onChange={setLifecycleStrategyId}
                        style={{ minWidth: 200 }}
                        options={backtests.map((b) => ({
                          value: b.task_id,
                          label: b.strategy_name,
                        }))}
                      />
                      <Button
                        type="primary"
                        icon={<Heartbeat size={16} />}
                        loading={lifecycleLoading}
                        disabled={!lifecycleStrategyId}
                        onClick={handleLifecycle}
                      >
                        获取建议
                      </Button>
                    </Space>

                    {lifecycleResult && (
                      <>
                        {/* Advice Tag */}
                        <Alert
                          type={lifecycleResult.advice === 'enable' ? 'success' : lifecycleResult.advice === 'disable' ? 'error' : 'warning'}
                          message={
                            <Space>
                              <Tag
                                color={lifecycleResult.advice === 'enable' ? 'green' : lifecycleResult.advice === 'disable' ? 'red' : 'gold'}
                                style={{ fontSize: 13, fontWeight: 600, padding: '2px 10px' }}
                              >
                                {lifecycleResult.advice === 'enable' ? '建议启用' : lifecycleResult.advice === 'disable' ? '建议停用' : '建议调整'}
                              </Tag>
                              <Text style={{ fontSize: 12 }}>{lifecycleResult.reason}</Text>
                            </Space>
                          }
                          style={{ marginBottom: 16 }}
                          showIcon
                        />

                        {/* Metrics */}
                        <Descriptions
                          column={3}
                          size="small"
                          colon={false}
                          style={{ marginBottom: 16 }}
                        >
                          <Descriptions.Item label={<Text type="secondary" style={{ fontSize: 12 }}>近期收益</Text>}>
                            <Text style={{
                              color: (lifecycleResult.metrics.recentReturn ?? 0) >= 0 ? '#10b981' : '#ef4444',
                              fontFamily: 'var(--font-mono)',
                              fontSize: 13,
                            }}>
                              {((lifecycleResult.metrics.recentReturn ?? 0) * 100).toFixed(2)}%
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={<Text type="secondary" style={{ fontSize: 12 }}>近期夏普</Text>}>
                            <Text style={{
                              color: (lifecycleResult.metrics.recentSharpe ?? 0) >= 1 ? '#10b981' : '#f59e0b',
                              fontFamily: 'var(--font-mono)',
                              fontSize: 13,
                            }}>
                              {(lifecycleResult.metrics.recentSharpe ?? 0).toFixed(2)}
                            </Text>
                          </Descriptions.Item>
                          <Descriptions.Item label={<Text type="secondary" style={{ fontSize: 12 }}>近期最大回撤</Text>}>
                            <Text style={{ color: '#ef4444', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                              {((lifecycleResult.metrics.recentMaxDrawdown ?? 0) * 100).toFixed(2)}%
                            </Text>
                          </Descriptions.Item>
                        </Descriptions>

                        {/* Suggestions */}
                        {lifecycleResult.suggestions && lifecycleResult.suggestions.length > 0 && (
                          <div>
                            <Text strong style={{ fontSize: 12, color: '#fafafa', marginBottom: 8, display: 'block' }}>建议操作</Text>
                            <List
                              size="small"
                              dataSource={lifecycleResult.suggestions}
                              renderItem={(item: string) => (
                                <List.Item style={{ padding: '6px 0', border: 'none' }}>
                                  <Space>
                                    <ArrowRight size={12} weight="bold" style={{ color: '#3b82f6' }} />
                                    <Text style={{ fontSize: 12 }}>{item}</Text>
                                  </Space>
                                </List.Item>
                              )}
                            />
                          </div>
                        )}
                      </>
                    )}

                    {!lifecycleResult && (
                      <div style={{ textAlign: 'center', padding: 30, color: '#71717a' }}>
                        选择一个策略并点击"获取建议"，查看生命周期建议
                      </div>
                    )}
                  </Card>
                </>
              ),
            },
          ]}
        />
      )}
    </div>
  )
}
