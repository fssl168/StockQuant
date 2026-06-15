# 前端功能扩展 — 券商交易执行 + 参数优化 实施计划

> 目标: 从当前"纯展示/模拟"前端升级为具备**真实交易能力 + 参数优化闭环**的机构级平台
> 基准: Product-Spec.md F0xx 规格要求 + 后端已实现的引擎层 (Broker/Order/Optimizer)

---

## 一、现状分析

### 已有后端引擎 (可直接对接)

| 模块 | 文件 | 状态 | 可用接口 |
|------|------|------|---------|
| Order 模型 | `stockquant/models/order.py` | ✅ Done | OrderSide/Type/Status 枚举, add_fill(), A股规则 |
| Trade 模型 | `stockquant/models/trade.py` | ✅ Done | TradeData dataclass |
| Position 模型 | `stockquant/models/position.py` | ✅ Done | T+1 冻结, available/cost/pnl |
| Account 模型 | `stockquant/models/account.py` | ✅ Done | cash/frozen/equity |
| BacktestBroker | `stockquant/engine/broker.py` | ✅ Done | 模拟撮合, 滑点, 100股校验 |
| PaperBroker | `stockquant/engine/broker.py` | ✅ Done | 模拟盘 broker |
| LiveBroker | `stockquant/engine/broker.py` | 🔶 骨架 | 校验+审计日志, TODO: XTP/CTP |
| Cerebro.optstrategy() | `stockquant/engine/cerebro.py` | ✅ Done | grid/random/walkforward 并行优化 |
| RiskManager | `stockquant/engine/risk.py` | ✅ Done | 多规则拦截器 |
| Notifier (9渠道) | `stockquant/execution/notifier/` | ✅ Done | 推送通知 |

### 前端当前状态 (需新建/改造)

| 页面 | 当前状态 | 差距 |
|------|---------|------|
| Portfolio (`/portfolio`) | Mock 数据展示页 | ❌ 无下单/撤单, 无实时持仓 API 对接 |
| Monitor (`/monitor`) | Mock 价格+告警规则 | ❌ 无交易操作入口 |
| 参数优化页面 | **不存在** | ❌ 完全缺失 |

### 后端 API 缺口

| 端点 | 规划状态 | 实际状态 |
|------|---------|---------|
| `/api/orders` (CRUD) | 未规划 | **未实现** |
| `/api/positions` | 未规划 | **未实现** |
| `/api/portfolio` | 未规划 | **未实现** |
| `/api/backtest/optimize` | 已规划 | **未实现** |
| `/ws/trading` | 未规划 | **未实现** |

---

## 二、实施范围

### 新增页面 (2 个)

| # | 路由 | 页面名 | 功能 |
|---|------|--------|------|
| T1 | `/trading` | Trading (交易执行) | 下单面板 / 订单簿 / 持仓明细 / 成交记录 / 账户概览 |
| O1 | `/optimize` | Optimize (参数优化) | 参数配置 / 运行控制 / 进度展示 / 结果可视化(散点图+排名表) |

### 改造页面 (2 个)

| # | 页面 | 改动 |
|---|------|------|
| R1 | Portfolio → 重构为"投资组合总览" | 接入交易数据, 增加快捷下单入口 |
| R2 | AppLayout → 新增菜单项 | 增加"交易"/"优化"导航入口 |

### 新增文件清单

```
web/src/
├── pages/
│   ├── Trading.tsx          ← 新建: 交易执行主页面
│   └── Optimize.tsx         ← 新建: 参数优化页面
├── components/
│   └── Trading/
│       ├── OrderForm.tsx    ← 下单表单组件
│       ├── OrderBook.tsx    ← 订单簿表格
│       ├── PositionPanel.tsx ← 持仓面板
│       └── AccountBar.tsx   ← 账户资金栏
├── api/
│   └── trading.ts           ← 交易 API 封装
│   └── optimize.ts          ← 优化 API 封装
├── types/
│   └── index.ts             ← 补充 Order/Account/BrokerMode 类型
└── stores/
    └── tradingStore.ts      ← 交易状态管理 (Zustand)
```

---

## 三、Step-by-Step 实施

### Step 1: 类型定义扩展 + API 层 + Store

#### 3.1 TypeScript 类型补充 (`web/src/types/index.ts`)

在现有类型定义末尾追加:

