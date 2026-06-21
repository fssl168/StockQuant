# 交易页前端白屏排查与修复

## Summary

交易页（`/trading`）白屏的根本原因是**前后端字段映射不匹配**。后端返回 snake_case 字段（经 client.ts 的 `snakeToCamel` 转为 camelCase 后），与前端 TypeScript 类型定义及 Table 组件的 `dataIndex`/`rowKey` 不一致。此外 AccountInfo 多个字段缺失，导致 `account?.marketValue`、`account?.dailyPnl` 始终为 undefined。

## Current State Analysis

### 后端路由（已正确）
- `main.py:96` — `app.include_router(trading.router, prefix="/api")` → 实际路径 `/api/trading/*`
- 前端 `api/trading.ts` 调用的路径 `/api/trading/account`、`/api/trading/orders` 等均正确

### 前端路由（已正确）
- `App.tsx:82` — `<Route path="/trading" element={<Trading />} />` 路由配置正确

### 字段映射问题（核心问题）

client.ts 的 `snakeToCamel` 会将 `order_id` → `orderId`、`trade_id` → `tradeId`、`filled_at` → `filledAt`、`position_value` → `positionValue`、`today_pnl` → `todayPnl`。

#### 1. AccountInfo 字段不匹配
后端 `/api/trading/account` 返回（camelCase 后）：
```
{ totalEquity, availableCash, positionValue, todayPnl, brokerMode }
```
前端 `AccountInfo` 类型期望：
```
{ totalEquity, cash, frozenCash, marketValue, availableCash, dailyPnl, dailyPnlPct }
```
- `marketValue` ← 后端返回 `positionValue`（缺失）
- `dailyPnl` ← 后端返回 `todayPnl`（缺失）
- `dailyPnlPct` ← 后端未返回（缺失）
- `cash`、`frozenCash` ← 后端未返回（缺失）

**影响**：账户栏"持仓市值""今日盈亏""日收益率"始终显示 0。不会白屏（有 `?? 0` 保护）。

#### 2. Order 字段不匹配（可能导致白屏）
后端 `/api/trading/orders` 返回（camelCase 后）：
```
{ orderId, symbol, side, type, price, quantity, status, createdAt, updatedAt }
```
前端 `Order` 类型及 Table 期望 `id` 字段。
- `rowKey="id"` → 找不到 key，React 警告
- `dataIndex: 'id'` → 取不到值，`t?.split('-')?.[1]` 有 `?.` 保护，不会崩溃

#### 3. TradeRecord 字段不匹配（可能导致白屏）
后端 `/api/trading/trades` 返回（camelCase 后）：
```
{ tradeId, orderId, symbol, side, price, quantity, amount, commission, filledAt }
```
前端 `TradeRecord` 类型及 Table 期望 `id` 和 `timestamp` 字段。
- `rowKey="id"` → 找不到 key
- `dataIndex: 'timestamp'` → 取不到值（后端返回 `filledAt`），`new Date(undefined)` 返回 Invalid Date，`toLocaleTimeString` 返回 "Invalid Date" 字符串

#### 4. 白屏触发点分析
如果后端接口报错（500）或返回非预期数据结构，`refreshAll` 的 `Promise.all` 会 reject，catch 中设置空数组并 `message.error`。此时页面应显示空表格，不应白屏。

**最可能的白屏原因**：如果后端返回了 `null` 或非数组作为 orders/positions/trades，且某些 render 函数未做 null 保护，如：
- `render: (n: number) => n.toLocaleString()` — 若 `n` 为 `null`/`undefined`，抛 TypeError
- `statusTag` 中 `const s = map[status]; return <Tag color={s.color}>` — 若 `status` 为 undefined，`s` 为 undefined，`s.color` 抛 TypeError

但正常情况下后端返回的数组元素都包含这些字段，所以白屏更可能是**后端接口未启动或返回 500**。

