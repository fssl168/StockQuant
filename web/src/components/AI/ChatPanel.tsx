import { useState, useRef, useEffect, useMemo } from 'react'
import { Input, Button, List, Avatar, Typography, Card } from 'antd'
import { PaperPlaneTilt, User, ChatCircleText, Wrench, CheckCircle } from '@phosphor-icons/react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'
import ReactECharts from 'echarts-for-react'
import SignalCard from './SignalCard'

const { Text, Paragraph } = Typography

// 配置 marked v15 使用 highlight.js 高亮代码块
const renderer = new marked.Renderer()
renderer.code = ({ text, lang }: { text: string; lang?: string }) => {
  const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
  const highlighted = hljs.highlight(text, { language }).value
  return `<pre><code class="hljs language-${language}">${highlighted}</code></pre>`
}
marked.use({ renderer, breaks: true, gfm: true })

function renderMarkdown(content: string): string {
  return DOMPurify.sanitize(marked.parse(content) as string)
}

/** Parse ```chart-json ... ``` blocks from content and return mixed segments */
type ChartJsonSegment =
  | { type: 'markdown'; html: string }
  | { type: 'chart'; option: Record<string, unknown> }
  | { type: 'chart_error'; raw: string }

function renderChartBlock(content: string): ChartJsonSegment[] {
  const segments: ChartJsonSegment[] = []
  const regex = /```chart-json\s*\n([\s\S]*?)```/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(content)) !== null) {
    // Markdown before this chart block
    if (match.index > lastIndex) {
      const md = content.slice(lastIndex, match.index)
      segments.push({ type: 'markdown', html: renderMarkdown(md) })
    }

    // Try to parse chart JSON
    const jsonStr = match[1].trim()
    try {
      const parsed = JSON.parse(jsonStr)
      segments.push({ type: 'chart', option: parsed })
    } catch {
      segments.push({ type: 'chart_error', raw: jsonStr })
    }

    lastIndex = regex.lastIndex
  }

  // Remaining markdown after last chart block
  if (lastIndex < content.length) {
    const md = content.slice(lastIndex)
    segments.push({ type: 'markdown', html: renderMarkdown(md) })
  }

  // If no chart-json blocks found, return entire content as markdown
  if (segments.length === 0) {
    segments.push({ type: 'markdown', html: renderMarkdown(content) })
  }

  return segments
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  type?: 'text' | 'tool_call' | 'tool_result'
  toolName?: string
  toolParams?: Record<string, unknown>
  toolResult?: unknown
}

interface ChatPanelProps {
  messages: Message[]
  streamingContent?: string
  isStreaming?: boolean
  onSend: (message: string) => void
  mode?: 'general' | 'strategy' | 'analysis' | 'monitor' | 'decision' | 'indicator'
}

interface ChartRendererProps {
  chartOption: Record<string, unknown>
}

function ChartRenderer({ chartOption }: ChartRendererProps) {
  const option = useMemo(() => {
    // Normalize chart options to dark theme
    const opt = { ...chartOption }
    if (!opt.backgroundColor) opt.backgroundColor = 'transparent'
    if (!opt.grid) {
      opt.grid = { left: 64, right: 16, top: 28, bottom: 24 }
    }
    // Dark theme overrides
    if (opt.xAxis) {
      if (typeof opt.xAxis === 'object') opt.xAxis = { ...(opt.xAxis as object) }
      const xAxis = opt.xAxis as Record<string, unknown>
      if (!xAxis.axisLine) xAxis.axisLine = { lineStyle: { color: '#27272a' } }
      if (!xAxis.axisLabel) xAxis.axisLabel = { color: '#a1a1aa', fontSize: 10 }
    }
    if (opt.yAxis) {
      if (typeof opt.yAxis === 'object') opt.yAxis = { ...(opt.yAxis as object) }
      const yAxis = opt.yAxis as Record<string, unknown>
      if (!yAxis.axisLine) yAxis.axisLine = { show: false }
      if (!yAxis.splitLine) yAxis.splitLine = { lineStyle: { color: '#18181b' } }
      if (!yAxis.axisLabel) yAxis.axisLabel = { color: '#a1a1aa', fontSize: 10 }
    }
    if (!opt.tooltip) {
      opt.tooltip = {
        backgroundColor: '#18181b',
        borderColor: '#27272a',
        textStyle: { color: '#fafafa', fontSize: 12 },
      }
    }
    return opt as Record<string, unknown>
  }, [chartOption])

  return (
    <div style={{ marginTop: 8, borderRadius: 6, overflow: 'hidden', border: '1px solid #27272a' }}>
      <ReactECharts option={option} style={{ height: 300, width: '100%' }} opts={{ renderer: 'canvas' }} />
    </div>
  )
}