```typescript
// ====== Trading Types ======
export type BrokerMode = 'paper' | 'live'
export type OrderSide = 'BUY' | 'SELL'
export type OrderType = 'MARKET' | 'LIMIT' | 'STOP'
export type OrderStatus = 'PENDING' | 'SUBMITTED' | 'PARTIAL_FILLED' | 'FILLED' | 'CANCELLED' | 'REJECTED'

export interface Order {
  id: string
  symbol: string
  side: OrderSide
  type: OrderType
  price: number
  quantity: number
  filledQty: number
  filledAvgPrice: number
  status: OrderStatus
  createdAt: string
  updatedAt: string
}

export interface AccountInfo {
  totalEquity: number
  cash: number
  frozenCash: number
  marketValue: number
  availableCash: number
  dailyPnl: number
  dailyPnlPct: number
}

export interface TradeRecord {
  id: string
  orderId: string
  symbol: string
  side: OrderSide
  price: number
  quantity: number
  commission: number
  timestamp: string
}

export interface OptimizerParam {
  name: string
  min: number
  max: number
  step?: number
  value?: number
}

export interface OptimizeConfig {
  strategyId: string
  params: OptimizerParam[]
  method: 'grid' | 'random' | 'walkforward'
  targetMetric: string
  maxIters?: number
  nJobs?: number
}

export interface OptimizeResult {
  rank: number
  params: Record<string, number>
  metrics: {
    sharpeRatio?: number
    totalReturn?: number
    maxDrawdown?: number
    winRate?: number
    totalTrades?: number
  }
}
```

#### 3.2 交易 API 层 (`web/src/api/trading.ts`)

```typescript
import client from './client'

// Mock implementation (will connect to real backend later)
const MOCK_DELAY = 600

// Account
export async function getAccount(): Promise<AccountInfo> { ...mock... }

// Orders
export async function getOrders(): Promise<Order[]> { ...mock... }
export async function placeOrder(req: { symbol: string; side: OrderSide; type: OrderType; price: number; quantity: number }): Promise<Order> { ...mock... }
export async function cancelOrder(orderId: string): Promise<void> { ...mock... }

// Positions
export async function getPositions(): Promise<Position[]> { ...mock... }

// Trades
export async function getTrades(): Promise<TradeRecord[]> { ...mock... }
```

所有 API 函数先使用 Mock 数据实现（模拟 PaperBroker 行为），返回结构符合后端 Schema。后续只需替换为真实 axios 调用即可。

#### 3.3 优化 API 层 (`web/src/api/optimize.ts`)

```typescript
import client from './client'

export async function runOptimization(config: OptimizeConfig): Promise<string> { /* taskId */ }
export async function getOptimizeStatus(taskId: string): Promise<{ status: string; progress: number; results?: OptimizeResult[] }> {}
export async function* streamOptimizeProgress(taskId: string): AsyncGenerator<{ progress: number; currentParams: Record<string,number>; bestResult?: OptimizeResult }> {}
```

同样先用 Mock SSE 流式进度。

#### 3.4 交易 Store (`web/src/stores/tradingStore.ts`)

```typescript
import { create } from 'zustand'

interface TradingState {
  brokerMode: BrokerMode
  account: AccountInfo | null
  orders: Order[]
  positions: Position[]
  trades: TradeRecord[]
  loading: boolean
  setBrokerMode: (m: BrokerMode) => void
  refreshAll: () => void
  placeOrder: (req: PlaceOrderReq) => Promise<Order>
  cancelOrder: (id: string) => Promise<void>
}
```

---

### Step 2: 交易执行主页面 — Trading.tsx

**文件**: `web/src/pages/Trading.tsx`

**布局设计** (对标专业量化终端):

