# Phase 3-4 实施计划

> Phase 1-2 已完成，本计划覆盖 Phase 3（高级功能 8 tasks）和 Phase 4（部署安全配置 9 tasks）
> 自行判断优先级、自行决策、持续开发直到 100% 功能达标

---

## 当前状态

- Phase 1 (7 tasks): 全部完成
- Phase 2 (13 tasks): 全部完成
- 达标率: ~52% → Phase 3-4 完成后预计达到 ~90%+

---

## Phase 3: 高级功能（8 tasks）

### Task 3.1: Monitor 实时 K 线图

**新建文件**: `web/src/components/Chart/RealtimeKline.tsx`

**实现方案**:
- ECharts candlestick 图表，复用现有暗色主题风格（bg: transparent, border: `#27272a`, label: `#a1a1aa`）
- Props: `{ symbol: string; data: KlineItem[]; height?: number; indicators?: string[] }`
- KlineItem: `{ date: string; open: number; high: number; low: number; close: number; volume: number }`
- 技术指标叠加：MA5/MA10/MA20（前端计算，line series 叠加）
- 成交量柱状图（底部 sub-grid，红涨绿跌）
- WS 实时更新：新 K 线追加到 data 数组末尾

**修改文件**: `web/src/pages/Monitor.tsx`
- 自选股表格增加"K线"操作按钮
- 点击弹出 Modal 展示 RealtimeKline
- 调用 `GET /api/data/kline?symbol=xxx&timeframe=d&start=xxx&end=xxx` 获取历史 K 线
- WS quote 消息实时更新最新 K 线的 close 价格

**修改文件**: `web/src/api/data.ts`
- 新增 `getKline(symbol, timeframe, start, end)` 方法

**后端**: 无需修改（data.py 已有 `/data/kline` 端点）

---

### Task 3.2: Monitor 社交媒体情绪监控

**新建文件**: `web/src/components/Monitor/SentimentPanel.tsx`

**实现方案**:
- 情绪仪表盘：ECharts gauge（0-100 分，红→黄→绿渐变）
- 情绪趋势图：ECharts line chart（近 7 天情绪分数变化）
- 热门话题列表：Tag 标签展示
- 数据来源：调用 `GET /api/ai/sentiment?symbol=xxx`（后端新增端点）

**修改文件**: `web/src/pages/Monitor.tsx`
- 右侧栏增加"情绪监控" Card，内嵌 SentimentPanel
- 选中自选股时展示该股票的情绪数据

**修改文件**: `stockquant/api/routers/ai_chat.py`
- 新增 `GET /api/ai/sentiment` 端点
- 调用 ChatAgent 分析新闻情绪，返回结构化数据：
  ```python
  {
    "symbol": "sh600519",
    "score": 72,  # 0-100
    "trend": [65, 68, 71, 69, 72, 75, 72],  # 近 7 天
    "topics": ["白酒涨价", "消费复苏", "北向资金"],
    "summary": "近期市场情绪偏乐观..."
  }
  ```
- MVP 实现：基于 search_news 工具结果 + 简单关键词分析

---

### Task 3.3: AIChat 对话式策略开发 (F028)

