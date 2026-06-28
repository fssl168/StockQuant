/**
 * Order splitter configuration component.
 *
 * Supports three strategies:
 * - 冰山订单 (Iceberg): showQty / hiddenQty
 * - 定时分批 (Time-sliced): sliceCount / intervalSec / randomize
 * - 自定义 (Custom): free-form quantity input per slice
 *
 * Displays estimated submission count and a preview of the slice breakdown.
 */

import { useMemo, useState } from 'react'
import {
  Card,
  Input,
  InputNumber,
  Typography,
  Space,
  Tag,
  Segmented,
  Switch,
  Row,
  Col,
  Table,
} from 'antd'
import {
  Lightning,
  Clock,
  Repeat,
  FileText,
} from '@phosphor-icons/react'
import { splitIceberg, type IcebergSlice } from '@/utils/icebergOrder'
import { splitByTime } from '@/utils/timeSlicer'

const { Text } = Typography

type StrategyType = 'iceberg' | 'timeSliced' | 'custom'

interface OrderSplitterProps {
  /** Total quantity to split */
  totalQty: number

  /** Optional: pre-selected strategy */
  defaultStrategy?: StrategyType
}

export default function OrderSplitter({
  totalQty,
  defaultStrategy = 'iceberg',
}: OrderSplitterProps) {
  const [strategy, setStrategy] = useState<StrategyType>(defaultStrategy)

  // Iceberg state
  const [showQty, setShowQty] = useState(500)
  const [hiddenQty, setHiddenQty] = useState(1000)
  const minShowQty = 100

  // Time-sliced state
  const [sliceCount, setSliceCount] = useState(5)
  const [intervalSec, setIntervalSec] = useState(300)
  const [randomize, setRandomize] = useState(false)
  const [randomizeRangeSec, setRandomizeRangeSec] = useState(60)

  // Custom state
  const [customQty, setCustomQty] = useState<string>('')

  // --- Iceberg ---
  const icebergSlices = useMemo<IcebergSlice[]>(() => {
    if (totalQty <= 0 || showQty <= 0) return []
    return splitIceberg(totalQty, {
      showQty: Math.max(showQty, minShowQty),
      hiddenQty: Math.max(hiddenQty, 0),
      minShowQty,
    })
  }, [totalQty, showQty, hiddenQty])

  const icebergVisibleCount = useMemo(
    () => icebergSlices.filter((s) => s.isVisible).length,
    [icebergSlices],
  )

  // --- Time-sliced ---
  const timeSlices = useMemo(() => {
    if (totalQty <= 0 || sliceCount <= 0) return []
    return splitByTime({
      totalQty,
      sliceCount,
      intervalSec,
      randomize,
      randomizeRangeSec,
    })
  }, [totalQty, sliceCount, intervalSec, randomize, randomizeRangeSec])

  // --- Custom ---
  const customParts = useMemo<number[]>(() => {
    if (!customQty.trim()) return []
    return customQty
      .split(/[,\n]/)
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !Number.isNaN(n) && n > 0)
  }, [customQty])

  const customTotal = useMemo(
    () => customParts.reduce((sum, n) => sum + n, 0),
    [customParts],
  )

  // --- Preview table columns ---
  const icebergColumns = [
    {
      title: '编号',
      dataIndex: 'sequence',
      key: 'sequence',
      width: 60,
      render: (n: number) => <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{n}</Text>,
    },
    {
      title: '数量',
      dataIndex: 'qty',
      key: 'qty',
      width: 100,
      render: (n: number) => <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{n.toLocaleString()}</Text>,
    },
    {
      title: '可见性',
      dataIndex: 'isVisible',
      key: 'isVisible',
      width: 100,
      render: (v: boolean) => (
        <Tag color={v ? 'green' : 'default'} style={{ fontSize: 10 }}>
          {v ? '可见' : '隐藏'}
        </Tag>
      ),
    },
  ]

  const timeColumns = [
    {
      title: '编号',
      key: 'index',
      width: 60,
      render: (_: unknown, __: unknown, i: number) => (
        <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{i + 1}</Text>
      ),
    },
    {
      title: '数量',
      dataIndex: 'qty',
      key: 'qty',
      width: 100,
      render: (n: number) => <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{n.toLocaleString()}</Text>,
    },
    {
      title: '执行时间',
      dataIndex: 'execAt',
      key: 'execAt',
      render: (_: unknown, r: { execAt: Date }) => (
        <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
          {r.execAt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </Text>
      ),
    },
  ]

  const customColumns = [
    {
      title: '编号',
      key: 'index',
      width: 60,
      render: (_: unknown, __: unknown, i: number) => (
        <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{i + 1}</Text>
      ),
    },
    {
      title: '数量',
      dataIndex: 'qty',
      key: 'qty',
      width: 100,
      render: (n: number) => <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{n.toLocaleString()}</Text>,
    },
  ]

  return (
    <Card
      size="small"
      title={
        <span style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Repeat size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />
          订单拆分器
          {totalQty > 0 && (
            <Tag color="blue" style={{ fontSize: 10, marginLeft: 4 }}>
              总量 {totalQty.toLocaleString()} 股
            </Tag>
          )}
        </span>
      }
    >
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        {/* Strategy selector */}
        <Segmented
          size="small"
          value={strategy}
          onChange={(v) => setStrategy(v as StrategyType)}
          style={{ width: '100%' }}
          options={[
            {
              label: '冰山订单',
              value: 'iceberg',
              icon: <Lightning size={14} />,
            },
            {
              label: '定时分批',
              value: 'timeSliced',
              icon: <Clock size={14} />,
            },
            {
              label: '自定义',
              value: 'custom',
              icon: <FileText size={14} />,
            },
          ]}
        />

        {/* --- Iceberg config --- */}
        {strategy === 'iceberg' && (
          <Space direction="vertical" style={{ width: '100%' }} size={8}>
            <Row gutter={[12, 0]}>
              <Col span={12}>
                <Text type="secondary" style={{ fontSize: 11 }}>每次显示挂单量</Text>
                <InputNumber
                  value={showQty}
                  onChange={(v) => setShowQty(v ?? 100)}
                  size="small"
                  min={minShowQty}
                  step={100}
                  style={{ width: '100%', marginTop: 4 }}
                  formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                />
              </Col>
              <Col span={12}>
                <Text type="secondary" style={{ fontSize: 11 }}>隐藏量</Text>
                <InputNumber
                  value={hiddenQty}
                  onChange={(v) => setHiddenQty(v ?? 0)}
                  size="small"
                  min={0}
                  step={100}
                  style={{ width: '100%', marginTop: 4 }}
                  formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                />
              </Col>
            </Row>

            {/* Summary */}
            <div
              style={{
                padding: '6px 10px',
                borderRadius: 4,
                background: 'var(--color-bg-elevated)',
                border: '1px solid var(--color-border-default)',
                fontSize: 11,
                display: 'flex',
                justifyContent: 'space-between',
              }}
            >
              <Text type="secondary">预计提交次数</Text>
              <Text strong style={{ fontFamily: 'var(--font-mono)' }}>
                {icebergSlices.length} 次
                <span style={{ color: '#10b981', marginLeft: 4 }}>
                  可见 {icebergVisibleCount} 次
                </span>
                <span style={{ color: 'var(--color-text-tertiary)', marginLeft: 4 }}>
                  隐藏 {icebergSlices.length - icebergVisibleCount} 次
                </span>
              </Text>
            </div>

            {/* Preview */}
            {icebergSlices.length > 0 && (
              <Table
                dataSource={icebergSlices}
                columns={icebergColumns}
                rowKey={(r) => r.sequence}
                size="small"
                pagination={false}
                scroll={{ y: 200 }}
                summary={() => (
                  <Table.Summary fixed>
                    <Table.Summary.Row>
                      <Table.Summary.Cell index={0}>
                        <Text strong>合计</Text>
                      </Table.Summary.Cell>
                      <Table.Summary.Cell index={1}>
                        <Text strong style={{ fontFamily: 'var(--font-mono)' }}>
                          {icebergSlices.reduce((s, r) => s + r.qty, 0).toLocaleString()}
                        </Text>
                      </Table.Summary.Cell>
                      <Table.Summary.Cell index={2} />
                    </Table.Summary.Row>
                  </Table.Summary>
                )}
              />
            )}
          </Space>
        )}

        {/* --- Time-sliced config --- */}
        {strategy === 'timeSliced' && (
          <Space direction="vertical" style={{ width: '100%' }} size={8}>
            <Row gutter={[12, 0]}>
              <Col span={8}>
                <Text type="secondary" style={{ fontSize: 11 }}>分批次数</Text>
                <InputNumber
                  value={sliceCount}
                  onChange={(v) => setSliceCount(v ?? 1)}
                  size="small"
                  min={1}
                  max={100}
                  style={{ width: '100%', marginTop: 4 }}
                />
              </Col>
              <Col span={8}>
                <Text type="secondary" style={{ fontSize: 11 }}>间隔（秒）</Text>
                <InputNumber
                  value={intervalSec}
                  onChange={(v) => setIntervalSec(v ?? 60)}
                  size="small"
                  min={1}
                  max={86400}
                  style={{ width: '100%', marginTop: 4 }}
                  formatter={(v) => `${v}`}
                  parser={(v) => parseInt(v || '0', 10)}
                />
              </Col>
              <Col span={8}>
                <Text type="secondary" style={{ fontSize: 11 }}>随机偏移</Text>
                <Switch size="small" checked={randomize} onChange={setRandomize} style={{ marginTop: 6 }} />
              </Col>
            </Row>

            {randomize && (
              <Row>
                <Col span={24}>
                  <Text type="secondary" style={{ fontSize: 11 }}>偏移范围（秒）</Text>
                  <InputNumber
                    value={randomizeRangeSec}
                    onChange={(v) => setRandomizeRangeSec(v ?? 30)}
                    size="small"
                    min={0}
                    max={intervalSec / 2}
                    style={{ width: '100%', marginTop: 4 }}
                  />
                </Col>
              </Row>
            )}

            {/* Summary */}
            <div
              style={{
                padding: '6px 10px',
                borderRadius: 4,
                background: 'var(--color-bg-elevated)',
                border: '1px solid var(--color-border-default)',
                fontSize: 11,
                display: 'flex',
                justifyContent: 'space-between',
              }}
            >
              <Text type="secondary">预计提交次数</Text>
              <Text strong style={{ fontFamily: 'var(--font-mono)' }}>
                {timeSlices.length} 次
              </Text>
            </div>

            {/* Preview */}
            {timeSlices.length > 0 && (
              <Table
                dataSource={timeSlices}
                columns={timeColumns}
                rowKey={(_, i) => i ?? 0}
                size="small"
                pagination={false}
                scroll={{ y: 200 }}
                summary={() => (
                  <Table.Summary fixed>
                    <Table.Summary.Row>
                      <Table.Summary.Cell index={0}>
                        <Text strong>合计</Text>
                      </Table.Summary.Cell>
                      <Table.Summary.Cell index={1}>
                        <Text strong style={{ fontFamily: 'var(--font-mono)' }}>
                          {timeSlices.reduce((s, r) => s + r.qty, 0).toLocaleString()}
                        </Text>
                      </Table.Summary.Cell>
                      <Table.Summary.Cell index={2} />
                    </Table.Summary.Row>
                  </Table.Summary>
                )}
              />
            )}
          </Space>
        )}

        {/* --- Custom config --- */}
        {strategy === 'custom' && (
          <Space direction="vertical" style={{ width: '100%' }} size={8}>
            <Text type="secondary" style={{ fontSize: 11 }}>
              输入每笔数量，用逗号或换行分隔
            </Text>
            <Input.TextArea
              value={customQty}
              onChange={(e) => setCustomQty(e.target.value)}
              placeholder="e.g. 500, 300, 200 或每行一个数字"
              autoSize={{ minRows: 3, maxRows: 6 }}
              style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}
            />

            {customParts.length > 0 && (
              <>
                <div
                  style={{
                    padding: '6px 10px',
                    borderRadius: 4,
                    background: 'var(--color-bg-elevated)',
                    border: '1px solid var(--color-border-default)',
                    fontSize: 11,
                    display: 'flex',
                    justifyContent: 'space-between',
                  }}
                >
                  <Text type="secondary">预计提交次数</Text>
                  <Text strong style={{ fontFamily: 'var(--font-mono)' }}>
                    {customParts.length} 次
                  </Text>
                </div>

                <div
                  style={{
                    padding: '6px 10px',
                    borderRadius: 4,
                    background: customTotal === totalQty ? 'rgba(16,185,129,0.08)' : 'rgba(245,158,11,0.08)',
                    border: `1px solid ${customTotal === totalQty ? 'rgba(16,185,129,0.2)' : 'rgba(245,158,11,0.2)'}`,
                    fontSize: 11,
                    display: 'flex',
                    justifyContent: 'space-between',
                  }}
                >
                  <Text style={{ color: customTotal === totalQty ? '#10b981' : '#f59e0b' }}>
                    拆分总量 {customTotal.toLocaleString()} 股
                    {customTotal !== totalQty && `（与目标差额: ${customTotal !== totalQty ? (customTotal > totalQty ? '+' : '') + (customTotal - totalQty) : 0} 股）`}
                  </Text>
                </div>

                <Table
                  dataSource={customParts.map((qty, i) => ({ qty, i }))}
                  columns={customColumns}
                  rowKey={(r) => r.i}
                  size="small"
                  pagination={false}
                  summary={() => (
                    <Table.Summary fixed>
                      <Table.Summary.Row>
                        <Table.Summary.Cell index={0}>
                          <Text strong>合计</Text>
                        </Table.Summary.Cell>
                        <Table.Summary.Cell index={1}>
                          <Text strong style={{ fontFamily: 'var(--font-mono)' }}>
                            {customTotal.toLocaleString()}
                          </Text>
                        </Table.Summary.Cell>
                      </Table.Summary.Row>
                    </Table.Summary>
                  )}
                />
              </>
            )}
          </Space>
        )}
      </Space>
    </Card>
  )
}
