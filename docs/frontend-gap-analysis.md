# StockQuant Web 前端重构 — 达标复核与优化方向清单

> 审计日期: 2026-06-15 | 基准文档: `stockquant-web-redesign-plan.md`

---

## 一、全局基础层 (Design System + Layout)

| # | 检查项 | 计划要求 | 当前状态 | 达标 |
|---|--------|---------|----------|------|
| G1 | CSS Design Tokens (色彩/字体/间距/圆角/阴影/过渡) | 14 色彩 token + 字体/间距/圆角/阴影/过渡完整定义 | `index.css` 已实现全部 tokens，含额外 `--color-brand-active/subtle/info/disabled` 等 | ✅ 达标+ |
| G2 | Ant Design ConfigProvider 主题注入 | token 对齐 design system | `main.tsx` 已配置 colorPrimary/colorBgBase/colorBgContainer/colorBorder/fontFamily | ✅ 达标 |
| G3 | 全局 Reset + Scrollbar + Focus 样式 | 自定义滚动条/focus-visible/reduced-motion | `index.css` 已实现 scrollbar/focus-visible/reduced-motion/table responsive wrapper | ✅ 达标 |
| G4 | AppLayout 侧边栏导航 | 220px 宽度、品牌区、菜单项、GitHub 链接 | `AppLayout.tsx` 已重构：220px sider、品牌标识、API 延迟检测(30s)、时钟、GitHub 链接、Badge | ✅ 达标+ |
| G5 | AppLayout Header | 52px 高度、backdropFilter blur | Header 含 API 状态指示灯、实时时钟、GitHub 外链、blur 效果 | ✅ 达标 |
| G6 | Tailwind CSS 集成 | @import 'tailwindcss' + @theme 映射 | `index.css` 已引入 tailwindcss 并映射 surface tokens | ✅ 达标 |

**小结: 全局基础层已全面达标，超出计划的增强包括 API 延迟实时监测、Tailwind 集成。**

---

## 二、页面级达标情况

### 2.1 Dashboard (`/`) — ✅ 基本达标

| # | 检查项 | 计划要求 | 当前状态 | 达标 |
|---|--------|---------|----------|------|
| D1 | 6 个指标卡片 | 等宽网格、xs=2/md=3/lg=6 列 | `MetricCard` 组件提取完成，使用 `Row/Col` 响应式网格（xs=24/sm=12/md=8/lg=4） | ⚠️ 列数偏差：当前 lg=4 非 lg=6 |
| D2 | 权益曲线图表 | ECharts Line 占 2/3 宽 | `EquityChart` 已接入，lg=16（占 2/3） | ✅ 达标 |
| D3 | AI 信号面板 | 占 1/3 宽、信号列表 | lg=8 信号面板，含 Empty 空态、信号列表滚动 | ✅ 达标 |
| D4 | 回测历史表格 | 完整宽度表格 | Table 组件含策略名/状态/收益率/夏普/时间列 | ✅ 达标 |
| D5 | Loading/Skeleton 加载态 | Skeleton 骨架屏 | 当前用文字"加载中..."替代，非 Skeleton | ❌ 未达标 |
| D6 | 颜色 Token 使用 | 使用 CSS 变量非硬编码 | 部分仍硬编码: `#71717a`, `#e4e4e7`, `#52525b`, `#fafafa`, `#ccc` 等 | ⚠️ 部分硬编码 |

**待优化:**
- [ ] D1: 调整指标卡网格为 lg=6（或 lg=3 时每行 6 卡需 2 行）
- [ ] D5: 引入 `<Skeleton />` 替代文字 loading
- [ ] D6: 清除剩余硬编码颜色值，统一使用 design tokens

---

### 2.2 Strategy (`/strategy`) — ⚠️ 未对标

| # | 检查项 | 计划要求 | 当前状态 | 达标 |
|---|--------|---------|----------|------|
| S1 | 左右分栏布局 | Monaco Editor 70% + 策略列表 30% | **当前为上下堆叠**: 编辑器在上 Card、列表在下 Card | ❌ 结构不符 |
| S2 | 工具栏 | 新建/模板/保存/语法检查按钮 | 有新建/从模板按钮，编辑模式内有保存/预览/取消 | ⚠️ 缺语法检查按钮 |
| S3 | Monaco Editor | 代码高亮 vs-dark 主题 | 已集成 Monaco Editor, height=350, vs-dark | ✅ 达标 |
| S4 | 策略列表 | 含编辑/删除操作 | Table 含名称/代码预览/时间/操作列 | ✅ 达标 |
| S5 | 模板库 Modal | 3 个默认模板加载 | Modal 含 DualMA/RSI/MACD 三个模板 | ✅ 达标 |
| S6 | 颜色/样式 | 使用 design tokens | 大量硬编码: `#111`, `#666`, `#ccc`, `var(--surface-border)` (未定义) | ❌ 未达标 |
| S7 | 页面标题风格 | 统一标题+副标题格式 | 有 Title level=4 + Text secondary 描述 | ⚠️ 样式不统一 |