```
┌─ StockQuant v2.0 — 交易执行 ─────────────────────────────────────────────┐
│                                                                        │
│ ┌─ Account Bar ──────────────────────────────────────────────────────┐  │
│ │ 总权益 ¥1,234,567  │  可用资金 ¥456,789  │  持仓市值 ¥777,778      │  │
│ │ 今日盈亏 +¥12,345 (+1.02%)                                        │  │
│ └────────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│ ┌─ [Paper/Live 切换] ─┬─ Order Form ──────────┬─ Positions ──────────┐  │
│ │                     │                      │                       │  │
│ │  股票代码: [____]   │  方向: BUY ▼          │  Symbol │ Qty │ PnL% │  │
│ │  名称: 贵州茅台     │  类型: LIMIT ▼        │  sh600519│ 100│+2.3%│  │
│ │  最新价: 1720.00    │  价格: [1720.50]      │  sz000858│ 200│-0.8%│  │
│ │  涨停: 1892.00      │  数量: [100 ]股       │  sh601318│ 500│+1.1%│  │
│ │  跌停: 1548.00      │                      │                       │  │
│ │                     │  [买入]  [卖出]        │                       │  │
│ │                     │                      │                       │  │
│ ├─────────────────────┤──────────────────────┤───────────────────────┤  │
│ │  Order Book (订单簿) │                      │  Trade History (成交)  │  │
│ │  ID  │Symbol│Side│Qty│Price│Status│Time     │  Time │Sym │Side│Px│Q │  │
│ │  #001│600519│BUY │100│1720│FILLED│10:30:01 │ 10:30 │519 │BUY │1720│100│
│ │  #002│000858│SELL│200│148 │PENDING│10:31:15 │ 10:31 │858 │SELL│148 │200│
│ └─────────────────────┴──────────────────────┴───────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

**核心功能模块**:

1. **AccountBar**: 顶部资金概览条（总权益/可用现金/持仓市值/今日盈亏）
2. **BrokerModeToggle**: Paper/Live 模式切换（Live 模式显示风险警告）
3. **OrderForm**: 左侧下单面板
   - 股票代码 Input + 自动查询名称和行情
   - 方向选择 (BUY/SELL)
   - 订单类型 (市价/限价/止损)
   - 价格/数量输入（限价单时价格可编辑）
   - 买入/卖出按钮（带确认弹窗）
4. **PositionPanel**: 右侧持仓列表（实时 PnL）
5. **OrderBook**: 左下订单簿（今日全部订单）
6. **TradeHistory**: 右下成交记录

**Mock 数据策略**:
- Account: 总权益 ~120万, 现金 ~40万, 3 只持仓
- Orders: 5-8 条混合状态的订单
- Positions: 3 只股票 (sh600519/sz000858/sh601318)
- Trades: 最近 20 条成交记录
- 下单操作: 模拟 800ms 延迟后添加到 orders 列表

**Design Token 使用**: 全部使用 `var(--color-*)`, 与现有页面风格一致

---

### Step 3: 参数优化主页面 — Optimize.tsx

**文件**: `web/src/pages/Optimize.tsx`

**布局设计**:

```
┌─ 参数优化 ─────────────────────────────────────────────────────────────┐
│                                                                        │
│ ┌─ 配置区 ──────────────────────────────────────────────────────────┐  │
│ │ 策略: [双均线交叉策略 ▼]                                          │  │
│ │                                                                    │  │
│ │ 参数网格:                                                          │  │
│ │ ┌────────────────┬────────┬────────┬────────┬────────┐           │  │
│ │ │ 参数名           │ 最小值   │ 最大值   │ 步长    │ 当前值  │           │  │
│ │ ├────────────────┼────────┼────────┼────────┼────────┤           │  │
│ │ │ fast_period     │ 5      │ 30     │ 5      │ 10     │           │  │
│ │ │ slow_period     │ 30     │ 120    │ 10     │ 60     │           │  │
│ │ │ stop_loss_pct   │ 0.01   │ 0.10   │ 0.01   │ 0.05   │           │  │
│ │ └────────────────┴────────┴────────┴────────┴────────┘           │  │
│ │                                                                    │  │
│ │ 优化方式: ○ 网格搜索  ● 随机采样  ○ 滚动窗口                        │  │
│ │ 优化目标: [夏普比率 ▼]   最大迭代数: [200]                         │  │
│ │                                                                    │  │
│ │                    [▶ 开始优化]                                     │  │
│ └────────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│ ┌─ 结果区 ──────────────────────────────────────────────────────────┐  │
│ │                                                                    │  │
│ │  Progress: ████████████░░░░░░ 65% (13/20 组合)                     │  │
│ │  当前参数: fast=15, slow=80, sl=0.03 → Sharpe=1.42               │  │
│ │                                                                    │  │
│ │  ┌─ 散点图 (Sharpe vs MaxDD) ──────────────────┐  ┌─ Top 10 ───┐  │  │
│ │  │                                             │  │ Rank │ Sharpe│  │  │
│ │  │         ★ (最佳参数点)                       │  │  1   │ 1.87  │  │  │
│ │  │      ●●                                      │  │  2   │ 1.73  │  │  │
│ │  │    ●● ●●  ●                                  │  │  3   │ 1.65  │  │  │
│ │  │  ●●     ●                                    │  │  ... │       │  │  │
│ │  │ ●                                              │  │  10  │ 1.21  │  │  │
│ │  └───────────────────────────────────────────────┘  └───────────┘  │  │
│ │                                                                    │  │
│ │  最佳参数详情:                                                      │  │
│ │  ┌────────────────────────────────────────────────────────────┐   │  │
│ │  │ fast_period=15, slow_period=80, stop_loss_pct=0.03         │   │  │
│ │  │ Sharpe Ratio: 1.87 │ Total Return: 45.2% │ Max DD: -12.3%  │   │  │
│ │  │ Win Rate: 62.5% │ Total Trades: 156                            │   │  │
│ │  │                        [应用到回测]  [保存参数]                │   │  │
│ │  └────────────────────────────────────────────────────────────┘   │  │
│ └────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

