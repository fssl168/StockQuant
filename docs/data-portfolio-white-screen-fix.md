# 数据/组合页面白屏修复 + Spec 达标计划

## 一、白屏根因分析

### 根因 1: 后端未运行导致 WS 代理持续报错

Vite dev server 配置了 `/ws` 代理到 `ws://localhost:8000`，但后端 FastAPI 未启动。AppLayout.tsx 中 `useWebSocket('/ws/notification')` 持续尝试连接，每次连接失败触发 Vite WS proxy 错误 (`ECONNREFUSED`)，每 2 秒重试一次，大量错误日志可能导致页面卡顿。

### 根因 2: API 请求 500 错误

Data 页面 `useDataStore.fetchSources()` 和 `fetchCacheStats()` 调用 `/api/data/sources` 和 `/api/data/cache`，后端未运行导致 Vite 代理返回 500。虽然 catch 了错误，但 API 请求超时 (10s) 可能阻塞页面。

### 根因 3: Portfolio 页面 `client.get` 无超时

Portfolio.tsx 中 `client.get('/portfolio/positions')` 和 `client.get('/portfolio/account')` 没有超时设置，后端不可达时请求挂起，可能导致 Suspense 卡住。

## 二、修复方案

### Fix 1: useWebSocket 增加连接失败静默处理

**文件**: `web/src/hooks/useWebSocket.ts`

- 连接失败后不再无限重试，最多重试 3 次后停止
- 重试间隔从固定 3s 改为指数退避 (1s → 2s → 4s)
- 添加 `silent` 选项，连接失败时不输出 console.error

### Fix 2: AppLayout WS 连接条件化

**文件**: `web/src/components/AppLayout.tsx`

- 仅在后端可达时才建立 WS 连接
- 使用 `/api/health` 检测后端状态，不可达时跳过 WS

### Fix 3: API client 添加超时和错误边界

**文件**: `web/src/api/client.ts`

- Axios 添加 `timeout: 5000` (5 秒超时)
- 添加响应拦截器，5xx 错误时返回空数据而非抛出异常

### Fix 4: Data 页面添加 ErrorBoundary

**文件**: `web/src/pages/Data.tsx`

- 添加 React ErrorBoundary 包裹，API 失败时显示降级 UI
- `useDataStore` 的 `fetchSources`/`fetchCacheStats` 失败时使用本地 mock 数据

### Fix 5: Portfolio 页面添加加载超时

**文件**: `web/src/pages/Portfolio.tsx`

- `client.get` 添加超时 fallback
- 添加 Skeleton 加载态

## 三、Spec 差距分析

### Data 页面 vs Product-Spec

| Spec 要求 | 当前状态 | 差距 |
|-----------|---------|------|
| 数据源列表 (CRUD) | 有列表但无编辑 | 缺少编辑/切换启用状态 |
| 缓存管理 (统计+清除) | 有统计无清除 | 缺少清除缓存按钮 |
| K线查询 | 已实现 | ✅ |
| 数据预览表格 | 无 | 缺少数据预览 |
| 采集日志 | 有 | ✅ |
| 数据导入 (CSV) | 无 | 缺少 CSV 上传功能 |

### Portfolio 页面 vs Product-Spec

| Spec 要求 | 当前状态 | 差距 |
|-----------|---------|------|
| 持仓汇总卡片 | 已实现 | ✅ |
| 持仓明细表格 | 已实现 | ✅ |
| 行业分布饼图 | 已实现 | ✅ |
| 盈亏分布图 | 已实现 | ✅ |
| 历史交易记录 | 无 | 缺少历史交易 tab |
| 风险指标面板 | 无 | 缺少 VaR/波动率等指标 |
| 资金曲线 | 无 | 缺少权益曲线图 |

## 四、实施步骤

### Step 1: 修复白屏问题 (5 个 fix)

1. useWebSocket 增加指数退避 + 最大重试次数
2. AppLayout WS 连接条件化
3. API client 添加 5s 超时
4. Data 页面 ErrorBoundary + mock fallback
5. Portfolio 页面超时 fallback + Skeleton

### Step 2: Data 页面 Spec 补齐

1. 添加缓存清除按钮
2. 添加数据源启用/禁用切换
3. 添加数据预览表格 (前 10 行)

### Step 3: Portfolio 页面 Spec 补齐

1. 添加历史交易记录 tab
2. 添加风险指标面板 (VaR/波动率/夏普)
3. 添加资金曲线图

### Step 4: 验证

- `npm run build` → 0 errors
- `npm test` → 0 failures
- 浏览器验证 Data 和 Portfolio 页面正常显示