## Proposed Changes

### 方案：修改后端返回字段，对齐前端类型定义

修改 `stockquant/api/routers/trading.py`，在后端返回中添加前端期望的字段（向后兼容，不影响现有字段）：

#### Change 1: `get_account` 端点添加缺失字段
**文件**: `stockquant/api/routers/trading.py` 第478-490行
**原因**: 前端 `AccountInfo` 期望 `marketValue`、`dailyPnl`、`dailyPnlPct`、`cash`、`frozenCash`
**改法**: 在返回字典中添加这些字段（值从现有字段映射）

```python
@router.get("/trading/account", summary="账户信息")
async def get_account():
    acc = _portfolio.account
    positions = _portfolio.positions
    market_value = sum(p.market_value for p in positions.values() if p.quantity > 0)
    total_equity = acc.total_equity
    today_pnl = acc.unrealized_pnl
    return {
        "total_equity": round(total_equity, 2),
        "cash": round(acc.cash, 2),
        "frozen_cash": round(acc.cash - acc.available_cash, 2),
        "market_value": round(market_value, 2),
        "available_cash": round(acc.available_cash, 2),
        "daily_pnl": round(today_pnl, 2),
        "daily_pnl_pct": round(today_pnl / _initial_cash * 100, 2) if _initial_cash > 0 else 0,
        "position_value": round(market_value, 2),  # 保留向后兼容
        "today_pnl": round(today_pnl, 2),          # 保留向后兼容
        "broker_mode": "paper",
    }
```

#### Change 2: `get_orders` 端点添加 `id` 字段
**文件**: `stockquant/api/routers/trading.py` 第699-719行
**原因**: 前端 `Order` 类型和 Table `rowKey="id"` 期望 `id` 字段
**改法**: 在每个订单字典中添加 `"id": order_id`

#### Change 3: `get_trades` 端点添加 `id` 和 `timestamp` 字段
**文件**: `stockquant/api/routers/trading.py` 第679-696行
**原因**: 前端 `TradeRecord` 类型和 Table 期望 `id`（非 `tradeId`）和 `timestamp`（非 `filledAt`）
**改法**: 在每个成交字典中添加 `"id": trade_id` 和 `"timestamp": filled_at`

#### Change 4: `place_order` 端点审计日志添加 `id` 字段
**文件**: `stockquant/api/routers/trading.py` 第545-555行
**原因**: `place_order` 返回的审计日志也需要 `id` 字段
**改法**: 在 `_orders_audit[order_id]` 字典中添加 `"id": order_id`

### 可选：修改前端 render 函数增加 null 保护
**文件**: `web/src/pages/Trading.tsx`
**原因**: 防止后端返回异常数据时 render 函数崩溃
**改法**: 给所有 `render: (n: number) => n.toFixed(...)` 和 `n.toLocaleString()` 加上 `(n ?? 0)` 保护

## Assumptions & Decisions

- 假设后端服务正在运行（或即将启动），`/api/trading/*` 接口可访问
- 选择修改后端而非前端，因为前端类型定义已被多个文件引用，修改类型影响面大；后端添加字段是向后兼容的
- `position_value` 和 `today_pnl` 保留在返回中，不影响现有调用方
- 前端 render 函数的 null 保护作为防御性编程一并添加

## Verification Steps

1. 启动后端服务，确认 `/api/trading/account`、`/api/trading/orders`、`/api/trading/positions`、`/api/trading/trades` 均返回 200
2. 用 curl 或浏览器验证返回 JSON 包含 `id`、`market_value`、`daily_pnl`、`timestamp` 等字段
3. 前端 `npm run dev` 启动后访问 `http://localhost:3000/trading`
4. 确认页面不再白屏，账户栏显示正确的持仓市值和今日盈亏
5. 确认订单簿、持仓、成交记录表格正常渲染数据
6. 运行 `npm run build` 确认无类型错误