**待优化:**
- [ ] S1: **重构为左右分栏** — 左侧 Monaco Editor (flex: 7) + 右侧策略列表/预览 (flex: 3)
- [ ] S2: 工具栏增加"语法检查"按钮
- [ ] S6: 全面替换硬编码颜色为 design tokens
- [ ] S7: 统一页面标题风格

---

### 2.3 Backtest (`/backtest`) — ⚠️ 未对标

| # | 检查项 | 计划要求 | 当前状态 | 达标 |
|---|--------|---------|----------|------|
| B1 | 三段式配置 | 策略配置 / 数据配置 / 执行参数 | 3 个 Card 分组实现 | ✅ 达标 |
| B2 | Monaco Editor | 策略代码编辑器 | 已集成 height=300 | ✅ 达标 |
| B3 | 表单验证 | 必填校验 | strategy_name/symbols/dates/cash 设了 rules | ✅ 达标 |
| B4 | 策略模板选择 | 7 个模板选项 | Select 含 7 个模板 | ✅ 达标 |
| B5 | 颜色/样式 | design tokens | 硬编码: `#0066FF` 图标色, `var(--surface-border)` 未定义 | ❌ 未达标 |
| B6 | 日期选择器 | DatePicker 替代 Input | **当前用普通 Input 文本框输入日期** | ❌ 应改 DatePicker |
| B7 | 页面标题风格 | 统一格式 | Title level=4 + Text secondary | ⚠️ 可接受 |

**待优化:**
- [ ] B5: 替换硬编码颜色为 design tokens（尤其是 `#0066FF` → `--color-brand-primary`）
- [ ] B6: **日期字段升级为 `<DatePicker>` 组件**

---

### 2.4 BacktestResult (`/backtest/:id`) — ⚠️ 部分达标

| # | 检查项 | 计划要求 | 当前状态 | 达标 |
|---|--------|---------|----------|------|
| BR1 | 8 个指标卡片 | 年化收益/回撤/夏普/Sortino/Calmar/胜率/总交易/SQN | 8 卡片实现，响应式 xs=24/sm=12/md=8/lg=6 | ✅ 达标 |
| BR2 | 权益曲线 + 回撤 + 月度热力图 | 3 个 ECharts 图表 | EquityChart + DrawdownChart + MonthHeatmap 均已接入 | ✅ 达标 |
| BR3 | 完整指标表格 MetricTable | 30+ 指标分组展示 | MetricTable 组件已集成 | ⚠️ 样式未更新（见 M1） |
| BR4 | 交易明细表格 | 分页、横向滚动 | Table 含分页和 scroll.x | ✅ 达标 |
| BR5 | AI 解读面板 | AI 分析文字展示 | Card 含 AI 解读文本 | ✅ 达标 |
| BR6 | 颜色/样式 | design tokens | 硬编码: `#666`, `#0066FF`, `#a855f7`, `#f0f0f0`, `#333`, `#1a1a1a`, `#555`, `#888`, `#444` | ❌ 大量硬编码 |
| BR7 | Loading 态 | Skeleton | 文字"加载中..." | ❌ 未达标 |

**待优化:**
- [ ] BR6: 全面替换硬编码颜色为 design tokens
- [ ] BR7: 引入 Skeleton loading

---

### 2.5 Data (`/data`) — ❌ 未对标

| # | 检查项 | 计划要求 | 当前状态 | 达标 |
|---|--------|---------|----------|------|
| DT1 | 数据源管理表格 | 数据源列表+状态+操作 | Table 实现 | ✅ 达标 |
| DT2 | 缓存状态卡片 | 4 个统计卡片 | Row/Col 4 卡片网格 | ✅ 达标 |
| DT3 | K线查询功能 | 交互式K线图查询 | **完全缺失** | ❌ 未实现 |
| DT4 | 采集日志表格 | 同步日志展示 | Table 实现 | ✅ 达标 |
| DT5 | 颜色/样式 | design tokens | 硬编码: `#666`, `#555`, `#888`, `#f0f0f0` | ❌ 未达标 |
| DT6 | 页面标题风格 | 统一格式 | 用 div 模拟标题，非 Typography.Title | ❌ 不统一 |

