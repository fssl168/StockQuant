# StockQuant 前端功能差距评估报告

> 基准: `Product-Spec.md` v2.0.0-dev
> 范围: 全部 30 功能 (F001-F030) + 11 前端页面 + 19+ 组件 + 13 后端路由
> 综合达标率: **52% → 目标 100%**

---

## 一、功能逐项矩阵

### 核心引擎层 (F001-F015)

| F-code | 特性 | 后端 | 前端 | 状态 |
|--------|------|------|------|------|
| F001 | 事件驱动回测引擎 | ✅ | N/A | 已完成 |
| F002 | 订单管理系统 OMS | ✅ | ✅ | 已完成 |
| F003 | 投资组合模拟 | ✅ | ✅ | 已完成 |
| F004 | 策略框架 | ✅ | ✅ | 已完成 |
| F005 | 回测统计指标 30+ | ✅ | ✅ | 已完成 |
| F006 | Broker 抽象层 | ✅ | ✅ | 已完成 |
| F007 | 佣金与滑点建模 | ✅ | ✅ | 已完成 |
| F008 | 参数优化器 | ✅ | 🟡 | **Mock 引擎** (optimize.ts 282 行) |
| F009 | 风险管理模块 | ✅ | ✅ | 已完成 |
| F010 | 仓位管理模块 | ✅ | N/A | 已完成 |
| F011 | 数据层抽象 | ✅ | 🟡 | **K 线为 mock 数据** |
| F012 | 模拟盘模式 | ✅ | 🟡 | **hardcoded demo 数据** |
| F013 | 回测报表系统 | ✅ | ✅ | 已完成 |
| F014 | 内置策略模板 7 套 | ✅ | ✅ | 已完成 |
| F015 | 自定义指标 DSL | ✅ | N/A | 已完成 |

**核心层达标率: 87%**

### AI/前端/部署层 (F016-F030)

| F-code | 特性 | 后端 | 前端 | 状态 |
|--------|------|------|------|------|
| F016 | Web Dashboard (旧) | ❌ | ✅ React 替代 | 已替代 |
| F017 | 券商 API 实盘 | 骨架 | 🟡 | Live 不可用 |
| F018 | 消息推送系统 | 🟡 | ✅ | 通知路由需完善 |
| F019 | 信号管线系统 | ✅ | 🟡 | SignalCard 集成不足 |
| F020 | AI 信息处理 | 🟡 | 🟡 | 降噪/总结/升华缺失 |
| F021 | AI 指标发现 Agent | ✅ | ❌ | 无前端入口 |
| F022 | AI 策略生成 Agent | ✅ | ✅ | 已实现 |
| F023 | AI 回测解读 Agent | ✅ | ✅ | 已实现 |
| F024 | AI 实时盯盘 Agent | 🟡 | 🟡 | 部分实现 |
| F025 | AI 辅助决策 Agent | ✅ | ❌ | 无前端入口 |
| F026 | AI 动态风控 Agent | ✅ | 🟡 | 无动态 UI |
| F027 | AI 策略对比 Agent | 🟡 | ❌ | 无路由 |
| F028 | AI 自然语言交互 | 🟡 | 🟡 | 基础对话可用 |
| F029 | Web Dashboard 前端 | 🟡 | 🟡 | 大部分实现 |
| F030 | 前后端集成部署 | 🟡 | N/A | 需完善 |

**AI/前端层达标率: 55%**

---

## 二、P0 阻塞项 (必须解决)

| # | 问题 | 文件 | 严重性 |
|---|------|------|--------|
| 1 | optimize.ts 282 行全为 Mock | `web/src/api/optimize.ts` | 🔴 404 级 |
| 2 | Dashboard 3 个指标硬编码 | `Dashboard.tsx` L45-63 | 🔴 |
| 3 | Portfolio 权益曲线随机生成 | `portfolio.py` `_generate_equity_points` | 🔴 |
| 4 | Trading 后端 hardcoded demo 数据 | `trading.py` | 🔴 |
| 5 | AIChat 未使用 SSE 流式输出 | `AIChat.tsx` | 🟡 |
| 6 | Monitor 无真实 WS 行情 | `Monitor.tsx` | 🟡 |

---

## 三、Phase 执行计划

### Phase 1: 数据真实化 (P0)
1. Dashboard 移除硬编码 → 真实 API
2. Optimize 连接真实后端 (非 Mock)
3. Trading 真实撮合
4. K 线真实数据
5. Portfolio 真实数据

### Phase 2: 前端补全 (P1)
1. 设计 Token 统一
2. AIChat SSE 流式
3. 策略对比页面
4. Settings 后端对接
5. 下单确认弹窗

### Phase 3: 高级功能 (P1/P2)
1. Monitor WS 实时行情
2. AIChat 工具调用展示
3. F027 策略对比

### Phase 4: 部署安全 (P2)
1. Docker Compose
2. Nginx
3. JWT
4. Rate Limiting

---

## 四、执行策略

按 Phase 顺序: Phase 1 → Phase 2 → Phase 3 → Phase 4
自行判断优先级，持续开发直到 100% 功能达标。
