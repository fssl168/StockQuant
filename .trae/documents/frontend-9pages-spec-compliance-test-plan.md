# 前端 9 页面 Spec 100% 达标 + 单元测试 实施计划

> 目标: (1) 修复 9 个页面的 Spec 缺口达到 100% 完整度; (2) 搭建前端测试基础设施并编写完整单元测试

---

## 一、当前达标率总览

| 页面 | 当前完成度 | 目标 |
|------|-----------|------|
| Dashboard | 65% | 100% |
| Backtest | 60% | 100% |
| BacktestResult | 75% | 100% |
| Strategy | 70% | 100% |
| Data | 45% | 100% |
| Monitor | 40% | 100% |
| Portfolio | 50% | 100% |
| AIChat | 60% | 100% |
| Settings | 55% | 100% |

### 全局性缺失 (影响多个页面)

| # | 缺失项 | 影响页面 | 优先级 |
|---|--------|---------|--------|
| G1 | MonthHeatmap 实现为柱状图而非热力图 | BacktestResult | P0 |
| G2 | AIChat XSS 风险 (dangerouslySetInnerHTML 无 sanitize) | AIChat | P0 |
| G3 | Backtest 提交后无跳转到结果页 | Backtest | P0 |
| G4 | Data 页面空 useEffect + K线查询无功能 | Data | P0 |
| G5 | Settings 条件显隐 (when) 未实现 | Settings | P1 |
| G6 | Strategy 更新功能缺失 | Strategy | P1 |
| G7 | AIChat SSE 实现不规范 | AIChat | P1 |
| G8 | BacktestResult AI 解读为硬编码 | BacktestResult | P1 |
| G9 | Monitor 告警规则无实际逻辑 | Monitor | P1 |
| G10 | Portfolio 全部数据硬编码 | Portfolio | P1 |
| G11 | Dashboard 数据硬编码 | Dashboard | P2 |
| G12 | Settings 未调 API | Settings | P2 |

### 代码质量问题 (需修复)

| # | 文件 | 问题 | 优先级 |
|---|------|------|--------|
| Q1 | AIChat.tsx | dangerouslySetInnerHTML XSS | P0 |
| Q2 | Data.tsx | useEffect 空操作 + K线查询无功能 | P0 |
| Q3 | BacktestResult.tsx | task 类型为 any | P1 |
| Q4 | Monitor.tsx | livePrices 闭包问题 | P1 |
| Q5 | Portfolio.tsx | 零 API 调用 | P1 |
| Q6 | Settings.tsx | Slider tooltip 双重缩放 | P1 |
| Q7 | Settings.tsx | Collapse activeKey 不响应 allExpanded | P1 |
| Q8 | Dashboard.tsx | metrics 类型为 Record<string, unknown> | P2 |
| Q9 | Backtest.tsx | 模板选择仅填充默认代码 | P2 |
| Q10 | Strategy.tsx | 模板代码与 API 层重复 | P2 |

---

## 二、实施范围

### Part A: 页面功能修复 (12 项缺口 → 0)

### Part B: 代码质量修复 (10 项问题 → 0)

### Part C: 测试基础设施搭建

### Part D: 单元测试编写 (9 页面 + 共享组件 + API + Store)

---

## 三、Step-by-Step 实施

### Step 1: 测试基础设施搭建

#### 1.1 安装依赖

```bash
cd web && npm install --save-dev vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
```

#### 1.2 vite.config.ts 追加 test 配置

在现有 `defineConfig` 中追加:

```ts
/// <reference types="vitest" />
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.ts',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    css: true,
  },
})
```

#### 1.3 src/setupTests.ts

```typescript
import '@testing-library/jest-dom/vitest'
```

#### 1.4 package.json scripts

```json
"test": "vitest run",
"test:watch": "vitest",
"test:coverage": "vitest run --coverage"
```

---

### Step 2: P0 页面功能修复

#### 2.1 G1: MonthHeatmap 改为真正的热力图

**文件**: `web/src/components/Chart/MonthHeatmap.tsx`

当前: ECharts bar chart → 改为 ECharts heatmap 类型

```typescript
// 改为 heatmap 类型
series: [{
  type: 'heatmap',
  data: monthlyData.map((v, i) => [i % 12, Math.floor(i / 12), v]),
  label: { show: true, formatter: (p) => `${p.value[2].toFixed(1)}%` },
}]
// X轴: 月份 1-12, Y轴: 年份
```

