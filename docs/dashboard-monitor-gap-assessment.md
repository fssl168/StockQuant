# Dashboard 与 Monitor 前端功能差距评估报告

> 评估基准：`Product-Spec.md` (F001-F030)
> 评估范围：Dashboard 仪表盘 + Monitor 盯盘页面及相关组件
> 评估时间：2025-06-16

---

## 一、整体达标率

| 模块 | 功能点 | 已实现 | 部分实现 | 未实现 | 达标率 |
|------|--------|--------|----------|--------|--------|
| Dashboard | 9 | 4 | 2 | 3 | 62% |
| Monitor | 11 | 6 | 3 | 2 | 70% |
| Strategy 模板库 | 7 | 3 | 0 | 4 | 43% |
| 图表组件 | 4 | 4 | 0 | 0 | 100% |
| 路由/导航 | 10 | 10 | 0 | 0 | 100% |
| 全局合计 | 41 | 27 | 5 | 9 | **73%** |

---

## 二、Dashboard 页面详细差距

### 已实现

1. ✅ 6 个指标卡片（MetricCard）：总权益、今日盈亏、持仓数、年化收益、最大回撤、夏普比率
2. ✅ 权益曲线图 — 使用 EquityChart 组件
3. ✅ AI 信号列表 — 使用 NotificationList 组件
4. ✅ 回测历史表格 — 从 dashboardApi 获取数据
5. ✅ 合并通知列表：signals + notifications

### 差距项

| ID | 差距 | 严重性 | 涉及文件 | 行号 |
|----|------|--------|----------|------|
| D-01 | 权益曲线数据为 mock（随机数） | 🔴 高 | Dashboard.tsx | L187 |
| D-02 | 缺少基准对比线（沪深300/中证500） | 🟡 中 | Dashboard.tsx | L187 |
| D-03 | 缺少 MetricTable 组件（30+ 指标表） | 🔴 高 | Dashboard.tsx | N/A |
| D-04 | SignalCard 未集成（无置信度/推理链展示） | 🟡 中 | Dashboard.tsx | L199 |
| D-05 | 无 WebSocket 实时更新机制 | 🟡 中 | Dashboard.tsx | N/A |
| D-06 | "主页仪表盘"标题应为"全局概览" | 🟢 低 | Dashboard.tsx | L162 |

---

## 三、Monitor 页面详细差距

### 已实现

1. ✅ 自选股列表 — 通过 marketStore
2. ✅ 实时行情 — WS `/ws/monitor`，不可用时 mock
3. ✅ 行情滚动条 — StockTicker 组件
4. ✅ K 线图弹窗 — RealtimeKline 组件
5. ✅ 告警规则 — 涨跌幅阈值和成交量检测
6. ✅ 最近信号 — notificationStore
7. ✅ 异动检测 — handleScanAnomalies + anomalyColumns
8. ✅ 收盘总结 — monitorApi.summary()
9. ✅ 情绪监控 — SentimentPanel 组件

### 差距项

| ID | 差距 | 严重性 | 涉及文件 | 行号 |
|----|------|--------|----------|------|
| M-01 | WatchList 组件存在但未使用（代码冗余） | 🟢 低 | Monitor.tsx | L1-484 vs WatchList.tsx |
| M-02 | AlertPanel 组件存在但未使用（代码冗余） | 🟢 低 | Monitor.tsx | L1-484 vs AlertPanel.tsx |
| M-03 | 盘前简报为硬编码文本 | 🔴 高 | Monitor.tsx | L415-419 |
| M-04 | 信号推理链不可见（无 AI 推理展开） | 🟡 中 | Monitor.tsx | L355-375 |
| M-05 | 信号确认/半自动下单未实现 | 🟡 中 | Monitor.tsx | N/A |
| M-06 | 自选股未持久化到后端 | 🟡 中 | marketStore.ts | N/A |

---

## 四、Strategy 模板库差距

### 已有（3/7）

1. ✅ Dual MACrossover
2. ✅ RSI Reversal
3. ✅ MACD Divergence

