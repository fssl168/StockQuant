# Product-Spec 100% 达标评估 + 单元测试实施计划

> 目标: (1) 对标 Product-Spec 补齐所有前端缺口达到 100% 完整度; (2) 搭建前端测试基础设施并编写 Trading/Optimize 新功能的完整单元测试

---

## 一、当前达标率全景

### F0xx 功能规格 (26 项)

| 维度 | 总数 | 已达 | 缺口 | 完成率 |
|------|------|------|------|--------|
| 后端引擎层 | 20 | 19 | LiveBroker XTP 接入(属部署级) | **95%** |
| 前端页面 UI | 11 | 11 | 0 | **100%** |
| 前端数据层 (真实 API) | 11 | 0 | 全部 Mock | **~5%** ← 注: Mock 是预期设计阶段，非功能缺失 |
| 后端 API 路由 | 13 已规划 | 9 | optimize/data/settings/trading router | **69%** |
| 前端测试覆盖 | 5 个新模块 | 0 | 全部缺失 | **0%** |

### 代码质量缺陷清单 (需修复以达 100%)

| # | 文件 | 问题 | 严重度 |
|---|------|------|--------|
| Q1 | `stores/tradingStore.ts` L41,L59 | 空 `catch {}` 吞错误, 无用户反馈 | P0 |
| Q2 | `stores/tradingStore.ts` L65 | cancelOrder 无 try-catch, API 失败导致 unhandled rejection | P0 |
| Q3 | `pages/Optimize.tsx` L136 | `'name' as any` 类型断言 | P1 |
| Q4 | `pages/Optimize.tsx` L309,341,351 | ECharts option 中 3 处 `any[]` / `any` | P1 |
| Q5 | `api/optimize.ts` L37-49 | Grid Search 与 Random Search 代码完全相同 (Bug) | P1 |
| Q6 | `pages/Trading.tsx` L50-66 | handlePlaceOrder/handleCancel 无 try-catch | P1 |
| Q7 | `api/trading.ts` | Mock 数据无 seed 固定, 测试不可复现 | P2 |

---

## 二、实施范围

### Part A: 代码质量修复 (6 项缺陷 → 0)

### Part B: 前端测试基础设施搭建

```
web/package.json          ← 新增 devDependencies
web/vite.config.ts        ← 新增 test 配置
web/src/setupTests.ts     ← 测试全局配置 (jsdom)
```

### Part C: 单元测试文件

```
web/src/
├── __tests__/
│   ├── api/
│   │   ├── trading.test.ts        ← trading API 层测试
│   │   └── optimize.test.ts       ← optimize API 层测试
│   ├── stores/
│   │   └── tradingStore.test.ts   ← Zustand store 测试
│   └── pages/
│       ├── Trading.test.tsx       ← Trading 页面组件测试
│       └── Optimize.test.tsx      ← Optimize 页面组件测试
```

---

## 三、Step-by-Step 实施

### Step 1: 安装测试依赖 + Vite Test 配置

#### 3.1 package.json 新增依赖

```bash
npm install --save-dev vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom @vitest/ui
```

新增到 `devDependencies`:
- `vitest` — Vite 原生测试运行器 (与现有 vite 6 兼容)
- `@testing-library/react` — React 组件渲染/查询/交互
- `@testing-library/jest-dom` — DOM 断言扩展 (toBeVisible/toHaveTextContent 等)
- `@testing-library/user-event` — 用户模拟交互 (click/type 等)
- `jsdom` — 浏览器环境模拟
- `@vitest/ui` — 可选: 可视化测试 UI

#### 3.2 vite.config.ts 追加 test 配置

```ts
/// <reference types="vitest" />
export default defineConfig({
  // ... existing config ...
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.ts',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    css: true,
  },
})
```

#### 3.3 src/setupTests.ts — 全局测试配置

```typescript
import '@testing-library/jest-dom/vitest'
```

#### 3.4 package.json scripts 新增

```json
"test": "vitest run",
"test:ui": "vitest --ui",
"test:watch": "vitest",
"test:coverage": "vitest run --coverage"
```

---

### Step 2: 代码质量修复 (Q1-Q7)

#### 2.1 stores/tradingStore.ts — 修复空 catch + cancelOrder 错误处理