**待优化:**
- [ ] DT3: **新增 K 线查询功能区**（ECharts candlestick + 代码/日期选择）
- [ ] DT5: 替换硬编码颜色
- [ ] DT6: 统一使用 Typography.Title

---

### 2.6 Monitor (`/monitor`) — ⚠️ 部分达标

| # | 检查项 | 计划要求 | 当前状态 | 达标 |
|---|--------|---------|----------|------|
| M1 | 自选股列表 | 添加/删除/表格展示 | Input 添加 + Table 展示 + 删除 | ✅ 达标 |
| M2 | 扫描控制面板 | 启停按钮 + 状态指示 | 圆形脉冲动画指示灯 + 启停按钮 | ✅ 达标+ |
| M3 | 最近信号推送 | 信号列表滚动 | Card 信号列表 | ✅ 达标 |
| M4 | 盘前简报 | 文字简报面板 | Card 文本内容 | ✅ 达标 |
| M5 | WebSocket 实时推送 | 实时行情/信号 | **当前仅 mock 数据，无真实 WS 连接** | ❌ 未实现 |
| M6 | 颜色/样式 | design tokens | 硬编码: `#1a1a1a`, `#555`, `#444`, `#0066FF`, `#a855f7` | ❌ 未达标 |
| M7 | 告警规则配置 | Should 级需求 | **缺失** | ⚠️ 可后续迭代 |

**待优化:**
- [ ] M5: 接入 WebSocket 实时数据推送（架构层面）
- [ ] M6: 替换硬编码颜色

---

### 2.7 Portfolio (`/portfolio`) — ⚠️ 部分达标

| # | 检查项 | 计划要求 | 当前状态 | 达标 |
|---|--------|---------|----------|------|
| P1 | 5 个汇总指标卡 | 总市值/总成本/累计盈亏/收益率/持仓数 | 5 卡片网格 xs=24/sm=12/md=6 | ✅ 达标 |
| P2 | 持仓明细表格 | 8 列详细持仓信息 | Table 含代码/名称/股数/成本/现价/市值/盈亏/盈亏% | ✅ 达标 |
| P3 | 行业分布饼图 | ECharts Pie | ReactECharts pie 图实现 | ✅ 达标 |
| P4 | 盈亏分析柱状图 | ECharts Bar | ReactECharts bar 图实现 | ✅ 达标 |
| P5 | 颜色/样式 | design tokens | 硬编码: `#666`, `#f0f0f0`, `#333`, `#1a1a1a`, `#555`, `#888`, `#0066FF` | ❌ 大量硬编码 |
| P6 | ECharts 图表配色 | 使用 brand palette | 饼图 color 用 `['#0066FF', '#10b981', '#f59e0b', '#6366f1']` | ⚠️ 应统一为 brand 色 |

**待优化:**
- [ ] P5: 全面替换硬编码颜色
- [ ] P6: ECharts 配色统一为 `--color-brand-primary` 系列色板

---

### 2.8 AIChat (`/ai-chat`) — ❌ 未对标

| # | 检查项 | 计划要求 | 当前状态 | 达标 |
|---|--------|---------|----------|------|
| AC1 | 消息列表 | 用户/AI 消息展示 | List + List.Item.Meta 实现 | ✅ 达标 |
| AC2 | 输入框 + 发送按钮 | 底部固定输入区域 | Input + Button 实现 | ✅ 达标 |
| AC3 | 流式输出 (SSE) | 打字机效果逐字输出 | **当前为一次性返回，无 SSE 流式** | ❌ 未实现 |
| AC4 | 空态引导 | 示例提示语 | 空态图标 + 示例提示 | ✅ 达标 |
| AC5 | 自动滚动 | 新消息自动到底部 | useRef + scrollIntoView | ✅ 达标 |
| AC6 | 颜色/样式 | design tokens | 大量硬编码: `#555`, `#888`, `#0066FF`, `#ddd`, `#444`, `#333`, `#1a1a1a`, `#f0f0f0` | ❌ 严重 |
| AC7 | 会话管理 | Should 级: 会话列表/切换 | **缺失** | ⚠️ 可后续 |
| AC8 | Markdown 渲染 | AI 回复支持 Markdown | **纯文本 pre-wrap，无 Markdown** | ❌ 未实现 |