#### 2.2 G2+Q1: AIChat XSS 修复

**文件**: `web/src/pages/AIChat.tsx`

方案: 安装 `dompurify` 并在 `renderMarkdown` 中使用

```bash
npm install dompurify @types/dompurify
```

```typescript
import DOMPurify from 'dompurify'

const renderMarkdown = (text: string): string => {
  return DOMPurify.sanitize(marked(text) as string)
}
```

#### 2.3 G3: Backtest 提交后跳转结果页

**文件**: `web/src/pages/Backtest.tsx`

```typescript
import { useNavigate } from 'react-router-dom'

// 在 submitTask 成功后:
const result = await backtestApi.submit(payload)
message.success('回测任务已提交')
navigate(`/backtest/${result.task_id}`)  // 跳转到结果页
```

#### 2.4 G4+Q2: Data 页面修复

**文件**: `web/src/pages/Data.tsx`

1. 删除空 `useEffect(() => { void 0 }, [])`
2. K 线查询按钮绑定实际逻辑:
```typescript
const handleFetchKline = async () => {
  setKlineLoading(true)
  try {
    const data = await dataApi.fetchKline(klineSymbol, klineStart, klineEnd)
    setKlineData(data)
  } catch {
    message.error('K线数据获取失败')
  } finally {
    setKlineLoading(false)
  }
}
```
3. 采集日志调用 `dataApi` 而非硬编码

---

### Step 3: P1 页面功能修复

#### 3.1 G5: Settings 条件显隐 (when) 实现

**文件**: `web/src/pages/Settings.tsx`

在渲染每个配置项前检查 `when` 条件:

```typescript
const isVisible = (item: ConfigItem, allValues: Record<string, unknown>): boolean => {
  if (!item.when) return true
  const fieldValue = allValues[item.when.field]
  return item.when.values.includes(String(fieldValue))
}
```

在 Collapse 面板渲染时过滤不可见项:
```typescript
const visibleItems = group.items.filter(item => isVisible(item, formValues))
if (visibleItems.length === 0) return null  // 整组隐藏
```

#### 3.2 G6: Strategy 更新功能

**文件**: `web/src/pages/Strategy.tsx`

1. 添加 `updateStrategy` API 调用到 `api/strategy.ts`:
```typescript
export async function updateStrategy(id: string, data: { name: string; code: string }): Promise<StrategyInfo> {
  const { data: result } = await client.put(`/strategy/${id}`, data)
  return result
}
```

2. 在 Strategy.tsx 中，保存按钮区分"新建"和"更新":
```typescript
const handleSave = async () => {
  if (currentStrategyId) {
    await strategyApi.update(currentStrategyId, { name: strategyName, code: editorCode })
  } else {
    await strategyApi.create({ name: strategyName, code: editorCode })
  }
}
```

#### 3.3 G7: AIChat SSE 规范化

**文件**: `web/src/pages/AIChat.tsx` + `web/src/api/ai.ts`

1. 修改 `streamChat` 函数使用标准 SSE 解析:
```typescript
export async function* streamChat(conversationId: string, message: string): AsyncGenerator<string> {
  const response = await fetch('/api/ai/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, message }),
  })
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6)
        if (data === '[DONE]') return
        yield data
      }
    }
  }
}
```

2. AIChat.tsx 消费端改为 `for await...of`:
```typescript
for await (const chunk of streamChat(conversationId, input)) {
  streamingContent += chunk
  // update UI
}
```

#### 3.4 G8: BacktestResult AI 解读接入 API

**文件**: `web/src/pages/BacktestResult.tsx`

```typescript
const [aiInsight, setAiInsight] = useState<string>('')
const [insightLoading, setInsightLoading] = useState(false)

const fetchInsight = async () => {
  setInsightLoading(true)
  try {
    const result = await aiApi.analyzeBacktest(taskId)
    setAiInsight(result.insight)
  } catch {
    setAiInsight('AI 解读暂时不可用')
  } finally {
    setInsightLoading(false)
  }
}
```

在 `api/ai.ts` 中添加:
```typescript
export async function analyzeBacktest(backtestId: string): Promise<{ insight: string }> {
  const { data } = await client.post(`/ai/analyze-backtest/${backtestId}`)
  return data
}
```

#### 3.5 G9: Monitor 告警规则绑定逻辑

**文件**: `web/src/pages/Monitor.tsx`

