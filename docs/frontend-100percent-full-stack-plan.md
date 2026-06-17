# 前端 100% Spec 达标 — WebSocket + 组件抽取 + 后端路由补齐 实施计划

> 目标: 补齐后端缺失路由、WebSocket 实时推送、前端组件抽取重构，使前端 Spec 达标率达到 100%

---

## 一、当前达标率总览

| 页面 | 当前 | 阻塞项 |
|------|------|--------|
| Dashboard | 90% | NotificationList 未抽取、数据 mock |
| Backtest | 90% | DataSelector/ParamForm 未抽取、WS 进度缺失 |
| BacktestResult | 95% | TradeTable/InsightCard 未抽取、AI 解读需后端路由 |
| Strategy | 90% | StrategyEditor/PreviewPanel 未抽取 |
| Data | 80% | 后端 data 路由缺失、组件未抽取 |
| Monitor | 80% | WS 未接入、组件未抽取 |
| Portfolio | 80% | 后端 portfolio 路由缺失、组件未抽取 |
| AIChat | 90% | ChatPanel/SignalCard 未抽取 |
| Settings | 85% | 后端 settings 路由缺失、组件未抽取 |
| Trading | 85% | 后端 trading 路由缺失、组件未抽取 |
| Optimize | 85% | 后端 optimize 路由缺失、组件未抽取 |

---

## 二、实施范围

### Part A: 后端 API 路由补齐 (6 个新路由模块)
### Part B: WebSocket 实时推送 (3 个端点)
### Part C: 前端组件抽取 (22 个独立组件)
### Part D: 前端接入真实 API + WS

---

## 三、Step-by-Step 实施

### Step 1: 后端 API 路由补齐

#### 1.1 新建 `stockquant/api/routers/data.py`

依赖: `DataFetcherManager` (已实现)

```python
# 端点清单:
GET  /api/data/sources        → 列出数据源配置
POST /api/data/sources        → 更新数据源配置
GET  /api/data/cache          → 缓存统计
DELETE /api/data/cache        → 清除缓存
GET  /api/data/kline          → K线数据查询 (symbol, start, end 参数)
```

实现: 调用 `DataFetcherManager` 获取数据源列表和缓存信息。K线数据通过 `DataFetcherManager.fetch()` 获取 OHLCV 数据并转换格式。

#### 1.2 新建 `stockquant/api/routers/settings.py`

依赖: 需新建配置持久化层 (JSON 文件)

```python
# 端点清单:
GET    /api/settings           → 获取全部配置
POST   /api/settings/save      → 保存配置 (批量)
DELETE /api/settings/{key}     → 恢复单个配置默认值
GET    /api/settings/whitelist → 获取管理员白名单
```

实现: 使用 JSON 文件存储配置 (`~/.stockquant/settings.json`)，读写操作通过 `SettingsManager` 类。

#### 1.3 新建 `stockquant/api/routers/trading.py`

依赖: `PaperBroker` / `LiveBroker` (已实现)

```python
# 端点清单:
GET  /api/trading/account    → 账户信息
POST /api/trading/order      → 下单
DELETE /api/trading/order/{id} → 撤单
GET  /api/trading/positions  → 持仓列表
GET  /api/trading/trades     → 成交记录
GET  /api/trading/orders     → 订单列表
```

实现: 使用 `PaperBroker` (模拟盘) 或 `LiveBroker` (实盘) 执行交易操作。通过 `broker_mode` 参数区分。

#### 1.4 新建 `stockquant/api/routers/portfolio.py`

依赖: `Portfolio` 模型 (已实现)

```python
# 端点清单:
GET /api/portfolio/positions  → 持仓列表
GET /api/portfolio/account    → 账户汇总
GET /api/portfolio/sector     → 行业分布
GET /api/portfolio/pnl        → 盈亏分析
```

实现: 从 `Portfolio` 模型获取持仓和汇总数据。

#### 1.5 新建 `stockquant/api/routers/optimize.py`

依赖: `Cerebro.optstrategy()` (已实现)

```python
# 端点清单:
POST /api/backtest/optimize           → 提交参数优化任务
GET  /api/backtest/optimize/{task_id} → 查询优化状态/结果
```

实现: 异步执行 `Cerebro.optstrategy()`，通过 `WebSocketManager` 推送进度。

#### 1.6 补充 `ai_chat.py` 缺失端点