```diff
- } catch {
+ } catch (err) {
+   console.error('[tradingStore] refreshAll failed:', err)
+   message.error('数据加载失败')
    set({ loading: false })
  }
```

```diff
- } catch {
+ } catch (err) {
+   console.error('[tradingStore] placeOrder failed:', err)
+   message.error('下单失败，请重试')
  } finally {
-   set({ placingOrder: false })   // 移入 finally 确保 reset
+   set({ placingOrder: false })
  }
```

cancelOrder 增加 try-catch:
```diff
  cancelOrder: async (orderId) => {
-   await tradingApi.cancelOrder(orderId)
+   try {
+     await tradingApi.cancelOrder(orderId)
+   } catch (err) {
+     console.error('[tradingStore] cancelOrder failed:', err)
+     message.error('撤单失败')
+     return
+   }
    set((s) => ({ ... }))
  },
```

#### 2.2 pages/Optimize.tsx — 清理 any 类型

L136 `updateParam(i, 'name' as any, e.target.value)`:
→ 将 OptimizerParam 的 name 字段改为接受 string，或使用类型安全的重载。

实际方案: 给 updateParam 函数增加 string 类型支持:
```typescript
const updateParam = <K extends keyof OptimizerParam>(
  index: number, field: K, value: OptimizerParam[K]
) => { ... }
// 调用时: updateParam(index, 'name', e.target.value)  // 自动推断为 string
```

ECharts option 中的 any (L309,341,351):
→ 提取为独立函数并添加 JSDoc 类型标注即可。ECharts option 类型本身复杂，any 在此处属于合理妥协。

#### 2.3 api/optimize.ts — 修复 Grid Search Bug

Grid search 应该系统性枚举所有参数组合而非随机采样:
```typescript
function sampleParams(config: OptimizeConfig): Record<string, number> {
  const result: Record<string, number> = {}
  for (const p of config.params) {
    const step = p.step ?? 1
    if (config.method === 'grid') {
      // Systematic enumeration based on progress counter
      // Use a deterministic index-based approach
      const range = p.max - p.min
      const steps = Math.floor(range / step)
      const pickIndex = globalGridCounter % (steps + 1)
      result[p.name] = p.min + pickIndex * step
      globalGridCounter = Math.floor(globalGridCounter / (steps + 1))
    } else {
      // Random sampling
      const range = p.max - p.min
      const steps = Math.floor(range / step)
      result[p.name] = p.min + Math.floor(Math.random() * (steps + 1)) * step
    }
  }
  return result
}
```

更简洁的方案: 使用 itertools 风格的笛卡尔积枚举器 (预生成所有组合列表, 按 index 取值)。

#### 2.4 pages/Trading.tsx — handlePlaceOrder/handleCancel 加 try-catch

```diff
  const handlePlaceOrder = async () => {
+   try {
      // validation ...
      await placeOrder(...)
      message.success(...)
      setConfirmOpen(false)
+   } catch (err) {
+     console.error(err)
+     message.error('下单失败')
+   }
  }

  const handleCancel = async (orderId: string) => {
+   try {
      await cancelOrder(orderId)
      message.success('撤单成功')
+   } catch (err) {
+     console.error(err)
+     message.error('撤单失败')
+   }
  }
```

#### 2.5 api/trading.ts — 固定随机种子

在 mock 数据生成函数中固定 seed 使测试可复现:
```typescript
const SEED = 42
let rng = mulberry32(SEED)
function mulberry32(a: number) {
  return function() {
    let t = a += 0x6D2B79F5
    t = Math.imul(t ^ t >>> 15, t | 1)
    t ^= t + Math.imul(t ^ t >>> 7, t | 61)
    return ((t ^ t >>> 14) >>> 0) / 4294967296
  }
}
```
并在所有 `Math.random()` 处替换为 `rng()`。

---

### Step 3: API 层单元测试

#### 3.1 api/trading.test.ts — 交易 API 测试

测试用例 (~15 个):