```typescript
// 告警规则状态
const [alertRules, setAlertRules] = useState({
  priceChangeEnabled: false,
  priceChangeThreshold: 5,
  volumeEnabled: false,
  volumeMultiplier: 3,
})

// 在价格更新回调中检查告警
const checkAlerts = (symbol: string, prevPrice: number, newPrice: number, volume: number) => {
  if (alertRules.priceChangeEnabled) {
    const changePct = Math.abs((newPrice - prevPrice) / prevPrice * 100)
    if (changePct > alertRules.priceChangeThreshold) {
      message.warning(`${symbol} 涨跌幅 ${changePct.toFixed(2)}% 超过阈值 ${alertRules.priceChangeThreshold}%`)
    }
  }
  // volume check similar
}
```

#### 3.6 G10: Portfolio 接入 API

**文件**: `web/src/pages/Portfolio.tsx`

1. 创建 `api/portfolio.ts`:
```typescript
import client from './client'
import type { Position, AccountInfo } from '../types'

export async function getPositions(): Promise<Position[]> {
  const { data } = await client.get('/portfolio/positions')
  return data
}

export async function getAccount(): Promise<AccountInfo> {
  const { data } = await client.get('/portfolio/account')
  return data
}
```

2. Portfolio.tsx 改为从 API 加载数据 (fallback 到 mock)

---

### Step 4: 代码质量修复 (Q1-Q10)

#### Q3: BacktestResult task 类型修复

```typescript
// 替换 any
interface BacktestTask {
  id: string
  strategy_name: string
  status: string
  metrics: Record<string, number>
  equity_curve: number[]
  trades: Trade[]
}
const [task, setTask] = useState<BacktestTask | null>(null)
```

#### Q4: Monitor livePrices 闭包修复

使用 `useRef` 保存最新值:
```typescript
const livePricesRef = useRef(livePrices)
livePricesRef.current = livePrices
// setInterval 中使用 livePricesRef.current
```

#### Q5: Portfolio API 接入 (已在 G10 中处理)

#### Q6: Settings Slider tooltip 修复

```typescript
// 修复: tooltip 显示的值不应再乘 scale
tooltip: { formatter: (v) => v != null ? `${Number(v).toFixed(2)}` : '' }
```

#### Q7: Settings Collapse activeKey 修复

```typescript
// 使用受控 activeKey 而非 defaultActiveKey
const [activeKeys, setActiveKeys] = useState<string[]>(GROUPS.map(g => g.key))

// 全部展开/折叠
const toggleExpand = (expand: boolean) => {
  setActiveKeys(expand ? GROUPS.map(g => g.key) : [])
}

<Collapse activeKey={activeKeys} onChange={(keys) => setActiveKeys(keys as string[])} />
```

#### Q8: Dashboard metrics 类型修复

```typescript
interface DashboardMetrics {
  total_assets: number
  today_pnl: number
  position_count: number
  annualized_return: number
  max_drawdown: number
  sharpe_ratio: number
  [key: string]: unknown
}
const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
```

#### Q9: Backtest 模板选择修复

```typescript
const handleTemplateSelect = (templateName: string) => {
  const template = STRATEGY_TEMPLATES.find(t => t.name === templateName)
  if (template) {
    form.setFieldsValue({ strategy_code: template.code })
    setEditorCode(template.code)
  }
}
```

#### Q10: Strategy 模板去重

删除 Strategy.tsx 中的 `DEFAULT_TEMPLATES`，统一使用 `strategyApi.templates()`:
```typescript
const [templates, setTemplates] = useState([])
useEffect(() => {
  strategyApi.templates().then(setTemplates)
}, [])
```

---

### Step 5: 单元测试

#### 5.1 API 层测试

**文件**: `web/src/__tests__/api/dashboard.test.ts`
- 测试 metrics/signals/recentBacktests 返回结构
- 测试错误处理

**文件**: `web/src/__tests__/api/backtest.test.ts`
- 测试 list/get/submit/delete
- 测试 submit 后返回 task_id

**文件**: `web/src/__tests__/api/strategy.test.ts`
- 测试 CRUD + templates

**文件**: `web/src/__tests__/api/data.test.ts`
- 测试 sources/cacheStats/fetchKline

**文件**: `web/src/__tests__/api/ai.test.ts`
- 测试 streamChat AsyncGenerator
- 测试 analyzeBacktest

#### 5.2 Store 测试

**文件**: `web/src/__tests__/stores/tradingStore.test.ts` (已在之前计划中)

#### 5.3 组件测试

