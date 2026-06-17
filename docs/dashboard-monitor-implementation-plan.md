# Dashboard 与 Monitor 功能补全实施计划

> 基于 `dashboard-monitor-gap-assessment.md` 差距报告

---

## 执行顺序（按依赖和优先级）

1. **P0-1**: Dashboard 权益曲线接真实数据
2. **P0-2**: /optimize 页面（404 修复）
3. **P1-1**: Dashboard MetricTable（30+ 指标表）
4. **P1-2**: Dashboard SignalCard 集成
5. **P1-3**: 盘前简报接真实 API
6. **P1-4**: 信号确认/半自动下单
7. **P1-5**: 信号推理链展开
8. **P1-6**: Dashboard 基准对比线
9. **P1-7**: 自选股持久化
10. **P2-1**: 清理冗余组件（WatchList/AlertPanel/DataSourceForm/DataLogTable）
11. **P2-2**: 模板库补全 4 套
12. **P2-3**: Settings NotifierForm SMTP 补全

---

## Task 1: Dashboard 权益曲线接真实数据

### 文件修改

**`d:\leanpython\StockQuant\web\src\pages\Dashboard.tsx`**
- 新增 state: `equityCurveData: { dates: string[]; values: number[] } | null`
- 在 useEffect 中新增对 `GET /portfolio/equity-curve` 的请求
- 用真实数据替换 L187 的 mock 数据：`Array.from({ length: 30 }, () => ...)`
- 保留 loading 和 fallback 逻辑

**`d:\leanpython\StockQuant\web\src\api\dashboard.ts`**
- 新增 `equityCurve(): Promise<{ dates: string[]; values: number[] }>`

---

## Task 2: /optimize 页面（404 修复）

### 新建文件

**`d:\leanpython\StockQuant\web\src\pages\Optimize.tsx`**
- 从 Backtest.tsx 复制参数优化 UI 逻辑
- 复用 `ParamForm.tsx` 和 `OptimizeResultChart.tsx`（如存在）
- 调用 `POST /api/optimize/submit`
- 展示优化结果表格

---

## Task 3: Dashboard MetricTable（30+ 指标表）

### 文件修改

**`d:\leanpython\StockQuant\web\src\pages\Dashboard.tsx`**
- 从 BacktestResult 页面导入 MetricTable 组件
- 在权益曲线下方新增 MetricTable 展示 30+ 指标
- 数据来源：`dashboardApi.metrics()` 返回的 metrics 数据

### 后端

**`d:\leanpython\StockQuant\stockquant\api\routers\dashboard.py`**
- `GET /dashboard/metrics` 返回更详细的 metrics（至少 30 个指标）
- 从最近完成回测提取：Total Return, Annualized Return, Sharpe, Sortino, Calmar, Win Rate, Profit Factor, SQN, Volatility 等

---

## Task 4: Dashboard SignalCard 集成

### 文件修改

**`d:\leanpython\StockQuant\web\src\pages\Dashboard.tsx`**
- 将 NotificationList 替换为 SignalCard
- 从 notificationStore 获取 signals
- 展示置信度、推理链

---

## Task 5: 盘前简报接真实 API

### 前端修改

**`d:\leanpython\StockQuant\web\src\pages\Monitor.tsx`**
- 删除 L415-419 硬编码文本
- 调用 `monitorApi.brief()` 获取真实盘前简报
- 展示 AI 生成的简报内容

**`d:\leanpython\StockQuant\web\src\api\monitor.ts`**
- 新增 `brief(symbols?)` 方法

---

## Task 6-8: 信号确认/推理链/基准对比（合并实现）

### 前端修改

**`d:\leanpython\StockQuant\web\src\pages\Dashboard.tsx`**
- 权益曲线增加 benchmarkData prop（从后端获取沪深300数据）
- SignalCard 支持点击展开推理链

**`d:\leanpython\StockQuant\web\src\pages\Monitor.tsx`**
- 信号卡片增加"确认"按钮
- 调用 `POST /api/monitor/signal/confirm` 确认信号

---

## Task 9: 自选股持久化

### 前端修改

**`d:\leanpython\StockQuant\web\src\pages\Monitor.tsx`**
- 在 add/remove watchlist 时调用 `monitorApi.updateWatchlist()`
- 页面加载时调用 `monitorApi.getWatchlist()` 恢复

**`d:\leanpython\StockQuant\web\src\api\monitor.ts`**
- 新增 `getWatchlist()` / `updateWatchlist(symbols)` 方法

---

## Task 10-12: 清理冗余 + 模板库补全

### 文件操作

**删除文件**:
- `d:\leanpython\StockQuant\web\src\components\Monitor\WatchList.tsx`
- `d:\leanpython\StockQuant\web\src\components\Monitor\AlertPanel.tsx`
- `d:\leanpython\StockQuant\web\src\components\Data\DataSourceForm.tsx`
- `d:\leanpython\StockQuant\web\src\components\Data\DataLogTable.tsx`

**新建文件**:
- `d:\leanpython\StockQuant\web\src\pages\Strategy.tsx` - 新增 4 套模板

---