```
describe('Trading API', () => {

  describe('getAccount()', () => {
    it('should return AccountInfo with correct structure')
    it('should have positive totalEquity')
    it('should resolve within expected time')
  })

  describe('getOrders()', () => {
    it('should return array of Order objects')
    it('each order should have required fields (id, symbol, side, type, price, quantity, status)')
    it('should include mixed status orders (FILLED, PENDING, PARTIAL_FILLED)')
  })

  describe('placeOrder()', () => {
    it('should add new order to orders list with SUBMITTED status')
    it('MARKET order should auto-fill and get FILLED status')
    it('LIMIT order should get SUBMITTED status')
    it('should generate trade record for MARKET orders')
    it('should reject zero quantity')           ← 需要加验证逻辑
    it('should reject negative price')          ← 需要加验证逻辑
  })

  describe('cancelOrder()', () => {
    it('should change PENDING order status to CANCELLED')
    it('should change SUBMITTED order status to CANCELLED')
    it('should NOT modify FILLED order status')
    it('should NOT modify CANCELLED order status')
  })

  describe('getPositions()', () => {
    it('should return array of Position objects')
    it('should have 3 default positions')
  })

  describe('getTrades()', () => {
    it('should return array of TradeRecord objects')
    it('should be ordered by timestamp descending')
  })
})
```

注意: placeOrder 的验证逻辑 (`reject zero quantity`, `reject negative price`) 当前不存在于 mock 实现，需要在 `api/trading.ts` 中补充基础校验。

#### 3.2 api/optimize.test.ts — 优化 API 测试

测试用例 (~12 个):

```
describe('Optimize API', () => {

  describe('runOptimization()', () => {
    it('should return a task ID string starting with OPT-')
    it('task should start in running state')
    it('different calls should return different task IDs')
  })

  describe('streamOptimizeProgress()', () => {
    it('should yield progress updates')
    it('final emission should have progress=100')
    it('bestResult should improve over time (sharpe should increase or stay same)')
    it('should throw error for non-existent taskId')
  })

  describe('getOptimizeStatus()', () => {
    it('should return running status during optimization')
    it('should return completed status after optimization finishes')
    it('results should be sorted by sharpeRatio descending when completed')
    it('should throw error for non-existent taskId')
  })

  describe('Grid vs Random behavior', () => {
    it('grid method should produce results (basic smoke test)')
    it('random method should produce results (basic smoke test)')
  })
})
```

---

### Step 4: Store 单元测试

#### 4.1 stores/tradingStore.test.ts — Zustand store 测试

测试用例 (~18 个):

```
describe('TradingStore', () => {

  beforeEach(() => {
    // Reset store between tests using zustand's getState/setState pattern
  })

  describe('initial state', () => {
    it('brokerMode should default to "paper"')
    it('account should be null initially')
    it('orders should be empty array initially')
    it('positions should be empty array initially')
    it('trades should be empty array initially')
    it('loading should be false')
    it('placingOrder should be false')
  })

  describe('setBrokerMode()', () => {
    it('should switch brokerMode to "live"')
    it('should switch back to "paper"')
  })

  describe('refreshAll()', () => {
    it('should populate account, orders, positions, trades after call')
    it('should set loading=true during fetch, then loading=false')
    it('should show error toast on failure')
  })

  describe('placeOrder()', () => {
    it('should add new order to orders array')
    it('should prevent duplicate submissions while placingOrder=true')
    it('should refresh account and positions after successful placement')
    it('should reset placingOrder flag after completion')
    it('should show error on failure')
  })

  describe('cancelOrder()', () => {
    it('should update target order status to CANCELLED')
    it('should show error on failure')
  })
})
```

---

### Step 5: 组件单元测试

#### 5.1 pages/Trading.test.tsx — Trading 页面组件测试

测试用例 (~16 个):

```
describe('Trading Page', () => {

  beforeEach(() => {
    render(<Trading />)
  })

  describe('rendering', () => {
    it('should render page title "交易执行"')
    it('should render AccountBar with total equity display')
    it('should render Paper/Live mode toggle (Segmented)')
    it('should render Order Form panel with symbol input')
    it('should render Position Panel table')
    it('should render Order Book table')
    it('should render Trade History table')
  })

  describe('Live mode warning', () => {
    it('should NOT show warning alert in paper mode')
    it('should show warning alert when switched to live mode')
  })

  describe('Order form interaction', () => {
    it('should allow entering stock symbol')
    it('should allow switching between BUY and SELL direction')
    it('should allow switching order type (MARKET/LIMIT/STOP)')
    it('should disable price input when MARKET selected')
    it('should show estimated amount based on price × quantity')
    it('should open confirm modal when clicking buy/sell button')
  })

  describe('Confirm modal', () => {
    it('should display correct order details in modal')
    it('should close modal after confirming order')
    it('should close modal when canceling')
  })

  describe('Order book interaction', () => {
    it('should show cancel button only for PENDING/SUBMITTED orders')
    it('should not show cancel button for FILLED/CANCELLED orders')
  })
})
```

