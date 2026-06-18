# StockQuant 前端全页面对标 Product-Spec 调试与达标计划

> **目标**：调试 StockQuant 前端所有页面功能与后端交互，移除 mock 数据、补全缺失端点、修复错误处理，达到 Product-Spec F029 的 100% 功能达标率。
>
> **基准**：基于对 13 个前端页面、15 个后端路由文件、11 个 API 客户端文件的全面探索。
>
> **执行原则**：自行判断优先级，自行决策，不征求用户意见，按 Phase 顺序执行直到全部完成。

---

## 一、当前状态分析

### 1.1 前端页面清单（13 个）

| 页面 | 文件 | 主要问题 |
|------|------|---------|
| Dashboard | `web/src/pages/Dashboard.tsx` | 权益曲线 mock 数据（line 221）；4 处空 catch |
| Backtest | `web/src/pages/Backtest.tsx` | 基本正常，WS 进度监听已实现 |
| BacktestResult | `web/src/pages/BacktestResult.tsx` | 导出报表 `// silently fail`（line 82） |
| Optimize | `web/src/pages/Optimize.tsx` | 已实现导出 CSV 和应用到回测 |
| Strategy | `web/src/pages/Strategy.tsx` | AI 生成错误处理已修复；保存策略 `/* ignore */`（line 201） |
| Monitor | `web/src/pages/Monitor.tsx` | WS 不可用时 `Math.random()` 模拟行情（line 152-207）；多处空 catch |
| AIChat | `web/src/pages/AIChat.tsx` | 基本正常，SSE 流式已实现 |
| Portfolio | `web/src/pages/Portfolio.tsx` | 硬编码 mock 持仓（line 17-21）；5 处空 catch |
| Data | `web/src/pages/Data.tsx` | 硬编码 mock 时间和记录数（line 129-130）；mock 数据源降级（line 267-271） |
| Settings | `web/src/pages/Settings.tsx` | 使用原生 `fetch` 绕过 axios client（line 241, 324） |
| Trading | `web/src/pages/Trading.tsx` | 基本正常，错误处理已完善 |
| Comparison | `web/src/pages/Comparison.tsx` | `.catch(() => {})`（line 139） |
| Login | `web/src/pages/Login.tsx` | 基本正常 |

### 1.2 后端缺失端点（前端调用但后端未实现）

| 前端调用 | 后端状态 | 影响 |
|---------|---------|------|
| `GET /portfolio/risk-metrics` | **未实现**（portfolio.py 无此端点） | Portfolio 页风险指标卡片无数据 |
| `GET /data/collect-logs` | **未实现**（data.py 无此端点） | Data 页采集日志无数据 |
| `GET /data/download?provider=xxx` | **未实现**（data.py 无此端点） | Data 页下载按钮无效 |

### 1.3 前端架构问题

| 问题 | 文件:行号 | 影响 |
|------|----------|------|
| `client.ts` 5xx 返回 null | `web/src/api/client.ts:61-64` | 调用方需处处判空，易引发 null 引用 |
| `dashboard.ts` 重复定义 `backtestApi` | `web/src/api/dashboard.ts:36-62` | 与 `backtest.ts` 重复，维护不一致 |
| `Settings.tsx` 绕过 axios client | `web/src/pages/Settings.tsx:241,324` | 丢失 JWT 拦截器和 snake_case 转换 |
| `BacktestResult.tsx` 绕过 axios client | `web/src/pages/BacktestResult.tsx:60` | 导出报表使用原生 fetch |

### 1.4 Mock 数据清单（需移除）

| 文件:行号 | Mock 内容 |
|----------|----------|
| `Portfolio.tsx:17-21` | 硬编码 3 只股票持仓（贵州茅台/五粮液/中国平安） |
| `Dashboard.tsx:221` | `Array.from({length:30}, () => 1_000_000 + Math.random()*200_000)` |
| `Monitor.tsx:152-207` | WS 不可用时 `Math.random()` 模拟价格和信号 |
| `Data.tsx:129-130` | 硬编码 `'2026-06-15 15:00'` 和 `'1,234,567'` |
| `Data.tsx:267-271` | 无数据源时降级到硬编码 mock 列表 |

---

## 二、实施计划（分 5 个 Phase）

### Phase 1: 后端缺失端点补全（P0 - 最高优先级）

**目标**：实现前端已调用但后端缺失的 3 个端点，确保前后端契约完整。

#### Task 1.1: 实现 `GET /portfolio/risk-metrics`

**文件**：`stockquant/api/routers/portfolio.py`