**核心功能模块**:

1. **ParamGridEditor**: 参数范围配置表格 (可增删行)
2. **MethodSelector**: 优化方式选择 (grid/random/walkforward)
3. **RunControl**: 开始/停止按钮 + 进度条
4. **ScatterChart**: ECharts 散点图 (X=MaxDrawdown, Y=SharpeRatio, 点大小=Return)
5. **RankingTable**: Top N 结果排名表
6. **BestResultCard**: 最佳参数详情 + 快捷操作

**Mock 数据策略**:
- 点击"开始优化"后:
  1. 显示 Progress bar
  2. 每 500ms 更新一次进度 (模拟并行计算)
  3. 同时更新散点图新点 + 排名表
  4. 全部完成后高亮最佳参数
- 默认生成 20 组结果 (Sharpe 0.8~2.0, Return 10%~60%, MaxDD -25%~-5%)

---

### Step 4: AppLayout 菜单 + 路由注册

**AppLayout.tsx** — menuItems 数组新增 2 项:

```tsx
{ key: '/trading', icon: <CurrencyCircleDollar size={20} weight="fill" />, label: '交易' },
{ key: '/optimize', icon: <SlidersHorizontal size={20} weight="fill" />, label: '优化' },
```

图标来源: `@phosphor-icons/react` (已在 package.json)

位置: 在 `/monitor` 之后, `/portfolio` 之前 (交易是盯盘后的自然下一步)

**App.tsx** — 新增路由:

```tsx
const Trading = lazy(() => import('./pages/Trading'))
const Optimize = lazy(() => import('./pages/Optimize'))

// Routes 内新增:
<Route path="/trading" element={<Trading />} />
<Route path="/optimize" element={<Optimize />} />
```

---

### Step 5: Portfolio 页面轻量改造

在现有 Portfolio 页面的标题区域增加一个"快捷下单"入口链接:

```tsx
{/* Quick action */}
<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
  <Title level={4} style={{ margin: 0 }}>投资组合</Title>
  <Button type="primary" size="small" icon={<CurrencyCircleDollar size={14} />} onClick={() => navigate('/trading')}>
    快捷交易
  </Button>
</div>
```

需要从 react-router-dom 导入 `useNavigate` (如果还没有的话)

---

## 四、不纳入本次范围

| 项目 | 原因 |
|------|------|
| LiveBroker XTP/CTP 真实接入 | 需券商 SDK + 实盘账号, 属部署级工作 |
| WebSocket 实时行情推送 | 需后端 WS 服务端配合 |
| 后端 REST API 真实实现 | 本次聚焦前端 UI + Mock 数据层 |
| Docker 部署配置 | 属 F030 独立任务 |
| 遗传算法/Bayes 优化 | 引擎层暂不支持, 仅 grid/random/walkforward |

---

## 五、执行顺序

```
Step 1 (类型+API+Store)     ← 基础设施，其他步骤依赖
    ↓
Step 2 (Trading 页面)       ← 核心新页面
Step 3 (Optimize 页面)      ← 核心新页面 (可与 Step 2 并行)
    ↓
Step 4 (菜单+路由)          ← 注册新页面到导航
Step 5 (Portfolio 改造)     ← 轻量改动
    ↓
验证: npm run build
```

---

## 六、验收标准

### 功能验收
- [ ] `/trading` 页面完整渲染: AccountBar + OrderForm + OrderBook + PositionPanel + TradeHistory
- [ ] Paper/Live 模式切换正常
- [ ] 下单操作: 输入股票代码→选方向→填数量→点击买入→订单出现在订单簿
- [ ] 撤单操作: 点击取消按钮→订单状态变为 CANCELLED
- [ ] `/optimize` 页面完整渲染: ParamGrid + MethodSelect + RunControl + ScatterChart + RankingTable
- [ ] 优化流程: 配置参数→开始→进度更新→散点图逐点出现→排名表刷新→最佳参数高亮
- [ ] 侧边栏新增"交易"+"优化"两个菜单项并可导航
- [ ] Portfolio 页面有"快捷交易"跳转按钮

### 技术验收
- [ ] `npm run build` → 0 errors
- [ ] 所有新页面使用 design tokens (无硬编码颜色)
- [ ] 所有新组件 TypeScript 类型安全 (无 `any`)
- [ ] 代码分割生效 (Trading/Optimize 为独立 chunk)

### 设计验收
- [ ] 交易页面布局对标专业量化终端 (同屏多面板)
- [ ] 优化页面散点图交互 (hover 显示参数详情)
- [ ] 整体风格与现有 9 个页面一致 (暗色主题, Inter 字体, 圆角卡片)