**文件**: `web/src/__tests__/components/MonthHeatmap.test.tsx`
- 测试渲染 heatmap 类型 (非 bar)
- 测试数据传入后正确显示

**文件**: `web/src/__tests__/components/MetricTable.test.tsx`
- 测试指标渲染
- 测试分组显示

#### 5.4 页面测试

**文件**: `web/src/__tests__/pages/Dashboard.test.tsx`
- 渲染测试: 标题、MetricCard、权益曲线、信号列表
- 数据加载: metrics API 调用
- 空状态: 无信号时显示 Empty

**文件**: `web/src/__tests__/pages/Backtest.test.tsx`
- 渲染测试: 表单字段、策略选择、日期选择器
- 提交流程: 填写表单 → 点击运行 → 跳转结果页
- 模板选择: 选择模板后代码更新

**文件**: `web/src/__tests__/pages/BacktestResult.test.tsx`
- 渲染测试: 图表、指标表、交易明细
- AI 解读: 加载状态、内容显示

**文件**: `web/src/__tests__/pages/Strategy.test.tsx`
- 渲染测试: 编辑器、策略列表
- 保存流程: 新建/更新策略
- 语法检查: 缺少 class/on_bar 时显示错误

**文件**: `web/src/__tests__/pages/Data.test.tsx`
- 渲染测试: 数据源表格、缓存统计、K线图
- K线查询: 输入代码 → 点击查询 → 显示图表

**文件**: `web/src/__tests__/pages/Monitor.test.tsx`
- 渲染测试: 自选股列表、告警面板
- 告警规则: 开关切换、阈值设置

**文件**: `web/src/__tests__/pages/Portfolio.test.tsx`
- 渲染测试: 汇总卡片、持仓表格、行业分布图
- 快捷交易按钮: 点击跳转 /trading

**文件**: `web/src/__tests__/pages/AIChat.test.tsx`
- 渲染测试: 对话面板、消息列表、输入框
- 发送消息: 输入文本 → 点击发送 → 流式响应
- XSS 防护: 危险 HTML 被 sanitize

**文件**: `web/src/__tests__/pages/Settings.test.tsx`
- 渲染测试: 14 个分组、向导/专家模式切换
- 条件显隐: when 条件生效
- 保存流程: dirty 追踪、浮动保存条

---

## 四、不纳入本次范围

| 项目 | 原因 |
|------|------|
| WebSocket 实时推送 | 需后端 WS 服务端配合，属架构级工作 |
| 后端 Router 补齐 | 属后端开发范畴 |
| E2E 测试 (Cypress) | 属下一阶段 |
| 组件抽取重构 (12 个独立组件) | 属重构范畴，不影响功能完整性 |
| LiveBroker XTP 真实接入 | 属部署级工作 |

---

## 五、执行顺序

```
Step 1: 测试基础设施 (vitest + testing-library)
    ↓
Step 2: P0 功能修复 (MonthHeatmap/XSS/Backtest跳转/Data修复)
    ↓
Step 3: P1 功能修复 (Settings when/Strategy更新/AIChat SSE/AI解读/Monitor告警/Portfolio API)
    ↓
Step 4: 代码质量修复 (Q3-Q10)
    ↓
Step 5: 单元测试 (API → Store → 组件 → 页面)
    ↓
验证: npm test → 全部通过 + npm run build → 0 errors
```

---

## 六、验收标准

### 功能验收
- [ ] MonthHeatmap 渲染为真正的 ECharts heatmap (非 bar)
- [ ] AIChat 无 XSS 风险 (DOMPurify sanitize)
- [ ] Backtest 提交后自动跳转 `/backtest/:id`
- [ ] Data K线查询有实际功能
- [ ] Settings when 条件显隐生效
- [ ] Strategy 保存可更新已有策略
- [ ] AIChat 使用标准 SSE 解析
- [ ] BacktestResult AI 解读调用 API
- [ ] Monitor 告警规则有实际逻辑
- [ ] Portfolio 从 API 加载数据

### 测试验收
- [ ] `npm test` → 0 failures
- [ ] 测试文件 ≥ 15 个
- [ ] 测试用例 ≥ 120 个
- [ ] 核心模块覆盖率 > 70%

### 技术验收
- [ ] `npm run build` → 0 errors
- [ ] 无 TypeScript `any` (除 ECharts 合理例外)
- [ ] 无硬编码颜色 (除语义色 #10b981/#ef4444)