**实现**：在文件末尾添加端点，基于真实持仓和交易数据计算风险指标：
- VaR(95%)：基于持仓市值的历史波动率估算
- 波动率：从权益曲线计算日收益率标准差
- 夏普比率：(年化收益 - 无风险利率) / 年化波动率
- 最大回撤：从权益曲线计算
- Beta/Alpha：相对沪深300指数

**逻辑**：
1. 获取持仓和权益曲线（复用已有的 `_compute_equity_curve_from_snapshots` 等函数）
2. 若无足够数据，返回默认零值（不报错）
3. 计算各项指标并返回 JSON

#### Task 1.2: 实现 `GET /data/collect-logs`

**文件**：`stockquant/api/routers/data.py`

**实现**：从 `_collect_tasks` 内存存储返回采集任务历史：
- 返回最近 20 条采集记录
- 每条包含：time, source, symbol, status, records, note
- 按 `created_at` 倒序

#### Task 1.3: 实现 `GET /data/download`

**文件**：`stockquant/api/routers/data.py`

**实现**：触发指定数据源的批量下载：
- 参数：`provider`（baostock/akshare/alphafeed/csv）
- 逻辑：调用对应 DataFeed 的批量下载方法，下载默认股票池（沪深300成分股前10只）的最新数据
- 返回：`{"success": true, "provider": "...", "count": N}`

---

### Phase 2: 移除前端 Mock 数据（P0）

**目标**：清除所有硬编码 mock 数据，改为空状态提示或真实 API 数据。

#### Task 2.1: Portfolio.tsx 移除 mock 持仓

**文件**：`web/src/pages/Portfolio.tsx`

**修改**：
- `positions` 初始 state 改为 `[]`（空数组）
- API 返回空时显示 Empty 组件提示"暂无持仓"
- 保留 `industryData` 动态计算逻辑（已实现）

#### Task 2.2: Dashboard.tsx 移除 mock 权益曲线

**文件**：`web/src/pages/Dashboard.tsx`

**修改**：
- 移除 `Array.from({length:30}, ...)` mock fallback
- 无数据时 `equityCurve.values` 传空数组，由 EquityChart 组件显示空状态

#### Task 2.3: Monitor.tsx 移除 mock 行情模拟

**文件**：`web/src/pages/Monitor.tsx`

**修改**：
- 移除 `Math.random()` 价格模拟逻辑（line 152-207）
- WS 不可用时显示提示"实时行情未连接，请启动监控"
- 保留告警规则检测逻辑，但仅对真实 WS 数据生效

#### Task 2.4: Data.tsx 移除硬编码时间和 mock 数据源

**文件**：`web/src/pages/Data.tsx`

**修改**：
- 移除硬编码 `'2026-06-15 15:00'` 和 `'1,234,567'`（line 129-130）
- 改为从数据源健康状态返回的 `last_check` 动态显示
- 移除 mock 数据源降级（line 267-271），无数据时显示 Empty

---

### Phase 3: 前端架构问题修复（P1）

**目标**：修复 client.ts、dashboard.ts、Settings.tsx 的架构问题。

#### Task 3.1: 修复 client.ts 5xx 返回 null 问题

**文件**：`web/src/api/client.ts`

**修改**：
- 5xx 错误不再返回 null，改为 reject Error
- 调用方通过 try/catch 处理错误
- 保留 401 清除 token 逻辑

**影响范围**：所有调用 client 的页面需要确保有 try/catch（大部分已有）

#### Task 3.2: 消除 dashboard.ts 重复的 backtestApi

**文件**：`web/src/api/dashboard.ts`

**修改**：
- 删除 `dashboard.ts` 中重复定义的 `backtestApi`（line 36-62）
- 改为从 `backtest.ts` re-export：`export { backtestApi } from './backtest'`
- 更新 `BacktestResult.tsx` 和 `Comparison.tsx` 的 import 路径

#### Task 3.3: Settings.tsx 改用 axios client

**文件**：`web/src/pages/Settings.tsx`

**修改**：
- 将 `fetch('/api/settings')` 改为 `client.get('/settings')`
- 将 `fetch('/api/settings/save', ...)` 改为 `client.post('/settings/save', ...)`
- 保留 `X-Admin-Token` header 通过 client 的请求配置传入
- 导入 `client from '@/api/client'`

#### Task 3.4: BacktestResult.tsx 导出报表改用 axios

**文件**：`web/src/pages/BacktestResult.tsx`

**修改**：
- 保留 `fetch` 用于下载 blob（axios 的 responseType: 'blob' 也可，但 fetch 更简单）
- 添加错误提示 message.error 替代 `// silently fail`