```python
POST /api/ai/analyze-backtest/{backtest_id}  → AI 解读回测结果
```

实现: 调用 `BacktestAgent.analyze()` 生成解读。

#### 1.7 注册路由到 main.py

```python
from stockquant.api.routers import data, settings, trading, portfolio, optimize
app.include_router(data.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(trading.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(optimize.router, prefix="/api")
```

---

### Step 2: WebSocket 实时推送

#### 2.1 新建 `/ws/backtest/{task_id}`

**文件**: `stockquant/api/routers/backtest.py` 中添加

```python
@router.websocket("/ws/backtest/{task_id}")
async def backtest_progress(websocket: WebSocket, task_id: str):
    await ws_manager.connect(websocket, task_id)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, task_id)
```

在回测执行过程中，通过 `ws_manager.push(task_id, {...})` 推送进度:
- `type: "progress"` — 进度百分比
- `type: "metrics"` — 中间指标
- `type: "trade"` — 成交记录
- `type: "complete"` — 回测完成

#### 2.2 修正 `/ws/monitor` 路径

**文件**: `stockquant/api/routers/monitor.py`

将 `/api/monitor/ws/alerts` 改为 `/ws/monitor`，使用全局 `ws_manager`:

```python
@router.websocket("/ws/monitor")
async def monitor_ws(websocket: WebSocket):
    await ws_manager.connect(websocket, "monitor")
    # ... existing alert logic using ws_manager.push
```

#### 2.3 新建 `/ws/notification`

**文件**: `stockquant/api/routers/notification.py` (新建)

```python
@router.websocket("/ws/notification")
async def notification_ws(websocket: WebSocket):
    await ws_manager.connect(websocket, "notification")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "notification")
```

集成 `MessageRouter` 推送通知。

#### 2.4 前端接入 WebSocket

**文件**: `web/src/pages/Monitor.tsx`

替换 `setInterval` 模拟为 `useWebSocket`:

```typescript
const { messages, status } = useWebSocket('/ws/monitor')

useEffect(() => {
  if (messages.length === 0) return
  const latest = messages[messages.length - 1]
  if (latest.type === 'quote') {
    // 更新实时价格
  } else if (latest.type === 'alert') {
    // 添加信号通知
  }
}, [messages])
```

**文件**: `web/src/pages/Backtest.tsx`

提交后监听回测进度:

```typescript
const { messages } = useWebSocket(`/ws/backtest/${taskId}`)

useEffect(() => {
  if (messages.length === 0) return
  const latest = messages[messages.length - 1]
  if (latest.type === 'progress') {
    setProgress(latest.data.percent)
  } else if (latest.type === 'complete') {
    navigate(`/backtest/${taskId}`)
  }
}, [messages])
```

**文件**: `web/src/components/AppLayout.tsx`

全局通知监听:

```typescript
const { messages } = useWebSocket('/ws/notification')
// 收到通知后添加到 notificationStore
```

---

### Step 3: 前端组件抽取

按优先级分 3 批执行:

#### 3.1 第一批: 高复用基础组件 (6 个)

| 组件名 | 源文件 | 目标文件 | 行数估计 |
|--------|--------|---------|---------|
| `MetricCard` | Dashboard.tsx L10-L34 | `components/Card/MetricCard.tsx` | ~30 |
| `NotificationList` | Dashboard.tsx L226-L277 | `components/AI/NotificationList.tsx` | ~50 |
| `SignalCard` | Monitor.tsx L168-L187 | `components/AI/SignalCard.tsx` | ~25 |
| `InsightCard` | BacktestResult.tsx L176-L194 | `components/AI/InsightCard.tsx` | ~25 |
| `TradeTable` | BacktestResult.tsx L97-L110 | `components/Table/TradeTable.tsx` | ~40 |
| `CacheStats` | Data.tsx L74-L90 | `components/Data/CacheStats.tsx` | ~25 |

每个组件:
1. 从页面文件中提取 JSX + 样式
2. 定义 Props 接口
3. 页面文件改为 import 使用
4. 添加组件单元测试

#### 3.2 第二批: 表单/面板组件 (8 个)