**修改文件**: `web/src/components/AI/ChatPanel.tsx`
- 新增"模式"切换：通用 / 策略开发 / 数据分析 / 盯盘
- 模式切换用 Segmented 组件（Ant Design 5）
- 策略开发模式：输入自然语言 → AI 生成策略代码 → 代码块增加"复制到策略编辑器"按钮
- 代码块检测：assistant 回复中 ```python 代码块自动识别，增加操作按钮

**修改文件**: `web/src/pages/AIChat.tsx`
- 传递 mode 状态给 ChatPanel
- 新增"复制到策略编辑器"处理函数：导航到 Strategy 页面并传递代码

**修改文件**: `stockquant/api/routers/ai_chat.py`
- 新增 `POST /api/ai/strategy/generate` 端点
- 接收 `{ description: str, strategy_type?: str }`
- 调用 ChatAgent 生成策略代码
- 返回 `{ code: str, name: str, description: str }`
- 同时修复 Strategy.tsx 前端已调用但后端缺失的问题

**修改文件**: `stockquant/ai/chat_tools.py`
- 新增 `generate_strategy` 工具函数

---

### Task 3.4: AIChat 对话式数据分析 (F028)

**修改文件**: `web/src/components/AI/ChatPanel.tsx`
- 数据分析模式：AI 回复中的 `tool_result` 如果包含 `chart_option`（ECharts option JSON），自动渲染 ECharts 图表
- 新增 `ChartRenderer` 子组件：检测 tool_result 中的 chart_option 字段，用 ReactECharts 渲染
- 图表交互：支持缩放、tooltip

**后端**: 无需修改（`generate_chart_json` 工具已存在，返回 ECharts option JSON）

---

### Task 3.5: AIChat 对话式盯盘 (F028)

**修改文件**: `web/src/components/AI/ChatPanel.tsx`
- 盯盘模式：用户输入"帮我盯 sh600519" → AI 调用 monitor API 启动监控
- 盯盘模式下的 tool_result 渲染：展示监控状态卡片（运行中/已停止、标的列表）
- AI 回复中包含信号时自动展示 SignalCard

**修改文件**: `stockquant/ai/chat_tools.py`
- 新增 `start_monitoring` 工具函数：调用 monitor API 启动监控
- 新增 `stop_monitoring` 工具函数：调用 monitor API 停止监控
- 新增 `get_monitoring_status` 工具函数：查询监控状态

**修改文件**: `stockquant/api/routers/ai_chat.py`
- 注册新工具到 ChatAgent

---

### Task 3.6: 策略对比历史 (F027)

**修改文件**: `stockquant/api/routers/comparison.py`
- 新增内存存储 `_comparison_history: list`（由 main.py 注入）
- `POST /comparison` 完成后保存结果到 `_comparison_history`
- `GET /comparison/history` 返回 `_comparison_history`
- 修复 `_compute_recent_performance` 私有方法调用问题

**修改文件**: `stockquant/api/main.py`
- 注入 `_comparison_history` 到 comparison 模块

**新建文件**: `web/src/components/Comparison/ComparisonChart.tsx`
- 雷达图：多策略多维度对比（收益率/夏普/最大回撤/胜率/盈亏比）
- 柱状图：关键指标横向对比
- 相关性热力图：策略间相关性矩阵

**修改文件**: `web/src/pages/Strategy.tsx`
- 新增"对比历史" Tab 或按钮
- 展示历史对比结果 + ComparisonChart

---

### Task 3.7: Portfolio 个股权益曲线

**修改文件**: `web/src/pages/Portfolio.tsx`
- 持仓表格 columns 增加"权益曲线"操作列
- 点击弹出 Modal 展示个股级别权益曲线
- 复用 EquityChart 组件
- 资金曲线数据从后端获取替换 mock 随机数据

**修改文件**: `stockquant/api/routers/portfolio.py`
- 新增 `GET /api/portfolio/equity-curve` 端点：返回整体资金曲线
- 新增 `GET /api/portfolio/equity-curve/{symbol}` 端点：返回个股权益曲线
- 数据来源：基于 _paper_positions 和 _trades 计算历史净值

**修改文件**: `web/src/api/portfolio.ts`（如存在）或 `web/src/api/client.ts`
- 新增 equityCurve API 方法

---

### Task 3.8: 通知路由实现

**修改文件**: `stockquant/api/routers/notification.py`
- 新增通知数据模型：
  ```python
  class NotificationItem:
      id: str
      type: str  # signal / alert / info
      title: str
      message: str
      time: str
      read: bool = False
  ```
- 新增内存存储 `_notifications: list[dict]`
- 实现 3 个端点：
  - `GET /api/notifications` — 返回通知列表（支持 ?type= 过滤）
  - `PUT /api/notifications/{id}/read` — 标记已读
  - `DELETE /api/notifications/{id}` — 删除通知
- WS 推送：新通知通过 ws_manager.push 到 "notification" channel

**修改文件**: `web/src/stores/notificationStore.ts`
- 新增 `markRead(id)` 方法
- 新增 `deleteNotification(id)` 方法
- 新增 `fetchFromBackend()` 方法：从后端加载通知
- NotificationItem 接口增加 `read` 字段
- 移除 mock 初始数据

**修改文件**: `web/src/pages/Monitor.tsx`
- 通知来源改为从 notificationStore 获取（已对接后端）

---

## Phase 4: 部署、安全与配置（9 tasks）

### Task 4.1: Docker Compose 更新

**修改文件**: `docker-compose.yml`
- 添加 PostgreSQL 服务：
  ```yaml
  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: stockquant
      POSTGRES_USER: stockquant
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-stockquant_secret}
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U stockquant"]
      interval: 10s
      timeout: 5s
      retries: 5
  ```
- 更新 backend depends_on 包含 postgres
- 更新 backend environment 添加全部环境变量
- 修复 ChromaDB healthcheck 端口（改为 `localhost:80`）

---

### Task 4.2: Nginx 反向代理配置

**新建文件**: `web/nginx/default.conf`

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;
    gzip_min_length 1000;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 代理
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
    }

    # WebSocket 代理
    location /ws/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    # 静态资源缓存
    location /assets/ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

**修改文件**: `web/Dockerfile`（如存在）
- 添加 Nginx 配置 COPY 指令

---

### Task 4.3: JWT 认证实现

**修改文件**: `stockquant/api/deps.py`
- 实现 JWT 编码/解码（使用 `python-jose`）：
  ```python
  from jose import JWTError, jwt
  from datetime import datetime, timedelta

  SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "stockquant-dev-secret-change-in-prod")
  ALGORITHM = "HS256"
  ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24h

  def create_access_token(data: dict) -> str:
      to_encode = data.copy()
      expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
      to_encode.update({"exp": expire})
      return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

  def decode_token(token: str) -> dict:
      return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
  ```
- 修改 `get_current_user` 实现 token 验证
- 新增 `User` 模型和密码哈希（`passlib[bcrypt]`）

**新建文件**: `stockquant/api/routers/auth.py`
- `POST /api/auth/login` — 用户名密码登录，返回 JWT token
- `POST /api/auth/register` — 注册（MVP 开放注册）
- `GET /api/auth/me` — 获取当前用户信息

**修改文件**: `stockquant/api/main.py`
- 注册 auth router
- MVP 阶段不强制认证（`get_current_user` 仍返回 anonymous），但端点可用

---

### Task 4.4: Rate Limiting

**修改文件**: `stockquant/api/main.py`
- 集成 slowapi：
  ```python
  from slowapi import Limiter, _rate_limit_exceeded_handler
  from slowapi.util import get_remote_address
  from slowapi.errors import RateLimitExceeded

  limiter = Limiter(key_func=get_remote_address)
  app.state.limiter = limiter
  app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
  ```
- 全局默认 100 req/min
- 关键端点自定义限流：
  - `/api/auth/login`: 5 req/min
  - `/api/ai/chat`: 20 req/min
  - `/api/backtest/submit`: 10 req/min

**依赖**: 需安装 `slowapi`

---

### Task 4.5: API Key 加密存储

**修改文件**: `stockquant/api/routers/settings.py`
- 引入 `cryptography.fernet.Fernet` 加密
- 加密密钥从环境变量 `SQ_ENCRYPTION_KEY` 读取，不存在则自动生成并保存到 `~/.stockquant/.encryption_key`
- 保存时：检测 `_SENSITIVE_KEYS` 列表（`ai.api_key`, `data_provider.api_key` 等），加密后存储
- 读取时：自动解密
- `GET /settings` 返回时对敏感字段掩码（`sk-****1234` 格式，保留后 4 位）

---

### Task 4.6: 前端环境变量补全

**新建文件**: `web/.env`
```
VITE_API_URL=/api
VITE_WS_URL=
VITE_API_HOST=
```

**新建文件**: `web/.env.production`
```
VITE_API_URL=/api
VITE_WS_URL=
VITE_API_HOST=
```

**修改文件**: `web/src/api/client.ts`
- baseURL 改为 `import.meta.env.VITE_API_URL || '/api'`

**修改文件**: `web/src/hooks/useWebSocket.ts`
- WS URL 改为优先使用 `import.meta.env.VITE_WS_URL`

**修改文件**: `web/src/pages/Strategy.tsx`
- `fetch('/api/ai/strategy/generate')` 改为使用 `client` 实例

---

### Task 4.7: 后端 .env 变量全量消费

**修改文件**: `stockquant/api/routers/ai_chat.py`
- 显式消费 OPENAI_API_KEY / OPENAI_API_BASE / OPENAI_MODEL / OPENAI_MAX_TOKENS / OPENAI_TEMPERATURE
- 通过 `from stockquant.api.routers.settings import _settings` 统一读取

**修改文件**: `stockquant/api/routers/data.py`
- 消费 TUSHARE_TOKEN / AKSHARE_PROXY / CACHE_DIR

**修改文件**: `stockquant/api/routers/trading.py`
- 消费 QMT_PATH / QMT_ACCOUNT / QMT_PASSWORD

**修改文件**: `stockquant/api/routers/notification.py`
- 消费 WECHAT_WEBHOOK_URL / DINGTALK_WEBHOOK_URL / SMTP_* / EMAIL_*

**统一入口**: 所有路由通过 `settings._settings` 字典读取配置，不再各自 `os.environ.get()`

---

### Task 4.8: stockquant_config.yaml 配置文件

**新建文件**: `stockquant/config.py`
```python
"""配置加载模块 — 支持 YAML + .env + Settings API 三级配置"""
import yaml
from pathlib import Path