**待优化:**
- [ ] AC3: **接入 SSE 流式输出**（后端已有 SSE 支持，前端需改造 fetch → EventSource/fetch+reader）
- [ ] AC6: 全面替换硬编码颜色（最严重的页面之一）
- [ ] AC8: **AI 回复增加 Markdown 渲染**（code block / table / list 格式化）

---

### 2.9 Settings (`/settings`) — ⚠️ 部分达标

| # | 检查项 | 计划要求 | 当前状态 | 达标 |
|---|--------|---------|----------|------|
| ST1 | 向导/专家模式切换 | Tag 切换 | wizard/expert Tag 切换实现 | ✅ 达标 |
| ST2 | 14 组 Collapse 手风琴 | 14 配置分组 | 14 组 GROUPS 定义完整 | ✅ 达标+ |
| ST3 | 浮动保存条 | FloatButton 脏数据检测 | FloatButton + dirtyCount 检测 | ✅ 达标 |
| ST4 | 管理员确认弹窗 | Admin Token 验证 | Modal + Password 输入 | ✅ 达标 |
| ST5 | 各类控件 | Switch/Select/InputNumber/Slider/Password | 全部控件类型覆盖 | ✅ 达标 |
| ST6 | 颜色/样式 | design tokens | 硬编码: `#0066FF`(大量), `#f0f0f0`, `#a855f7`, `#f59e0b`, `#555`, `#333` | ❌ 最严重页面 |
| ST7 | Banner 渐变背景 | 品牌渐变 banner | linear-gradient purple→blue | ⚠️ 可接受但色值应 token 化 |
| ST8 | 向导模式内容 | Should 级 | 显示"已移除"提示 | ⚠️ 占位 |

**待优化:**
- [ ] ST6: **最大规模的硬编码颜色清理**（`#0066FF` 出现 ~15 次，应批量替换为 `var(--color-brand-primary)`）

---

## 三、共享组件达标情况

| # | 组件 | 计划要求 | 当前状态 | 达标 |
|---|------|---------|----------|------|
| C1 | EquityChart | 深色主题 ECharts 折线图 | 已更新为新 design token 颜色 | ✅ 达标 |
| C2 | DrawdownChart | 深色主题面积图 | 已更新 | ✅ 达标 |
| C3 | MonthHeatmap | 深色主题热力图 | 已更新 | ✅ 达标 |
| C4 | MetricTable | 30+ 指标结构化展示 | **硬编码**: `rgba(255,255,255,0.02)`, `#1a1a1a`, `#555`, `#666`, `#f0f0f0` | ❌ 未达标 |
| C5 | MetricCard (Dashboard) | 可复用指标卡片 | Dashboard 内提取为独立组件 | ✅ 达标（但仅 Dashboard 内使用） |

**待优化:**
- [ ] C4: MetricTable 全面 token 化

---

## 四、跨页面通用问题汇总

### 问题 A: 硬编码颜色值 (影响全部 9 个页面)

以下硬编码颜色值在多个页面中重复出现，应统一替换为 CSS 变量：

| 硬编码值 | 应替换为 | 出现频次估算 |
|---------|---------|------------|
| `#0066FF` (旧品牌蓝) | `var(--color-brand-primary)` / `#3b82f6` | ~20 次 |
| `#555` | `var(--color-text-tertiary)` | ~12 次 |
| `#666` | `var(--color-text-tertiary)` | ~8 次 |
| `#888` | `var(--color-text-secondary)` | ~6 次 |
| `#f0f0f0` | `var(--color-text-primary)` | ~10 次 |
| `#333` / `#444` | `var(--color-bg-elevated)` / `var(--color-text-disabled)` | ~8 次 |
| `#1a1a1a` | `var(--color-bg-surface)` | ~10 次 |
| `#a855f7` (紫色) | `var(--color-info)` | ~4 次 |
| `var(--surface-border)` (未定义变量!) | `var(--color-border-default)` | ~4 次 |

### 问题 B: 页面标题风格不统一

- Dashboard: `Title level={5}` + 手工 style
- Strategy/Backtest/Monitor/Portfolio: `Title level={4}` + `Text secondary`
- Data: 纯 `div` + `fontWeight`
- 应统一为标准组件或提取 `PageHeader`

### 问题 C: 缺失功能 (PRD Should/Could 级)

