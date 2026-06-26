# 修复 `net::ERR_ABORTED http://localhost:3000/api/health`

## Summary
前端访问 `/api/health` 返回 `net::ERR_ABORTED` 错误，原因是后端服务未运行或无法连接。代码配置本身是正确的，问题出在运行时状态。

## Current State Analysis

### 配置验证（均正确）
| 组件 | 文件 | 状态 |
|------|------|------|
| Vite Proxy | [vite.config.ts](web/vite.config.ts#L16-L20) | `/api` → `http://localhost:8000` ✓ |
| 后端端点 | [main.py](stockquant/api/main.py#L298-L305) | `@app.get("/api/health")` GET 方法 ✓ |
| 前端调用 | [AppLayout.tsx](web/src/components/AppLayout.tsx#L80) | `fetch('/api/health', { method: 'GET' })` ✓ |

### 根因分析
`ERR_ABORTED` 表示请求被中止，最可能的原因：
1. **后端服务未启动** — 端口 8000 无服务监听，Vite proxy 连接失败导致请求中断
2. **后端启动时崩溃** — 服务开始监听但在处理请求前出错

## Proposed Changes

### Step 1: 检查后端运行状态
确认端口 8000 是否有进程在监听。

### Step 2: 启动/重启后端服务
如果后端未运行，执行：
```bash
cd d:\projects\StockQuant
python -m uvicorn stockquant.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 3: 验证修复
- 浏览器访问 `http://localhost:3000/api/health` 应返回 JSON
- 页面右上角应显示绿色状态点和延迟 ms 数

## Assumptions & Decisions
- 假设代码无语法错误（之前已修复过 main.py 的 `app = create_app()` 问题）
- 假设依赖已安装（python -m uvicorn 可用）

## Verification
1. 后端启动日志显示 `StockQuant API 网关启动`
2. 直接访问 `http://localhost:8000/api/health` 返回 `{"status":"ok",...}`
3. 前端页面不再报 ERR_ABORTED 错误