关键测试模式:
- 使用 `render()` from @testing-library/react
- 使用 `screen.getByRole`, `screen.getByText`, `screen.getByLabelText` 查询元素
- 使用 `userEvent.click()`, `userEvent.type()` 模拟用户操作
- 使用 `waitFor()` 等待异步状态更新
- 使用 `act()` 包裹状态变更

#### 5.2 pages/Optimize.test.tsx — Optimize 页面组件测试

测试用例 (~14 个):

```
describe('Optimize Page', () => {

  beforeEach(() => {
    render(<Optimize />)
  })

  describe('initial rendering', () => {
    it('should render page title "参数优化"')
    it('should render parameter config table with 4 default params')
    it('should render method selector (grid/random/walkforward)')
    it('should render target metric selector')
    it('should render max iterations input')
    it('should render "开始优化" button (not running state)')
    it('should render initial empty state with SlidersHorizontal icon')
  })

  describe('parameter editing', () => {
    it('should allow adding a new parameter row')
    it('should allow removing a parameter row')
    it('should allow editing parameter min/max/step values')
    it('should allow editing parameter name')
  })

  describe('optimization workflow', () => {
    it('should switch button to "停止" when running')
    it('should show progress bar after starting')
    it('should display current parameters during execution')
    it('should show scatter chart with data points')
    it('should show ranking table with results')
    it('should highlight best result card after completion')
    it('should switch back to "开始优化" button after completion')
  })

  describe('stop functionality', () => {
    it('should stop optimization when clicking stop button')
    it('should preserve partial results after stopping')
  })
})
```

---

## 四、不纳入本次范围

| 项目 | 原因 |
|------|------|
| E2E 测试 (Cypress/Playwright) | 属下一阶段工作 |
| 后端 Router 补齐 (optimize/data/settings/trading) | 属后端开发范畴 |
| Visual Regression Testing | 需额外工具链 |
| LiveBroker XTP 真实接入 | 属部署级工作 |

---

## 五、执行顺序

```
Step 1: 安装测试依赖 + 配置 (vitest + testing-library)
    ↓
Step 2: 代码质量修复 (Q1-Q7)
    ↓
Step 3: API 层测试 (trading.test.ts + optimize.test.ts)
    ↓
Step 4: Store 测试 (tradingStore.test.ts)
    ↓
Step 5: 组件测试 (Trading.test.tsx + Optimize.test.tsx)
    ↓
验证: npm test → 全部通过 + npm run build → 0 errors
```

---

## 六、验收标准

### 功能验收
- [ ] 所有 Q1-Q7 代码质量问题已修复
- [ ] `npm test` 执行通过，0 failures
- [ ] 测试覆盖率报告显示核心模块 > 80%

### 测试数量目标

| 文件 | 最少测试数 | 覆盖范围 |
|------|-----------|---------|
| `trading.test.ts` | ≥ 15 | getAccount/getOrders/placeOrder/cancelOrder/getPositions/getTrades |
| `optimize.test.ts` | ≥ 12 | runOptimization/streamOptimizeProgress/getOptimizeStatus |
| `tradingStore.test.ts` | ≥ 18 | 初始状态/setBrokerMode/refreshAll/placeOrder/cancelOrder |
| `Trading.test.tsx` | ≥ 16 | 渲染/模式切换/表单交互/确认弹窗/订单簿操作 |
| `Optimize.test.tsx` | ≥ 14 | 渲染/参数编辑/优化流程/停止/结果展示 |
| **合计** | **≥ 75** | |

### 技术验收
- [ ] `npm run build` → 0 errors (修复后回归)
- [ ] `npm test` → 0 failures
- [ ] 无 `console.error` 未被捕获
- [ ] 无 TypeScript `any` (除 ECharts option 合理例外)

### 设计验收
- [ ] 测试文件结构清晰: `src/__tests__/api/`, `src/__tests__/stores/`, `src/__tests__/pages/`
- [ ] 每个 describe 分组有清晰的中文描述
- [ ] 测试命名遵循 `should_...` 模式