| 组件名 | 源文件 | 目标文件 |
|--------|--------|---------|
| `DataSelector` | Backtest.tsx L114-L146 | `components/Backtest/DataSelector.tsx` |
| `StrategyEditor` | Strategy.tsx L141-L211 | `components/Strategy/StrategyEditor.tsx` |
| `PreviewPanel` | Strategy.tsx L203-L211 | `components/Strategy/PreviewPanel.tsx` |
| `ParamForm` | Backtest.tsx L148-L173 | `components/Backtest/ParamForm.tsx` |
| `WatchList` | Monitor.tsx L147-L165 | `components/Monitor/WatchList.tsx` |
| `AlertPanel` | Monitor.tsx L234-L249 | `components/Monitor/AlertPanel.tsx` |
| `DataSourceForm` | Data.tsx L138-L150 | `components/Data/DataSourceForm.tsx` |
| `DataLogTable` | Data.tsx L153-L172 | `components/Data/DataLogTable.tsx` |

#### 3.3 第三批: 复杂/专用组件 (8 个)

| 组件名 | 源文件 | 目标文件 |
|--------|--------|---------|
| `ChatPanel` | AIChat.tsx L149-L209 | `components/AI/ChatPanel.tsx` |
| `PortfolioSummary` | Portfolio.tsx L78-L95 | `components/Portfolio/PortfolioSummary.tsx` |
| `SectorPieChart` | Portfolio.tsx L104-L119 | `components/Portfolio/SectorPieChart.tsx` |
| `PnLTable` | Portfolio.tsx L120-L134 | `components/Portfolio/PnLTable.tsx` |
| `LLMConfigForm` | Settings.tsx ai_model 组 | `components/Settings/LLMConfigForm.tsx` |
| `AgentToggles` | Settings.tsx evolution 组 | `components/Settings/AgentToggles.tsx` |
| `NotifierForm` | Settings.tsx notification 组 | `components/Settings/NotifierForm.tsx` |
| `StockTicker` | Monitor.tsx L111-L136 | `components/Monitor/StockTicker.tsx` |

---

### Step 4: 前端接入真实 API

#### 4.1 修改 `api/trading.ts`

将 mock 实现替换为真实 API 调用:

```typescript
export async function getAccount(): Promise<AccountInfo> {
  const { data } = await client.get('/trading/account')
  return data
}

export async function placeOrder(order: OrderRequest): Promise<Order> {
  const { data } = await client.post('/trading/order', order)
  return data
}
// ... 其余方法类似
```

保留 mock 作为开发 fallback (通过环境变量 `VITE_USE_MOCK` 控制)。

#### 4.2 修改 `api/optimize.ts`

替换为真实 API:

```typescript
export async function runOptimization(config: OptimizeConfig): Promise<string> {
  const { data } = await client.post('/backtest/optimize', config)
  return data.task_id
}
```

#### 4.3 修改 Portfolio.tsx

移除 mock 数据 fallback，直接使用 API。

#### 4.4 修改 Data.tsx

K线查询调用真实 `dataApi.fetchKline()`。

---

## 四、不纳入本次范围

| 项目 | 原因 |
|------|------|
| Cerebro 引擎接入回测路由 | 属核心引擎集成，需单独规划 |
| LiveBroker XTP 真实接入 | 属部署级工作 |
| E2E 测试 (Cypress) | 属下一阶段 |
| 性能优化 (Lighthouse 审计) | 属优化阶段 |

---

## 五、执行顺序

```
Step 1: 后端 API 路由补齐 (6 个新路由模块)
    ↓
Step 2: WebSocket 端点补全 (3 个 WS 端点 + 前端接入)
    ↓
Step 3: 前端组件抽取 (22 个组件, 分 3 批)
    ↓
Step 4: 前端接入真实 API (trading/optimize/portfolio/data)
    ↓
验证: npm test + npm run build + 后端 pytest → 0 errors
```

---

## 六、验收标准

### 后端验收
- [ ] 6 个新路由模块创建完成
- [ ] 所有端点返回正确格式数据
- [ ] pytest 通过 (新增路由测试)
- [ ] 3 个 WebSocket 端点可连接

### 前端验收
- [ ] 22 个组件抽取完成
- [ ] Monitor 使用 WebSocket 替代 setInterval
- [ ] Backtest 提交后监听 WS 进度
- [ ] trading/optimize/portfolio/data 接入真实 API
- [ ] `npm run build` → 0 errors
- [ ] `npm test` → 0 failures
- [ ] 页面 Spec 达标率: 全部 ≥ 95%

### 测试验收
- [ ] 新增后端路由测试 ≥ 30 个
- [ ] 新增组件测试 ≥ 22 个
- [ ] 总测试数 ≥ 260 个