/** Inline chart renderer for chart-json blocks (400x300, supports line/bar/pie) */
function InlineChartRenderer({ chartSpec }: { chartSpec: Record<string, unknown> }) {
  const option = useMemo(() => {
    const chartType = (chartSpec.chartType || chartSpec.type || 'line') as string
    const title = (chartSpec.title || '') as string
    const data = chartSpec.data as Array<Record<string, unknown>> | undefined
    const series = chartSpec.series as Array<Record<string, unknown>> | undefined

    // If the spec is already an ECharts option, use it directly
    if (series || chartSpec.xAxis || chartSpec.yAxis) {
      const opt = { ...chartSpec }
      if (!opt.backgroundColor) opt.backgroundColor = 'transparent'
      if (!opt.tooltip) {
        opt.tooltip = {
          backgroundColor: '#18181b',
          borderColor: '#27272a',
          textStyle: { color: '#fafafa', fontSize: 12 },
        }
      }
      return opt as Record<string, unknown>
    }

    // Build ECharts option from simplified spec
    const opt: Record<string, unknown> = {
      backgroundColor: 'transparent',
      tooltip: {
        backgroundColor: '#18181b',
        borderColor: '#27272a',
        textStyle: { color: '#fafafa', fontSize: 12 },
      },
    }

    if (title) {
      opt.title = { text: title, textStyle: { color: '#fafafa', fontSize: 13 }, left: 'center' }
    }

    if (chartType === 'pie') {
      const pieData = (data || []).map((d) => ({
        name: (d.name || d.label || '') as string,
        value: d.value as number,
      }))
      opt.series = [{
        type: 'pie',
        radius: '60%',
        data: pieData,
        label: { color: '#a1a1aa' },
        itemStyle: { borderColor: '#18181b', borderWidth: 2 },
      }]
    } else {
      // line / bar
      const categories = (data || []).map((d) => (d.date != null ? String(d.date) : String(d.index ?? '')))
      const values = (data || []).map((d) => d.value as number)

      opt.xAxis = {
        type: 'category',
        data: categories,
        axisLine: { lineStyle: { color: '#27272a' } },
        axisLabel: { color: '#a1a1aa', fontSize: 10 },
      }
      opt.yAxis = {
        type: 'value',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#18181b' } },
        axisLabel: { color: '#a1a1aa', fontSize: 10 },
      }
      opt.grid = { left: 64, right: 16, top: title ? 40 : 28, bottom: 24 }

      const mainSeries: Record<string, unknown> = {
        type: chartType === 'bar' ? 'bar' : 'line',
        data: values,
        smooth: chartType === 'line',
      }
      const allSeries = [mainSeries]

      // Add EMA line if present
      if (data && data.length > 0 && 'ema10' in data[0]) {
        allSeries.push({
          type: 'line',
          data: data.map((d) => d.ema10 as number),
          smooth: true,
          lineStyle: { width: 1, type: 'dashed' },
          itemStyle: { opacity: 0 },
          showSymbol: false,
        })
      }

      opt.series = allSeries
    }

    return opt
  }, [chartSpec])

  return (
    <div style={{ marginTop: 8, borderRadius: 6, overflow: 'hidden', border: '1px solid #27272a' }}>
      <ReactECharts option={option} style={{ height: 300, width: '100%' }} opts={{ renderer: 'canvas' }} />
    </div>
  )
}