### 缺失（4/7）

| ID | 模板 | 严重性 | 涉及文件 |
|----|------|--------|----------|
| S-01 | Bollinger Bounce（布林带突破） | 🟡 中 | Strategy.tsx L11-58 |
| S-02 | Dual Thrust（双轨策略） | 🟡 中 | Strategy.tsx L11-58 |
| S-03 | Mean Reversion（均值回归） | 🟡 中 | Strategy.tsx L11-58 |
| S-04 | Momentum（动量策略） | 🟡 中 | Strategy.tsx L11-58 |

---

## 五、F027/F028/F030 完全未实现

| 功能代码 | 功能名称 | 状态 | 说明 |
|----------|----------|------|------|
| F027 | AI 策略回测对比 Agent | ❌ 未实现 | 无策略对比页面 |
| F028 | AI 自然语言交互界面 | 🟡 部分 | AIChat 有基础对话，无专用入口 |
| F030 | 前后端集成部署 | ❌ 未实现 | 无 Docker/Nginx 配置（但 Phase 4 已补全） |

---

## 六、Settings 页面差距

| ID | 差距 | 严重性 | 涉及文件 |
|----|------|--------|----------|
| ST-01 | NotifierForm 缺少 SMTP 详细配置 | 🟡 中 | Settings.tsx |
| ST-02 | admin_token 在保存 Modal 中未传递到 API | 🟡 中 | Settings.tsx L667-683 |

---

## 七、路由问题

| ID | 问题 | 严重性 |
|----|------|--------|
| R-01 | `/optimize` 路由已定义但无 Optimize.tsx 页面文件 | 🔴 高（404） |

---

## 八、代码冗余

| ID | 冗余组件 | 替代实现 | 建议 |
|----|----------|----------|------|
| C-01 | WatchList.tsx | Monitor.tsx 内联实现 | 删除 WatchList.tsx |
| C-02 | AlertPanel.tsx | Monitor.tsx 内联实现 | 删除 AlertPanel.tsx |
| C-03 | DataSourceForm.tsx | Data.tsx 内联实现 | 删除 DataSourceForm.tsx |
| C-04 | DataLogTable.tsx | Data.tsx 内联实现 | 删除 DataLogTable.tsx |

---

## 九、后端 API 差距

| ID | 端点 | 需求 | 状态 |
|----|------|------|------|
| API-01 | `GET /api/dashboard/metrics` | Dashboard 指标数据 | ❌ 缺失 |
| API-02 | `GET /api/dashboard/equity-curve` | Dashboard 资金曲线 | ❌ 缺失 |
| API-03 | `GET /api/monitor/premarket` | 盘前简报 | ❌ 缺失 |
| API-04 | `POST /api/monitor/signal/confirm` | 信号确认下单 | ❌ 缺失 |
| API-05 | `GET /api/strategies/templates` | 策略模板列表 | ❌ 缺失 |
| API-06 | `PUT /api/watchlist` | 自选股持久化 | ❌ 缺失 |

---

## 十、实施优先级

### P0（最高优先）— 核心功能缺失
1. **D-01**: Dashboard 权益曲线接真实数据
2. **API-01/02**: Dashboard 后端 API 缺失
3. **R-01**: /optimize 页面缺失（404）
4. **M-03**: 盘前简报硬编码

### P1（高优先）— 用户体验
1. **D-03**: 缺少 MetricTable
2. **D-04**: SignalCard 未集成
3. **M-04**: 信号推理链不可见
4. **M-05**: 信号确认/半自动下单
5. **M-06**: 自选股持久化
6. **API-03/04**: 盘前简报 + 信号确认后端
7. **S-01~S-04**: 模板库补全 4 套

### P2（中优先）— 完善体验
1. **D-02**: 基准对比线
2. **D-05**: WebSocket 实时更新
3. **M-01/02**: 清理冗余组件
4. **API-05/06**: 模板列表 + 自选股持久化后端
5. **ST-01/02**: Settings 补全