_CONFIG_FILE = Path.home() / ".stockquant" / "stockquant_config.yaml"

def load_config() -> dict:
    """加载 YAML 配置文件"""
    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    return {}

_config_cache = None

def get_config() -> dict:
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache

def reload_config():
    global _config_cache
    _config_cache = load_config()
```

**新建文件**: `stockquant_config.yaml`（模板，放在项目根目录）
```yaml
# StockQuant 配置模板
ai:
  model: gpt-4o
  temperature: 0.7
  max_tokens: 4096

data:
  provider: baostock
  cache_dir: ~/.stockquant/cache

trading:
  broker: paper
  commission_rate: 0.0003

monitor:
  scan_interval: 30
  alert_threshold: 3.0

notification:
  enabled_channels: [websocket]
```

**修改文件**: `stockquant/api/main.py`
- 启动时调用 `config.load_config()` 并注入到 settings 模块

**修改文件**: `stockquant/api/routers/settings.py`
- 配置优先级链: Settings API (JSON) > YAML > .env > 代码默认值

---

### Task 4.9: Settings API 与 .env 完整联动

**修改文件**: `stockquant/api/routers/settings.py`
- `GET /settings` 返回值增加 `source` 字段标注来源（override / yaml / env / default）
- 保存后热生效：通知相关模块重新初始化（如 AI Agent 重新创建）
- `DELETE /settings/{key}` 回退到 .env 值（而非代码默认值）
- `GET /settings/whitelist` 返回所有可配置项及来源

---

## 执行顺序

Phase 3 按依赖关系排序：
1. **3.8** 通知路由（基础依赖，其他模块可能需要通知能力）
2. **3.1** 实时 K 线图（Monitor 核心功能）
3. **3.7** Portfolio 个股权益曲线（独立功能）
4. **3.6** 策略对比历史（独立功能）
5. **3.3** AIChat 策略开发（修复后端缺失端点）
6. **3.4** AIChat 数据分析（依赖 3.3 的模式框架）
7. **3.5** AIChat 盯盘（依赖 3.3 的模式框架）
8. **3.2** 情绪监控（独立功能，可最后）

Phase 4 按依赖关系排序：
1. **4.6** 前端环境变量（基础配置）
2. **4.8** YAML 配置文件（基础配置）
3. **4.7** 后端 .env 变量全量消费（依赖 4.8）
4. **4.9** Settings API 完整联动（依赖 4.8）
5. **4.5** API Key 加密存储（依赖 4.9）
6. **4.3** JWT 认证（安全基础）
7. **4.4** Rate Limiting（安全基础）
8. **4.2** Nginx 配置（部署基础）
9. **4.1** Docker Compose 更新（部署基础）

---

## 关键设计决策

1. **K 线技术指标前端计算**: MA/EMA 在前端计算，避免后端重复实现，减少 API 传输量
2. **情绪分析 MVP**: 基于新闻关键词简单分析，不依赖外部 NLP API
3. **AIChat 模式切换**: 使用 Ant Design Segmented 组件，4 种模式共享 ChatPanel 但切换工具集
4. **通知内存存储**: MVP 阶段使用内存 list，重启清空，后续迁移数据库
5. **JWT 认证 MVP**: 实现完整但不强制，`get_current_user` 仍返回 anonymous，端点可用但不受保护
6. **配置三级优先级**: Settings API (JSON) > YAML > .env > 代码默认值
7. **加密密钥管理**: 从环境变量读取，不存在则自动生成并保存到本地文件

---

## 验证方式

每个 Task 完成后：
1. 后端: 启动 Uvicorn，用 curl 测试 API 端点
2. 前端: 启动 Vite，在浏览器验证页面功能
3. 集成: 前端调用后端 API 验证数据流
4. TypeScript: 运行 `npm run typecheck` 确保无类型错误
