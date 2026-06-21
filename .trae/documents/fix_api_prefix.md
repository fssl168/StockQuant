# 修复缺少 `/api` 前缀的 API 端点

## Summary

在 `web/src/` 目录下全面排查 API 调用，发现多处 HTTP 请求端点缺少 `/api` 前缀，导致请求 404。本次计划修复剩余 4 处问题。

## Current State Analysis

- `client.ts` 使用 `axios.create({ baseURL: import.meta.env.VITE_API_URL || '' })`，所有 API 请求路径需以 `/api/...` 开头
- `SentimentPanel.tsx` 的 `/ai/sentiment` 已在上一轮修复为 `/api/ai/sentiment`
- 搜索发现还有 4 处遗漏：
  1. `Login.tsx:18` — 注册接口 `/auth/register`
  2. `AppLayout.tsx:74` — 健康检查 `fetch('/health')`
  3. `notificationStore.ts:33` — 标记已读 `/notifications/${id}/read`
  4. `notificationStore.ts:39` — 删除通知 `/notifications/${id}`

## Proposed Changes

| 文件 | 位置 | 当前代码 | 修复后代码 |
|---|---|---|---|
| `web/src/pages/Login.tsx` | 第18行 | `.post('/auth/register', values)` | `.post('/api/auth/register', values)` |
| `web/src/components/AppLayout.tsx` | 第74行 | `fetch('/health', { method: 'GET' })` | `fetch('/api/health', { method: 'GET' })` |
| `web/src/stores/notificationStore.ts` | 第33行 | `client.put(\`/notifications/${id}/read\`)` | `client.put(\`/api/notifications/${id}/read\`)` |
| `web/src/stores/notificationStore.ts` | 第39行 | `client.delete(\`/notifications/${id}\`)` | `client.delete(\`/api/notifications/${id}\`)` |

## Assumptions & Decisions

- 假设后端所有业务 API 均统一挂载在 `/api` 前缀下（与已有正确调用一致）
- WebSocket 端点 `/ws/...` 不在本次修复范围，因其不属于 HTTP API 且已有独立前缀规范
- 不修改路由跳转路径（如 `navigate('/')`、`key: '/backtest'` 等），仅修复实际 HTTP 请求

## Verification Steps

1. 运行 `npm run dev` 启动前端
2. 打开浏览器访问 http://localhost:3000
3. 检查以下功能是否正常：
   - 注册页面提交后无 404
   - 顶部栏健康检查状态正常（显示延迟毫秒数）
   - 通知标记已读/删除无 404
