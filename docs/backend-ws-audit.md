# 后端 WebSocket 通知 API 排查与修复计划

## 一、当前 WS 端点路径映射

### 后端注册路径 (FastAPI)

| 路由模块 | 装饰器路径 | prefix | 最终路径 |
|---------|-----------|--------|---------|
| main.py | `@app.websocket("/ws")` | 无 | `/ws` |
| notification.py | `@router.websocket("/ws/notification")` | `/api` | **`/api/ws/notification`** |
| monitor.py | `@router.websocket("/ws/monitor")` | `/api/monitor` | **`/api/monitor/ws/monitor`** |
| backtest.py | `@router.websocket("/ws/backtest/{task_id}")` | `/api` | **`/api/ws/backtest/{task_id}`** |
| ai_chat.py | `@router.websocket("/ws/chat/{conversation_id}")` | `/api` | **`/api/ws/chat/{conversation_id}`** |

### 前端连接路径

| 页面 | useWebSocket URL | 实际连接 |
|------|-----------------|---------|
| AppLayout.tsx:48 | `/api/ws/notification` | `ws://localhost:3000/api/ws/notification` |
| Monitor.tsx:29 | `/api/monitor/ws/monitor` | `ws://localhost:3000/api/monitor/ws/monitor` |
| Backtest.tsx:52 | `/api/ws/backtest/${taskId}` | `ws://localhost:3000/api/ws/backtest/${taskId}` |

### Vite 代理规则

| 匹配 | 目标 | WS 支持 |
|------|------|---------|
| `/api` | `http://localhost:8000` | ✅ ws: true |
| `/ws` | `ws://localhost:8000` | ✅ ws: true |

## 二、问题排查

### 问题 1: notification WS 路径不匹配 ❌

- **后端注册路径**: `notification.router` 的 prefix 是 `/api`，装饰器是 `/ws/notification`
- **最终路径**: `/api/ws/notification` ✅
- **前端连接**: `/api/ws/notification` ✅
- **Vite 代理**: `/api` 代理到 `http://localhost:8000`，WS 透传 ✅
- **结论**: 路径匹配正确

### 问题 2: monitor WS 路径不匹配 ❌

- **后端注册路径**: `monitor.router` 的 prefix 是 `/api/monitor`，装饰器是 `/ws/monitor`
- **最终路径**: `/api/monitor/ws/monitor`
- **前端连接**: `/api/monitor/ws/monitor` ✅
- **Vite 代理**: `/api` 代理到 `http://localhost:8000` ✅
- **结论**: 路径匹配正确，但路径设计不合理 (`/api/monitor/ws/monitor` 有冗余)

### 问题 3: backtest WS 路径

- **后端注册路径**: `backtest.router` 的 prefix 是 `/api`，装饰器是 `/ws/backtest/{task_id}`
- **最终路径**: `/api/ws/backtest/{task_id}` ✅
- **前端连接**: `/api/ws/backtest/${taskId}` ✅
- **结论**: 路径匹配正确

### 问题 4: 全局 WS 端点 `/ws` ❌

- **后端注册**: `@app.websocket("/ws")` — 在 main.py 中直接注册
- **前端**: 无连接
- **Vite 代理**: `/ws` 代理到 `ws://localhost:8000`
- **结论**: 端点存在但未被使用，无害

### 问题 5: ai_chat WS 端点

- **后端注册路径**: `/api/ws/chat/{conversation_id}`
- **前端**: AIChat.tsx 使用 SSE (fetch stream)，未使用 WS
- **结论**: 端点存在但前端未接入，无害

## 三、真正的问题

### 核心问题: 后端未启动时 WS 连接持续失败

前端 useWebSocket 在 `url` 非 null 时始终尝试连接。当后端不可达时:
1. WS 连接失败 → onclose 触发 → 指数退避重试 (1s→2s→4s) → 3 次后停止
2. Vite 代理 `/api` 的 WS 透传到 `localhost:8000`，后端未运行 → `ECONNREFUSED`
3. 每次页面加载都重复 3 次失败尝试

**已修复**: 上一轮已添加 `backendAvailable` 条件，后端不可达时不建立 WS 连接。

### 次要问题: WS 路径设计不一致

| 端点 | 当前路径 | 建议路径 |
|------|---------|---------|
| notification | `/api/ws/notification` | `/ws/notification` (统一到 /ws 前缀) |
| monitor | `/api/monitor/ws/monitor` | `/ws/monitor` (去掉冗余) |
| backtest | `/api/ws/backtest/{id}` | `/ws/backtest/{id}` (统一到 /ws 前缀) |
| chat | `/api/ws/chat/{id}` | `/ws/chat/{id}` (统一到 /ws 前缀) |

但修改路径需要同步修改前端和后端，风险较大。当前路径虽然不一致但功能正确。

## 四、修复方案

### Fix 1: 统一 WS 路径到 `/ws` 前缀 (可选, 低优先级)

将所有 WS 端点从各路由模块移到 main.py 统一注册，路径统一为 `/ws/*`:

```python
# main.py
@app.websocket("/ws/notification")
async def notification_ws(websocket: WebSocket):
    ...

@app.websocket("/ws/monitor")
async def monitor_ws(websocket: WebSocket):
    ...

@app.websocket("/ws/backtest/{task_id}")
async def backtest_ws(websocket: WebSocket, task_id: str):
    ...

@app.websocket("/ws/chat/{conversation_id}")
async def chat_ws(websocket: WebSocket, conversation_id: str):
    ...
```

前端同步修改:
- AppLayout: `/api/ws/notification` → `/ws/notification`
- Monitor: `/api/monitor/ws/monitor` → `/ws/monitor`
- Backtest: `/api/ws/backtest/${taskId}` → `/ws/backtest/${taskId}`

### Fix 2: 验证后端启动 (核心)

启动后端验证 WS 端点是否正常工作:

```bash
cd d:\leanpython\StockQuant
python -m stockquant.api.main
# 或
uvicorn stockquant.api.main:create_app --factory --port 8000
```

然后用浏览器访问 `ws://localhost:8000/ws/notification` 验证连接。

## 五、实施步骤

1. **验证后端能否启动** — 检查所有 import 是否正确，依赖是否齐全
2. **统一 WS 路径** — 将 WS 端点从路由模块移到 main.py，路径统一为 `/ws/*`
3. **同步前端路径** — 修改 3 个前端文件的 WS URL
4. **启动后端验证** — 运行 FastAPI，浏览器测试 WS 连接
5. **构建验证** — npm run build + npm test