---

### Phase 4: 错误处理完善（P2）

**目标**：为关键空 catch 块添加错误日志和用户提示。

#### Task 4.1: Portfolio.tsx 错误处理

**文件**：`web/src/pages/Portfolio.tsx`

**修改**：5 处 `.catch(() => {})` 改为 `.catch((e) => console.warn('[Portfolio] xxx failed:', e.message))`

#### Task 4.2: Dashboard.tsx 错误处理

**文件**：`web/src/pages/Dashboard.tsx`

**修改**：4 处 `.catch(() => {})` 添加 console.warn 日志

#### Task 4.3: Monitor.tsx 错误处理

**文件**：`web/src/pages/Monitor.tsx`

**修改**：多处 `.catch(() => {})` 和 `} catch { /* ignore */ }` 添加日志

#### Task 4.4: Data.tsx 错误处理

**文件**：`web/src/pages/Data.tsx`

**修改**：2 处 `// ignore` 添加日志

#### Task 4.5: BacktestResult.tsx 错误处理

**文件**：`web/src/pages/BacktestResult.tsx`

**修改**：`// silently fail` 改为 `message.error('导出失败')`

#### Task 4.6: Strategy.tsx 错误处理

**文件**：`web/src/pages/Strategy.tsx`

**修改**：`} catch { /* ignore */ }`（line 201）改为 `} catch (e) { message.error('保存策略失败') }`

---

### Phase 5: 最终验证（P3）

**目标**：全量验证前后端集成正常。

#### Task 5.1: TypeScript 编译验证

```bash
cd web && npx tsc --noEmit
```

#### Task 5.2: 后端导入验证

```bash
python -c "import stockquant.api.main; print('OK')"
```

#### Task 5.3: 后端 API 端点验证

```bash
python -c "
from stockquant.api.main import app
routes = [r.path for r in app.routes if hasattr(r, 'path')]
required = ['/portfolio/risk-metrics', '/data/collect-logs', '/data/download']
for r in required:
    assert r in routes, f'Missing: {r}'
    print(f'OK: {r}')
"
```

#### Task 5.4: 前端构建验证

```bash
cd web && npm run build
```

---

## 三、假设与决策

### 3.1 假设
1. 后端 `portfolio.py` 的 `_get_trading_state()` 和权益曲线计算函数可复用
2. 后端 `data.py` 的 `_collect_tasks` 内存存储可用于 collect-logs 端点
3. 前端 `EquityChart` 组件已支持空数据显示
4. 前端 `Empty` 组件来自 Ant Design，可直接使用

### 3.2 决策
1. **不修改 auth.py 的内存用户库**：超出本次"前端调试"范围，且 admin/admin123 默认账户可用
2. **不修改 ai_chat.py 的 MVP 情感分析**：已有 `/ai/sentiment` 端点，前端未直接调用该 mock 端点
3. **保留 Monitor.tsx 的 WS fallback 提示**：不模拟数据，但显示"未连接"提示
4. **client.ts 5xx 改为 reject**：统一错误处理，调用方已有 try/catch
5. **风险指标计算简化**：无足够历史数据时返回零值，不报错

---

## 四、验证步骤

### 4.1 每个 Phase 完成后
- 运行 `npx tsc --noEmit` 确保无类型错误
- 运行 `python -c "import stockquant.api.main"` 确保后端可导入

### 4.2 全部完成后
- 运行 `npm run build` 确保前端构建成功
- 运行后端 API 端点验证脚本
- 检查所有页面无 mock 数据残留（grep `Math.random`、`mock`、`硬编码`）

### 4.3 达标标准
- ✅ 13 个前端页面全部通过真实 API 调用获取数据
- ✅ 3 个缺失后端端点已实现
- ✅ 无 mock 数据残留
- ✅ 无空 catch 块（关键路径）
- ✅ TypeScript 编译零错误
- ✅ 前端构建成功
- ✅ 后端导入成功

---

## 五、执行顺序

1. **Phase 1**（后端端点补全）→ Task 1.1, 1.2, 1.3 并行
2. **Phase 2**（移除 mock 数据）→ Task 2.1, 2.2, 2.3, 2.4 并行
3. **Phase 3**（架构修复）→ Task 3.1, 3.2, 3.3, 3.4 顺序执行（3.1 影响范围大）
4. **Phase 4**（错误处理）→ Task 4.1-4.6 并行
5. **Phase 5**（最终验证）→ Task 5.1-5.4 顺序执行