export default function ChatPanel({ messages, streamingContent = '', isStreaming = false, onSend, mode = 'general' }: ChatPanelProps) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  const handleSend = () => {
    const text = input.trim()
    if (!text) return
    onSend(text)
    setInput('')
  }

  /** Detect trading signal keywords in assistant message content */
  function detectSignalType(content: string): 'BUY' | 'SELL' | null {
    const upper = content.toUpperCase()
    if (/买入|BUY/.test(upper)) return 'BUY'
    if (/卖出|SELL/.test(upper)) return 'SELL'
    return null
  }

  /** Render tool_call message */
  function renderToolCall(msg: Message) {
    return (
      <Card
        size="small"
        style={{ marginTop: 6, borderLeft: '3px solid var(--color-brand-primary)' }}
        styles={{ body: { padding: '8px 12px' } }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: msg.toolParams && Object.keys(msg.toolParams).length > 0 ? 6 : 0 }}>
          <Wrench size={14} weight="fill" style={{ color: 'var(--color-brand-primary)' }} />
          <Text strong style={{ fontSize: 12 }}>{msg.toolName ?? '工具调用'}</Text>
        </div>
        {msg.toolParams && Object.keys(msg.toolParams).length > 0 && (
          <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {JSON.stringify(msg.toolParams, null, 2)}
          </div>
        )}
      </Card>
    )
  }

  /** Render tool_result message */
  function renderToolResult(msg: Message) {
    const result = msg.toolResult
    let resultContent: React.ReactNode
    let hasChart = false

    // Check if result contains chart_option (ECharts option JSON from generate_chart_json)
    if (typeof result === 'object' && result !== null && 'chart_option' in result) {
      const chartOption = result.chart_option as Record<string, unknown>
      if (chartOption && typeof chartOption === 'object') {
        resultContent = <ChartRenderer chartOption={chartOption} />
        hasChart = true
      }
    }
    if (!hasChart) {
      if (Array.isArray(result)) {
        resultContent = (
          <ul style={{ margin: 0, paddingLeft: 16, fontSize: 11 }}>
            {result.map((item, i) => (
              <li key={i} style={{ color: 'var(--color-text-secondary)' }}>
                {typeof item === 'object' ? JSON.stringify(item) : String(item)}
              </li>
            ))}
          </ul>
        )
      } else if (typeof result === 'object' && result !== null) {
        resultContent = (
          <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {JSON.stringify(result, null, 2)}
          </div>
        )
      } else {
        resultContent = <Paragraph style={{ fontSize: 11, margin: 0, color: 'var(--color-text-secondary)' }}>{String(result ?? '')}</Paragraph>
      }
    }
    return (
      <Card
        size="small"
        style={{ marginTop: 6, borderLeft: '3px solid #52c41a' }}
        styles={{ body: { padding: '8px 12px' } }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
          <CheckCircle size={14} weight="fill" style={{ color: '#52c41a' }} />
          <Text strong style={{ fontSize: 12 }}>执行结果</Text>
        </div>
        {resultContent}
      </Card>
    )
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
      <div style={{ flex: 1, overflowY: 'auto', paddingRight: 8 }}>
        {messages.length === 0 && !isStreaming && (
          mode === 'indicator' ? (
            <div style={{ textAlign: 'center', color: 'var(--color-text-tertiary)', marginTop: 60 }}>
              <ChatCircleText size={48} weight="duotone" style={{ color: 'var(--color-brand-primary)', marginBottom: 16 }} />
              <div style={{ fontSize: 14, color: 'var(--color-text-secondary)', marginBottom: 8 }}>
                🔍 指标发现模式 — 输入市场状态或股票代码，AI 将推荐最适合的技术指标
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 8, marginTop: 16 }}>
                {[
                  '当前市场适合什么指标？',
                  'sh600519 适合哪些指标？',
                  '趋势类指标推荐',
                  '震荡类指标推荐',
                ].map((q) => (
                  <Button
                    key={q}
                    size="small"
                    onClick={() => { setInput(q) }}
                    style={{ borderRadius: 16, fontSize: 12 }}
                  >
                    {q}
                  </Button>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', color: 'var(--color-text-tertiary)', marginTop: 100 }}>
              <ChatCircleText size={48} weight="duotone" style={{ color: 'var(--color-brand-primary)', marginBottom: 16 }} />
              <div style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>开始与 AI 对话</div>
              <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
                试试: "查询 sh600519 最近 30 天" 或 "解读我的回测结果"
              </div>
            </div>
          )
        )}
        <List
          dataSource={messages}
          renderItem={(msg) => {
            const isToolCall = msg.type === 'tool_call'
            const isToolResult = msg.type === 'tool_result'
            const signalType = msg.role === 'assistant' && !isToolCall && !isToolResult ? detectSignalType(msg.content) : null

            return (
            <List.Item style={{
              paddingTop: 12, paddingBottom: 12,
              borderBottom: '1px solid var(--color-bg-surface)',
              background: msg.role === 'user' ? 'var(--color-brand-subtle)' : 'transparent',
              borderRadius: 4,
            }}>
              <List.Item.Meta
                avatar={
                  <Avatar style={{
                    background: isToolCall ? '#722ed1' : isToolResult ? '#52c41a' : msg.role === 'user' ? 'var(--color-bg-elevated)' : 'var(--color-brand-primary)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    width: 28, height: 28,
                  }}>
                    {isToolCall ? <Wrench size={16} weight="fill" /> : isToolResult ? <CheckCircle size={16} weight="fill" /> : msg.role === 'user' ? <User size={16} weight="fill" /> : <ChatCircleText size={16} weight="fill" />}
                  </Avatar>
                }
                title={<Text strong style={{ fontSize: 12, color: isToolCall ? '#722ed1' : isToolResult ? '#52c41a' : msg.role === 'user' ? 'var(--color-brand-primary)' : 'var(--color-text-primary)' }}>
                  {isToolCall ? `工具: ${msg.toolName ?? '调用'}` : isToolResult ? '工具结果' : msg.role === 'user' ? '您' : 'AI 助手'}
                </Text>}
                description={
                  <div>
                    {isToolCall ? renderToolCall(msg) : isToolResult ? renderToolResult(msg) : (
                      <>
                        {msg.role === 'assistant'
                          ? renderChartBlock(msg.content).map((seg, idx) => {
                              if (seg.type === 'chart') {
                                return <InlineChartRenderer key={`chart-${idx}`} chartSpec={seg.option} />
                              }
                              if (seg.type === 'chart_error') {
                                return (
                                  <pre key={`chart-err-${idx}`} style={{ marginTop: 8, padding: 8, borderRadius: 4, background: '#18181b', color: '#a1a1aa', fontSize: 11, overflow: 'auto', border: '1px solid #27272a' }}>
                                    <code>{seg.raw}</code>
                                  </pre>
                                )
                              }
                              return (
                                <div
                                  key={`md-${idx}`}
                                  style={{ marginTop: 6, fontSize: 13, lineHeight: 1.7, color: 'var(--color-text-secondary)' }}
                                  dangerouslySetInnerHTML={{ __html: seg.html }}
                                />
                              )
                            })
                          : (
                            <div
                              style={{ marginTop: 6, fontSize: 13, lineHeight: 1.7, color: 'var(--color-text-secondary)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
                              dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
                            />
                          )
                        }
                      </>
                    )}
                    {signalType && (
                      <div style={{ marginTop: 8 }}>
                        <SignalCard
                          type={signalType}
                          title={signalType === 'BUY' ? '买入信号' : '卖出信号'}
                          message={msg.content.slice(0, 60)}
                          time={new Date(msg.timestamp).toLocaleTimeString()}
                          confidence={undefined}
                        />
                      </div>
                    )}
                  </div>
                }
              />
              <span style={{ color: 'var(--color-text-disabled)', fontSize: 10, fontFamily: 'var(--font-mono)', marginLeft: 12, alignSelf: 'start', marginTop: 4 }}>
                {new Date(msg.timestamp).toLocaleTimeString()}
              </span>
            </List.Item>
            )
          }}
        />
        {/* Streaming message */}
        {isStreaming && (
          <List.Item style={{ paddingTop: 12, paddingBottom: 12, borderBottom: '1px solid var(--color-bg-surface)', borderRadius: 4 }}>
            <List.Item.Meta
              avatar={<Avatar style={{ background: 'var(--color-brand-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28 }}>
                <ChatCircleText size={16} weight="fill" />
              </Avatar>}
              title={<Text strong style={{ fontSize: 12, color: 'var(--color-text-primary)' }}>AI 助手</Text>}
              description={
                streamingContent ? (
                  <div
                    style={{ marginTop: 6, fontSize: 13, lineHeight: 1.7, color: 'var(--color-text-secondary)' }}
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(streamingContent) }}
                  />
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {[0, 1, 2].map(i => (
                        <div key={i} style={{
                          width: 6, height: 6, borderRadius: '50%',
                          background: 'var(--color-brand-primary)',
                          animation: `thinking-bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
                        }} />
                      ))}
                    </div>
                    <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>正在思考...</span>
                  </div>
                )
              }
            />
          </List.Item>
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={handleSend}
          placeholder="输入消息..."
          size="large"
          disabled={isStreaming}
          allowClear
        />
        <Button
          type="primary"
          icon={<PaperPlaneTilt size={18} />}
          onClick={handleSend}
          size="large"
          loading={isStreaming}
          style={{ minWidth: 48 }}
        />
      </div>

      <style>{`
        @keyframes thinking-bounce {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  )
}
