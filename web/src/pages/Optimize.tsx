import { useState, useRef } from 'react'
import {
  Card, Button, InputNumber, Select, Typography, Table, Space, Row, Col,
  Radio, Tag, Progress, Statistic, Empty, Divider, message,
  Input,
} from 'antd'
import {
  SlidersHorizontal, Play, Stop, Trophy, ChartLineUp, DownloadSimple,
  ArrowRight, Sparkle,
} from '@phosphor-icons/react'
import ReactECharts from 'echarts-for-react'
import type { ColumnsType } from 'antd/es/table'

import { runOptimization, streamOptimizeProgress } from '../api/optimize'
import type { OptimizeConfig, OptimizerParam, OptimizeResult } from '../types'

const { Title, Text } = Typography

export default function Optimize() {
  const [params, setParams] = useState<OptimizerParam[]>([
    { name: 'fast_period', min: 5, max: 30, step: 5, value: 10 },
    { name: 'slow_period', min: 30, max: 120, step: 10, value: 60 },
    { name: 'stop_loss_pct', min: 0.01, max: 0.10, step: 0.01, value: 0.05 },
    { name: 'take_profit_pct', min: 0.02, max: 0.20, step: 0.02, value: 0.10 },
  ])

  const [method, setMethod] = useState<'grid' | 'random' | 'walkforward'>('grid')
  const [targetMetric, setTargetMetric] = useState('sharpeRatio')
  const [maxIters, setMaxIters] = useState(20)

  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState(0)
  const [results, setResults] = useState<OptimizeResult[]>([])
  const [bestResult, setBestResult] = useState<OptimizeResult | null>(null)
  const [currentParams, setCurrentParams] = useState<Record<string, number>>({})
  const abortRef = useRef(false)

  const handleStart = async () => {
    setRunning(true)
    setProgress(0)
    setResults([])
    setBestResult(null)
    abortRef.current = false

    const config: OptimizeConfig = {
      strategyId: 'dual_ma_cross',
      params,
      method,
      targetMetric,
      maxIters,
    }

    try {
      const taskId = await runOptimization(config)
      for await (const update of streamOptimizeProgress(taskId)) {
        if (abortRef.current) break
        setProgress(update.progress)
        setCurrentParams(update.currentParams)
        if (update.bestResult) setBestResult(update.bestResult)
        // Re-sort results by target metric descending
        setResults((prev) => {
          const all = [...prev]
          if (update.bestResult && !all.find((r) => r.rank === update.bestResult!.rank)) {
            all.push(update.bestResult)
          }
          return all.sort((a, b) => (b.metrics.sharpeRatio ?? 0) - (a.metrics.sharpeRatio ?? 0))
        })
      }
      setRunning(false)
      if (!abortRef.current) message.success(`优化完成！共 ${results.length} 组参数`)
    } catch (err) {
      setRunning(false)
      message.error('优化失败')
    }
  }

  const handleStop = () => {
    abortRef.current = true
    setRunning(false)
  }

  // Param grid editing helpers
  const updateParam = <K extends keyof OptimizerParam>(
    index: number, field: K, value: OptimizerParam[K]
  ) => {
    setParams((prev) =>
      prev.map((p, i) => (i === index ? { ...p, [field]: value } : p))
    )
  }

  const addParam = () => {
    setParams((prev) => [
      ...prev,
      { name: `param_${prev.length + 1}`, min: 0, max: 100, step: 1, value: 50 },
    ])
  }

  const removeParam = (index: number) => {
    setParams((prev) => prev.filter((_, i) => i !== index))
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>参数优化</Title>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Grid Search / Random Sampling / Walk-Forward Optimization
        </Text>
      </div>

      {/* Config Section */}
      <Card
        size="small"
        title={
          <span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <SlidersHorizontal size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> 参数配置
          </span>
        }
        style={{ marginBottom: 16 }}
      >
        {/* Param table */}
        <Table
          dataSource={params.map((p, i) => ({ ...p, _key: i }))}
          rowKey="_key"
          size="small"
          pagination={false}
          columns={[
            {
              title: '参数名',
              dataIndex: 'name',
              key: 'name',
              width: 130,
              render: (t: string, _: unknown, i: number) => (
                <Input
                  value={t}
                  size="small"
                  onChange={(e) => updateParam(i, 'name', e.target.value)}
                  style={{ fontFamily: 'var(--font-mono)' }}
                />
              ),
            },
            {
              title: '最小值',
              dataIndex: 'min',
              key: 'min',
              width: 80,
              render: (n: number, _, i: number) => (
                <InputNumber
                  size="small"
                  value={n}
                  onChange={(v) => updateParam(i, 'min', v ?? 0)}
                  style={{ width: '100%' }}
                />
              ),
            },
            {
              title: '最大值',
              dataIndex: 'max',
              key: 'max',
              width: 80,
              render: (n: number, _, i: number) => (
                <InputNumber
                  size="small"
                  value={n}
                  onChange={(v) => updateParam(i, 'max', v ?? 0)}
                  style={{ width: '100%' }}
                />
              ),
            },
            {
              title: '步长',
              dataIndex: 'step',
              key: 'step',
              width: 70,
              render: (n: number, _, i: number) => (
                <InputNumber
                  size="small"
                  value={n}
                  min={0.001}
                  step={0.001}
                  onChange={(v) => updateParam(i, 'step', v ?? 0)}
                  style={{ width: '100%' }}
                />
              ),
            },
            {
              title: '操作',
              key: 'action',
              width: 50,
              render: (_: unknown, __: unknown, i: number) => (
                <Button type="link" danger size="small" onClick={() => removeParam(i)}>
                  删除
                </Button>
              ),
            },
          ]}
        />
        <Button
          type="dashed"
          size="small"
          icon={<Sparkle size={12} />}
          onClick={addParam}
          style={{ marginTop: 8 }}
        >
          添加参数
        </Button>

        <Divider />

        {/* Method + Target + Iters */}
        <Row gutter={[16, 12]} align="middle">
          <Col>
            <Text type="secondary" style={{ fontSize: 11 }}>优化方式</Text>
            <Radio.Group
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              optionType="button"
              buttonStyle="solid"
              size="small"
            >
              <Radio.Button value="grid">网格搜索</Radio.Button>
              <Radio.Button value="random">随机采样</Radio.Button>
              <Radio.Button value="walkforward">滚动窗口</Radio.Button>
            </Radio.Group>
          </Col>
          <Col>
            <Text type="secondary" style={{ fontSize: 11 }}>优化目标</Text>
            <Select
              value={targetMetric}
              onChange={setTargetMetric}
              size="small"
              style={{ width: 140 }}
              options={[
                { label: '夏普比率', value: 'sharpeRatio' },
                { label: '年化收益', value: 'totalReturn' },
                { label: '最大回撤', value: 'maxDrawdown' },
                { label: '胜率', value: 'winRate' },
              ]}
            />
          </Col>
          <Col>
            <Text type="secondary" style={{ fontSize: 11 }}>最大迭代</Text>
            <InputNumber
              size="small"
              value={maxIters}
              onChange={(v) => setMaxIters(v ?? 20)}
              min={1}
              max={500}
              style={{ width: 80 }}
            />
          </Col>
          <Col flex="auto">
            <div style={{ textAlign: 'right' }}>
              {!running ? (
                <Button
                  type="primary"
                  icon={<Play weight="fill" size={14} />}
                  onClick={handleStart}
                >
                  开始优化
                </Button>
              ) : (
                <Button
                  danger
                  icon={<Stop weight="fill" size={14} />}
                  onClick={handleStop}
                >
                  停止
                </Button>
              )}
            </div>
          </Col>
        </Row>
      </Card>

      {/* Results Section */}
      {(running || results.length > 0) && (
        <Card
          size="small"
          title={
            <span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
              <ChartLineUp size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} /> 优化结果
              {running && <Tag color="processing" style={{ marginLeft: 4 }}>运行中</Tag>}
            </span>
          }
        >
          {/* Progress bar */}
          {running && (
            <div style={{ marginBottom: 16 }}>
              <Progress
                percent={progress}
                strokeColor={{ from: '#3b82f6', to: '#8b5cf6' }}
                format={(p) => `${p}% (${Math.round(p! / 100 * maxIters)}/${maxIters})`}
              />
              {Object.keys(currentParams).length > 0 && (
                <Text code style={{ fontSize: 11, marginTop: 4 }}>
                  当前: {Object.entries(currentParams).map(([k, v]) => `${k}=${v}`).join(', ')}
                </Text>
              )}
            </div>
          )}

          <Row gutter={[12, 12]}>
            {/* Scatter chart */}
            <Col xs={24} lg={14}>
              <ReactECharts
                option={{
                  tooltip: {
                    trigger: 'item',
                    formatter: (params: any) => {
                      const d = params.data
                      return `<b>#${d[3]} Rank</b><br/>Sharpe: ${d[0]?.toFixed(2)}<br/>Return: ${d[1]?.toFixed(1)}%<br/>MaxDD: ${d[2]?.toFixed(1)}%<br/>` +
                        Object.entries(d[4] || {}).map(([k, v]) => `${k}=${v}`).join('<br/>')
                    },
                  },
                  grid: { left: 56, right: 16, top: 16, bottom: 36 },
                  xAxis: {
                    type: 'value',
                    name: 'Max Drawdown (%)',
                    nameLocation: 'center',
                    nameGap: 28,
                    axisLabel: {
                      formatter: (v: number) => `${v}%`,
                      color: 'var(--color-text-tertiary)',
                      fontSize: 10,
                    },
                    axisLine: { lineStyle: { color: 'var(--color-border-default)' } },
                    splitLine: { lineStyle: { color: 'var(--color-bg-surface)' } },
                  },
                  yAxis: {
                    type: 'value',
                    name: 'Sharpe Ratio',
                    nameLocation: 'center',
                    nameGap: 36,
                    axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
                    axisLine: { lineStyle: { color: 'var(--color-border-default)' } },
                    splitLine: { lineStyle: { color: 'var(--color-bg-surface)' } },
                  },
                  series: [
                    {
                      type: 'scatter',
                      symbolSize: (data: any[]) =>
                        Math.max(6, Math.min(24, ((data[1] ?? 0) / 60) * 20)),
                      data: results.map((r) => [
                        r.metrics.maxDrawdown ?? 0,
                        r.metrics.sharpeRatio ?? 0,
                        r.metrics.totalReturn ?? 0,
                        r.rank,
                        r.params,
                      ]),
                      itemStyle: {
                        color: (params: any) => {
                          const rank = params.data[3]
                          return rank === 1 ? '#f59e0b' : 'var(--color-brand-primary)'
                        },
                        opacity: 0.75,
                      },
                      emphasis: {
                        itemStyle: { opacity: 1, shadowBlur: 10, shadowColor: 'rgba(59,130,246,0.3)' },
                      },
                    },
                  ],
                  animation: false,
                }}
                style={{ height: 340 }}
                notMerge={true}
              />
            </Col>

            {/* Ranking table */}
            <Col xs={24} lg={10}>
              <Table<OptimizeResult>
                dataSource={results.slice(0, 10)}
                rowKey="rank"
                size="small"
                pagination={false}
                scroll={{ y: 300 }}
                columns={[
                  {
                    title: '#',
                    dataIndex: 'rank',
                    key: 'rank',
                    width: 36,
                    align: 'center',
                    render: (n: number) =>
                      n === 1 ? (
                        <Trophy size={14} weight="fill" style={{ color: '#f59e0b' }} />
                      ) : (
                        n
                      ),
                  },
                  {
                    title: 'Sharpe',
                    dataIndex: ['metrics', 'sharpeRatio'],
                    key: 'sr',
                    width: 65,
                    render: (v: number) => (
                      <span
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontWeight: v >= 1.5 ? 600 : 400,
                        }}
                      >
                        {v?.toFixed(2)}
                      </span>
                    ),
                  },
                  {
                    title: 'Return',
                    dataIndex: ['metrics', 'totalReturn'],
                    key: 'ret',
                    width: 65,
                    render: (v: number) => (
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{v?.toFixed(1)}%</span>
                    ),
                  },
                  {
                    title: 'MaxDD',
                    dataIndex: ['metrics', 'maxDrawdown'],
                    key: 'dd',
                    width: 65,
                    render: (v: number) => (
                      <span style={{ fontFamily: 'var(--font-mono)', color: '#ef4444' }}>
                        {v?.toFixed(1)}%
                      </span>
                    ),
                  },
                  {
                    title: 'WinRate',
                    dataIndex: ['metrics', 'winRate'],
                    key: 'wr',
                    width: 60,
                    render: (v: number) => (
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{v?.toFixed(1)}%</span>
                    ),
                  },
                  {
                    title: 'Trades',
                    dataIndex: ['metrics', 'totalTrades'],
                    key: 'tr',
                    width: 55,
                    render: (v: number) => v?.toLocaleString(),
                  },
                ] as ColumnsType<OptimizeResult>}
              />
            </Col>
          </Row>

          {/* Best result detail card */}
          {bestResult && !running && (
            <div
              style={{
                marginTop: 16,
                padding: '16px 20px',
                borderRadius: 8,
                background:
                  'linear-gradient(135deg, rgba(245,158,11,0.08), rgba(59,130,246,0.06))',
                border: '1px solid rgba(245,158,11,0.25)',
              }}
            >
              <Row gutter={[24, 12]} align="middle">
                <Col flex="auto">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <Trophy size={22} weight="fill" style={{ color: '#f59e0b' }} />
                    <Text strong style={{ fontSize: 14 }}>
                      最佳参数组合 (Rank #{bestResult.rank})
                    </Text>
                  </div>
                  <Text code style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                    {Object.entries(bestResult.params)
                      .map(([k, v]) => `${k}=${v}`)
                      .join(',  ')}
                  </Text>
                </Col>
                <Col>
                  <Space size={16}>
                    <Statistic
                      title="Sharpe"
                      value={bestResult.metrics.sharpeRatio}
                      precision={2}
                      valueStyle={{ fontSize: 16, color: '#f59e0b' }}
                    />
                    <Statistic
                      title="年化收益"
                      value={bestResult.metrics.totalReturn}
                      precision={1}
                      suffix="%"
                      valueStyle={{ fontSize: 14 }}
                    />
                    <Statistic
                      title="最大回撤"
                      value={bestResult.metrics.maxDrawdown}
                      precision={1}
                      suffix="%"
                      valueStyle={{ fontSize: 14, color: '#ef4444' }}
                    />
                    <Statistic
                      title="胜率"
                      value={bestResult.metrics.winRate}
                      precision={1}
                      suffix="%"
                      valueStyle={{ fontSize: 14 }}
                    />
                  </Space>
                </Col>
              </Row>
              <div style={{ marginTop: 12, textAlign: 'right' }}>
                <Space>
                  <Button size="small" icon={<DownloadSimple size={14} />}>
                    导出结果
                  </Button>
                  <Button type="primary" size="small" icon={<ArrowRight size={14} />}>
                    应用到回测
                  </Button>
                </Space>
              </div>
            </div>
          )}

          {/* Empty state for no results yet but running */}
          {running && results.length === 0 && (
            <Empty description="正在计算中..." image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </Card>
      )}

      {/* Initial empty state */}
      {!running && results.length === 0 && (
        <Card size="small">
          <Empty
            image={
              <SlidersHorizontal size={64} weight="thin" style={{ opacity: 0.25 }} />
            }
            description={
              <span>
                配置参数范围后点击<Text type="secondary">「开始优化」</Text>运行参数搜索
              </span>
            }
          />
        </Card>
      )}
    </div>
  )
}