| 功能 | 优先级 | 说明 |
|------|--------|------|
| SSE 流式 AI 对话 | Must | AIChat 当前一次性返回 |
| K 线查询 | Must | Data 页面缺失核心功能 |
| DatePicker | Must | Backtest 日期用文本输入 |
| WebSocket 实时行情 | Should | Monitor 无真实 WS 连接 |
| Markdown 渲染 | Should | AI 回复纯文本 |
| Skeleton 加载 | Should | 多页面用文字替代 |
| 策略语法检查 | Could | Strategy 页面缺少 |
| 左右分栏 Strategy | Must | PRD 明确要求 70/30 布局 |

### 问题 D: 性能/工程问题

| 问题 | 影响 | 建议 |
|------|------|------|
| 无代码分割/懒加载 | 首屏包体积大 (~2.4MB chunk warning) | `React.lazy()` + `Suspense` 按路由拆分 |
| ECharts 多实例 | Portfolio 同时渲染 2 个 ECharts | 可接受，但注意内存 |
| any 类型泛滥 | Strategy/BacktestResult/Dashboard 中 `any` | 逐步收窄类型 |

---

## 五、优化优先级建议 (下一步行动)

### P0 — 立即修复 (一致性 + 正确性)

1. **全量硬编码颜色清洗** — 批量替换 9 个页面 + MetricTable 中的旧色值为 design tokens
   - 涉及文件: Strategy.tsx, Backtest.tsx, BacktestResult.tsx, Data.tsx, Monitor.tsx, Portfolio.tsx, AIChat.tsx, Settings.tsx, MetricTable.tsx, Dashboard.tsx(残余)
   - 预期效果: 视觉一致性 100%

2. **Strategy 页面左右分栏重构** — 符合 PRD 线框图的 70/30 布局
   - 涉及文件: Strategy.tsx

3. **Backtest 日期选择器升级** — Input → DatePicker
   - 涉及文件: Backtest.tsx

### P1 — 功能补全 (体验提升)

4. **AIChat SSE 流式输出** — 接入 EventSource 或 fetch streaming
   - 涉及文件: AIChat.tsx, api/ai.ts

5. **Data 页面 K 线查询** — 新增 ECharts candlestick 图
   - 涉及文件: Data.tsx

6. **Skeleton 加载态** — Dashboard/BacktestResult 引入 Skeleton
   - 涉及文件: Dashboard.tsx, BacktestResult.tsx

7. **AIChat Markdown 渲染** — react-markdown 或轻量方案
   - 涉及文件: AIChat.tsx

### P2 — 工程优化 (性能/可维护性)

8. **路由级代码分割** — React.lazy + Suspense
   - 涉及文件: App.tsx (router 定义)

9. **PageHeader 组件提取** — 统一标题风格
   - 新建文件: components/shared/PageHeader.tsx

10. **MetricCard 全局化** — 从 Dashboard 提取到 components 共享
    - 涉及文件: components/shared/MetricCard.tsx

11. **ECharts 主题 Token 化** — Portfolio 图表配色统一
    - 涉及文件: Portfolio.tsx

### P3 — 锦上添花 (后续迭代)

12. Monitor WebSocket 接入
13. Strategy 语法检查按钮
14. Settings 向导模式实现
15. Lighthouse 性能审计 + 优化
16. 响应式断点测试 (xs/sm/md/lg 真机验证)

---

## 六、达标率统计

| 维度 | 总项数 | ✅ 达标 | ⚠️ 部分 | ❌ 未达标 | 达标率 |
|------|--------|---------|---------|-----------|--------|
| 全局基础层 | 6 | 6 | 0 | 0 | **100%** |
| Dashboard | 6 | 3 | 2 | 1 | **67%** |
| Strategy | 7 | 3 | 1 | 3 | **43%** |
| Backtest | 7 | 5 | 1 | 1 | **71%** |
| BacktestResult | 7 | 4 | 1 | 2 | **57%** |
| Data | 6 | 3 | 0 | 3 | **50%** |
| Monitor | 7 | 4 | 1 | 2 | **57%** |
| Portfolio | 6 | 4 | 1 | 1 | **67%** |
| AIChat | 8 | 4 | 1 | 3 | **50%** |
| Settings | 8 | 6 | 2 | 0 | **88%** |
| 共享组件 | 5 | 4 | 0 | 1 | **80%** |
| **合计** | **73** | **46** | **11** | **16** | **63%** |

**总体达标率: 63% (46/73)** — 基础设施完善，页面级实施参差不齐。
