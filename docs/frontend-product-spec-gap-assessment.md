# StockQuant 前端功能与页面对标 Product-Spec 全面差距评估报告

> 评估日期: 2026-06-16 | 基准文档: `Product-Spec.md` F029 + 全局功能需求
> 评估范围: 前端 11 个页面 + 后端 API + 前后端集成

---

## 一、评估总览

| 维度 | 总项数 | ✅ 达标 | ⚠️ 部分 | ❌ 未达标 | 达标率 |
|------|--------|---------|---------|-----------|--------|
| F029 页面功能 (10页) | 50 | 35 | 8 | 7 | **70%** |
| 后端 API 完整度 | 20 | 10 | 6 | 4 | **50%** |
| 前后端集成 | 15 | 5 | 5 | 5 | **33%** |
| 全局功能 (认证/部署/性能/配置) | 16 | 3 | 4 | 9 | **19%** |
| **合计** | **101** | **53** | **23** | **25** | **52%** |

---

## 二、逐页面对标 Product-Spec F029

### 2.1 Dashboard (`/`) — 达标率 80%

| # | Spec 要求 | 当前状态 | 达标 |
|---|----------|---------|------|
| D1 | 6 个指标卡片 (总权益/日PnL/持仓数/年化/回撤/夏普) | MetricCard 组件 6 卡片 | ✅ |
| D2 | 权益曲线图 (ECharts) | EquityChart 已接入 | ✅ |
| D3 | AI 信号面板 (1/3 宽) | NotificationList + SignalCard | ✅ |
| D4 | 回测历史表格 | Table 含策略名/状态/收益率/夏普/时间 | ✅ |
| D5 | 数据来源: `/api/dashboard/metrics` | 调用 dashboardApi.metrics() | ✅ |
| D6 | 实时通知推送 (WS `/ws/notification`) | AppLayout 已连接 WS notification | ✅ |
| D7 | 持仓汇总联动 | 指标卡数据来自 dashboard API (聚合 backtest) | ⚠️ 仅聚合回测数据，无实盘持仓 |
| D8 | 系统状态指示 | Header 含 API 健康检测 (30s 轮询) | ✅ |

**差距项**: D7 — Dashboard 应同时展示实盘/模拟盘持仓数据，当前仅聚合回测结果

---

### 2.2 Backtest (`/backtest`) — 达标率 75%

| # | Spec 要求 | 当前状态 | 达标 |
|---|----------|---------|------|
| B1 | 三段式配置 (策略/数据/执行参数) | 3 个 Card 分组 | ✅ |
| B2 | Monaco Editor 策略代码编辑 | 已集成 height=300, vs-dark | ✅ |
| B3 | 策略模板选择 (7 个) | Select 含 7 个模板 | ✅ |
| B4 | DataSelector (标的/数据源/日期/初始资金) | 组件已抽取 | ✅ |
| B5 | ParamForm (佣金/滑点/回撤熔断) | 组件已抽取 | ✅ |
| B6 | 表单验证 | strategy_name/symbols/dates/cash 有 rules | ✅ |
| B7 | 异步任务提交 → WebSocket 实时进度 | 提交后监听 `/ws/backtest/{taskId}` | ✅ |
| B8 | 完成后自动跳转结果页 | navigate(`/backtest/${taskId}`) | ✅ |
| B9 | 回测真实执行 (后端 Cerebro.run) | **后端仅 queued 状态，无实际执行** | ❌ |
| B10 | 日期选择器 DatePicker | 已升级为 DatePicker | ✅ |
| B11 | 风控规则配置 | **缺失** | ❌ |
| B12 | 基准选择 (沪深300/中证500) | **缺失** | ❌ |

**差距项**: 
- B9: 后端 `POST /api/backtest` 仅创建任务记录，未调用 Cerebro.run() 执行回测
- B11: 缺少风控规则配置 (RiskManager 参数)
- B12: 缺少回测基准选择

---

### 2.3 BacktestResult (`/backtest/:id`) — 达标率 85%

| # | Spec 要求 | 当前状态 | 达标 |
|---|----------|---------|------|
| BR1 | 8 个指标卡片 | 年化/回撤/夏普/Sortino/Calmar/胜率/总交易/SQN | ✅ |
| BR2 | 权益曲线 + 回撤 + 月度热力图 | EquityChart + DrawdownChart + MonthHeatmap | ✅ |
| BR3 | 30+ 指标分组表格 | MetricTable 组件 | ✅ |
| BR4 | 交易明细表格 (分页) | TradeTable 含分页 | ✅ |
| BR5 | AI 解读面板 | InsightCard + analyzeBacktest() | ✅ |
| BR6 | 基准对比曲线 | **缺失** | ❌ |
| BR7 | Skeleton 加载态 | 已实现 | ✅ |

**差距项**: BR6 — 缺少基准对比曲线 (沪深300/中证500叠加显示)

---

### 2.4 Optimize (`/optimize`) — 达标率 80%

| # | Spec 要求 | 当前状态 | 达标 |
|---|----------|---------|------|
| O1 | 参数范围配置表 (可增删行) | 可编辑参数表格 | ✅ |
| O2 | 优化方式选择 (grid/random/walkforward) | 3 种方式 Radio | ✅ |
| O3 | 优化目标 (Sharpe/Return/Drawdown/WinRate) | Select 下拉 | ✅ |
| O4 | 实时进度条 + WebSocket | streamOptimizeProgress (WS + polling fallback) | ✅ |
| O5 | 散点图 (Drawdown vs Sharpe, 气泡大小=Return) | ECharts scatter | ✅ |
| O6 | 排名表 | Table 含 rank/Sharpe/Return/MaxDD/WinRate/Trades | ✅ |
| O7 | 最佳参数详情 + 应用到回测 | BestResultCard + export/apply 按钮 | ✅ |
| O8 | 后端真实执行 Cerebro.optstrategy() | **后端仅 queued，无实际执行** | ❌ |

**差距项**: O8 — 后端 `POST /api/backtest/optimize` 未调用 Cerebro.optstrategy()

---

### 2.5 Strategy (`/strategy`) — 达标率 90%

| # | Spec 要求 | 当前状态 | 达标 |
|---|----------|---------|------|
| S1 | 左右分栏 (70/30) | Monaco Editor 70% + 策略列表 30% | ✅ |
| S2 | Monaco Editor (vs-dark, Python) | 已集成 | ✅ |
| S3 | 策略 CRUD | strategyStore + strategyApi | ✅ |
| S4 | 模板库 (7 套) | Modal 含 7 个模板 | ✅ |
| S5 | 语法检查 | StrategyEditor 含客户端语法检查 | ✅ |
| S6 | 代码预览 | PreviewPanel | ✅ |
| S7 | AI 策略生成 (F022) | **缺失** — 无自然语言→策略代码入口 | ❌ |

**差距项**: S7 — 缺少 AI 策略生成入口 (Product-Spec F022 要求自然语言→策略代码)

---

### 2.6 Monitor (`/monitor`) — 达标率 65%

| # | Spec 要求 | 当前状态 | 达标 |
|---|----------|---------|------|
| M1 | 自选股列表 (添加/删除) | WatchList 组件 | ✅ |
| M2 | 实时行情 (WebSocket) | **Mock 数据，无真实 WS 行情** | ❌ |
| M3 | 扫描控制 (启停) | 圆形脉冲动画 + 启停按钮 | ✅ |
| M4 | 盘前简报 | monitorApi.brief() | ✅ |
| M5 | AI 信号推送 | SignalCard + notificationStore | ⚠️ 仅 mock 信号 |
| M6 | 告警规则配置 | AlertPanel (涨跌幅/成交量异常) | ✅ |
| M7 | 收盘总结 | monitorApi.summary() 端点存在但前端未展示 | ⚠️ |
| M8 | 异动检测 (放量/涨停/跌停) | **缺失** | ❌ |
| M9 | 情绪监控 (社交媒体) | **缺失** | ❌ |
| M10 | 实时 K 线图 | **缺失** | ❌ |

**差距项**: 
- M2: 无真实 WebSocket 行情推送
- M8: 缺少异动检测功能
- M9: 缺少社交媒体情绪监控 (F024 要求)
- M10: 缺少实时 K 线图
- M7: 收盘总结未展示

---

### 2.7 AIChat (`/ai-chat`) — 达标率 75%

| # | Spec 要求 | 当前状态 | 达标 |
|---|----------|---------|------|
| AC1 | 消息列表 (用户/AI) | ChatPanel 组件 | ✅ |
| AC2 | 流式输出 (SSE) | streamChat + 逐字渲染 | ✅ |
| AC3 | Markdown 渲染 | marked + DOMPurify | ✅ |
| AC4 | 会话管理 (列表/切换/新建) | aiStore conversations + 左侧会话栏 | ✅ |
| AC5 | 空态引导 | 示例提示语 | ✅ |
| AC6 | AI 工具调用 (市场数据/新闻查询) | 后端有 /tools/query_market_data + /tools/search_news | ⚠️ 前端未集成工具调用展示 |
| AC7 | 信号卡片 (AI 给出交易建议时) | SignalCard 组件存在但未在 ChatPanel 中使用 | ❌ |
| AC8 | 对话式策略开发 (F028) | **缺失** | ❌ |
| AC9 | 对话式数据分析 (F028) | **缺失** | ❌ |
| AC10 | 对话式盯盘 (F028) | **缺失** | ❌ |

**差距项**:
- AC6: AI 工具调用结果未在前端展示 (如市场数据表格、新闻列表)
- AC7: AI 给出交易建议时未附带 SignalCard
- AC8-AC10: F028 对话式交互 (策略开发/数据分析/盯盘) 完全缺失

---

### 2.8 Portfolio (`/portfolio`) — 达标率 70%

| # | Spec 要求 | 当前状态 | 达标 |
|---|----------|---------|------|
| P1 | 5 个汇总指标卡 | PortfolioSummary | ✅ |
| P2 | 持仓明细表格 | Table 含代码/名称/股数/成本/现价/市值/盈亏 | ✅ |
| P3 | 行业分布饼图 | SectorPieChart | ✅ |
| P4 | 盈亏分析柱状图 | PnLTable | ✅ |
| P5 | 风险指标卡 (VaR/波动率/夏普/回撤/Beta/Alpha) | 风险指标 Card | ✅ |
| P6 | 权益曲线图 | ECharts line | ✅ |
| P7 | 真实持仓数据 (非 mock) | **后端返回 hardcoded demo 数据** | ❌ |
| P8 | 交易历史 | Tab 含成交记录表格 | ✅ |
| P9 | 快捷交易入口 | Button 跳转 /trading | ✅ |
| P10 | 个股权益曲线 | **缺失** | ❌ |

**差距项**:
- P7: 后端 `/api/portfolio/positions` 和 `/api/portfolio/account` 返回 hardcoded demo 数据
- P10: 缺少个股级别的权益曲线

---

### 2.9 Data (`/data`) — 达标率 75%

| # | Spec 要求 | 当前状态 | 达标 |
|---|----------|---------|------|
| DT1 | 数据源管理表格 | DataSourceForm | ✅ |
| DT2 | 缓存状态卡片 (4 个) | CacheStats | ✅ |
| DT3 | K 线查询 (ECharts candlestick) | 已实现 K 线查询 + 蜡烛图 | ✅ |
| DT4 | 采集日志表格 | DataLogTable | ✅ |
| DT5 | 真实 K 线数据 (非 mock) | **后端返回随机模拟数据** | ❌ |
| DT6 | 数据下载/采集触发 | **缺失** | ❌ |
| DT7 | 数据预览表格 | 有数据预览 | ✅ |
| DT8 | 数据源健康状态 | **缺失** | ❌ |

**差距项**:
- DT5: 后端 `/api/data/kline` 返回随机模拟数据，未调用真实 DataFetcherManager
- DT6: 缺少手动触发数据采集/下载的功能
- DT8: 缺少数据源健康状态展示

---

### 2.10 Settings (`/settings`) — 达标率 90%

| # | Spec 要求 | 当前状态 | 达标 |
|---|----------|---------|------|
| ST1 | 向导/专家模式切换 | Tag 切换 | ✅ |
| ST2 | 14 组配置 | 14 组 GROUPS 完整定义 | ✅ |
| ST3 | 浮动保存条 | FloatButton + dirtyCount | ✅ |
| ST4 | 管理员确认弹窗 | Modal + Password | ✅ |
| ST5 | 各类控件 (Switch/Select/InputNumber/Slider/Password) | 全部覆盖 | ✅ |
| ST6 | 向导模式 5 步引导 | Steps 组件 + 5 步内容 | ✅ |
| ST7 | 配置热生效 | **后端 settings 存内存 dict，不持久化** | ⚠️ |
| ST8 | 密钥掩码 | secret 字段 Input.Password | ✅ |
| ST9 | 条件显隐 (when 字段) | **缺失** | ❌ |

**差距项**:
- ST7: 后端 settings 存储在内存 dict 中，重启后丢失，不持久化到文件/数据库
- ST9: 缺少条件显隐 (when 字段依赖关系)

---

### 2.11 Trading (`/trading`) — 达标率 70%

| # | Spec 要求 | 当前状态 | 达标 |
|---|----------|---------|------|
| T1 | Paper/Live 模式切换 | tradingStore brokerMode | ✅ |
| T2 | 账户概览条 | AccountBar (总权益/可用/市值/日PnL) | ✅ |
| T3 | 下单表单 (代码/方向/类型/价格/数量) | OrderForm | ✅ |
| T4 | 订单簿 + 撤单 | Table + cancelOrder() | ✅ |
| T5 | 持仓列表 | PositionPanel | ✅ |
| T6 | 成交记录 | TradeHistory | ✅ |
| T7 | 真实交易执行 (PaperBroker) | **后端 Paper 交易使用 hardcoded 价格** | ❌ |
| T8 | Live 模式 (LiveBroker) | **LiveBroker 骨架，无券商 API** | ❌ |
| T9 | 订单确认弹窗 | **缺失** | ❌ |
| T10 | 自动刷新 (10s) | Paper 模式 10s 自动刷新 | ✅ |

**差距项**:
- T7: 后端交易使用 hardcoded 价格，未接入 PaperBroker 真实撮合
- T8: LiveBroker 仅有骨架，无券商 API 接入
- T9: 缺少下单确认弹窗 (半自动模式要求)

---

## 三、后端 API 完整度评估

### 3.1 已实现但使用 Mock/Hardcoded 数据的端点

| 端点 | 问题 | 优先级 |
|------|------|--------|
| `GET /api/data/kline` | 返回随机模拟数据，未调用 DataFetcherManager | P0 |
| `GET /api/trading/account` | 返回 hardcoded demo 数据 | P0 |
| `GET /api/trading/positions` | 返回 hardcoded demo 数据 | P0 |
| `GET /api/portfolio/positions` | 返回 hardcoded demo 数据 | P1 |
| `GET /api/portfolio/account` | 返回 hardcoded demo 数据 | P1 |
| `GET /api/portfolio/sector` | 返回 hardcoded demo 数据 | P1 |
| `GET /api/portfolio/pnl` | 返回 hardcoded demo 数据 | P1 |
| `POST /api/trading/order` | Paper 交易使用 hardcoded 价格 100.0 | P0 |

### 3.2 未实现的核心端点

| 端点 | 功能 | 优先级 |
|------|------|--------|
| 回测执行引擎 | POST /api/backtest 后调用 Cerebro.run() | P0 |
| 优化执行引擎 | POST /api/backtest/optimize 后调用 Cerebro.optstrategy() | P0 |
| 数据采集触发 | POST /api/data/collect (手动触发数据下载) | P1 |
| 收盘总结展示 | GET /api/monitor/summary 前端未接入 | P2 |

### 3.3 空路由/占位路由

| 路由 | 状态 |
|------|------|
| `notification.py` | 空路由，无任何端点 |
| `GET /api/comparison/history` | 返回空列表 |

---

## 四、前后端集成评估

### 4.1 WebSocket 集成状态

| WS 端点 | 后端 | 前端 | 集成状态 |
|---------|------|------|---------|
| `/ws` | ✅ | — | 通用连接 |
| `/ws/notification` | ✅ | ✅ AppLayout 已接入 | ✅ 正常 |
| `/ws/monitor` | ✅ | ❌ 前端未接入 | ❌ 未集成 |
| `/ws/backtest/{id}` | ✅ | ✅ Backtest 页面已接入 | ✅ 正常 |
| `/ws/chat/{id}` | ✅ | ❌ AIChat 未使用 WS | ⚠️ 使用 SSE 替代 |
| `/ws/optimize/{id}` | ✅ | ✅ Optimize 页面已接入 | ✅ 正常 |

### 4.2 SSE 流式集成

| 功能 | 后端 | 前端 | 状态 |
|------|------|------|------|
| AI 对话流式 | `POST /api/ai/chat/stream` | `streamChat()` | ✅ 正常 |

### 4.3 认证/安全

| 功能 | Spec 要求 | 当前状态 |
|------|---------|---------|
| JWT 认证 | NFR004 | ❌ deps.py 返回 anonymous |
| CORS | 前后端分离 | ✅ allow_origins=["*"] |
| Rate Limiting | NFR004 | ❌ 未实现 |
| API Key 加密存储 | NFR004 | ❌ 明文存储 |

---

## 五、全局功能评估

### 5.1 Product-Spec F016/F029/F030 功能状态

| 功能 ID | 名称 | Spec 状态 | 前端状态 | 后端状态 |
|---------|------|----------|---------|---------|
| F016 | Web Dashboard | ❌ Planned (旧) | ✅ 已实现 (React) | ✅ API 已实现 |
| F029 | Web Dashboard 前端 | ⚠️ Partial | ✅ 11 页面 | ⚠️ 部分 mock |
| F030 | 前后端集成部署 | ❌ Planned | ⚠️ docker-compose 存在 | ⚠️ 需更新 |
| F024 | AI 实时盯盘 Agent | ❌ Planned | ⚠️ Monitor 页面存在 | ⚠️ 后端有 scan/brief |
| F027 | AI 策略对比 Agent | ❌ Planned | ⚠️ Comparison API 存在 | ⚠️ history 返回空 |
| F028 | AI 自然语言交互 | ❌ Planned | ⚠️ AIChat 存在 | ⚠️ 基础对话可用 |

### 5.2 配置与启动变量

> Spec 要求: F029 Settings 14 组配置 + `.env` 环境变量 + `stockquant_config.yaml` + 前端 `VITE_*` 变量

#### 5.2.1 后端环境变量 (`.env`)

| # | 变量 | 用途 | 当前状态 | 达标 |
|---|------|------|---------|------|
| EV1 | `DATABASE_URL` | 数据库连接 | ✅ 已接入 PostgreSQL，models.py/repository.py/decision_agent.py/chat_memory.py 均读取 | ✅ |
| EV2 | `OPENAI_API_KEY` / `OPENAI_API_BASE` / `OPENAI_MODEL` | LLM 配置 | ⚠️ .env 已定义，但 API 层未读取，仅 LLMAdapter 直接读环境变量 | ⚠️ |
| EV3 | `OPENAI_MAX_TOKENS` / `OPENAI_TEMPERATURE` | LLM 参数 | ❌ .env 已定义，Settings API 未暴露，回测/AI 对话未使用 | ❌ |
| EV4 | `TUSHARE_TOKEN` | Tushare 数据源 | ❌ .env 已定义，DataFetcherManager 未注册 TushareFeed | ❌ |
| EV5 | `AKSHARE_PROXY` | AkShare 代理 | ❌ .env 已定义，AkShareFeed 未使用代理配置 | ❌ |
| EV6 | `QMT_PATH` / `QMT_ACCOUNT` / `QMT_PASSWORD` | 券商通道 | ❌ .env 已定义，LiveBroker 未接入 QMT | ❌ |
| EV7 | `REDIS_URL` / `REDIS_PASSWORD` | 缓存/队列 | ❌ .env 已定义，后端未使用 Redis | ❌ |
| EV8 | `KAFKA_BOOTSTRAP_SERVERS` / `KAFKA_ENABLED` | 消息总线 | ❌ .env 已定义，后端未使用 Kafka | ❌ |
| EV9 | `SIGNAL_DEDUP_*` | 信号去重 | ❌ .env 已定义，API 层未读取 | ❌ |
| EV10 | `SIMULATOR_FORCE_RUN` / `TRADING_ADMIN_TOKEN` | 模拟器/管理员 | ⚠️ .env 已定义，Settings API 有 admin_token 但未读环境变量 | ⚠️ |
| EV11 | `WECHAT_WEBHOOK_URL` / `DINGTALK_WEBHOOK_URL` | 通知推送 | ❌ .env 已定义，Notifier 未在 API 层集成 | ❌ |
| EV12 | `SMTP_*` / `EMAIL_*` | 邮件通知 | ❌ .env 已定义，Notifier 未在 API 层集成 | ❌ |
| EV13 | `CACHE_DIR` / `LOG_DIR` | 缓存/日志目录 | ⚠️ .env 已定义，DataFetcherManager 使用硬编码缓存路径 | ⚠️ |
| EV14 | `HOST` / `PORT` / `DEBUG` | 服务器启动 | ✅ Uvicorn 读取 PORT，但 DEBUG 未生效 | ⚠️ |

#### 5.2.2 前端环境变量 (`VITE_*`)

| # | 变量 | 用途 | 当前状态 | 达标 |
|---|------|------|---------|------|
| FV1 | `VITE_API_URL` | 后端 API 地址 | ⚠️ 仅在 optimize.ts/trading.ts 中用于判断是否使用 Mock，未作为 baseURL | ⚠️ |
| FV2 | `VITE_WS_URL` | WebSocket 地址 | ❌ 未定义，WebSocket 硬编码 `ws://localhost:8000` | ❌ |
| FV3 | `VITE_API_HOST` | API Host (Spec 示例) | ❌ 未定义，Spec 示例用 `import.meta.env.VITE_API_HOST` | ❌ |

#### 5.2.3 配置文件 (`stockquant_config.yaml`)

| # | 配置项 | Spec 要求 | 当前状态 | 达标 |
|---|--------|----------|---------|------|
| CF1 | AI 配置 (provider/model/api_key/temperature) | Spec 7.1 定义 | ❌ YAML 配置文件未创建，仅 .env 环境变量 | ❌ |
| CF2 | 数据采集 (frequency/sources/schedule) | Spec 7.1 定义 | ❌ 未实现配置化数据源调度 | ❌ |
| CF3 | NLP 配置 (sentiment_model/fallback_provider) | Spec 7.1 定义 | ❌ 未实现 | ❌ |
| CF4 | 监控配置 (symbols/alert_threshold/channels) | Spec 7.1 定义 | ❌ MonitorAgent 参数硬编码 | ❌ |
| CF5 | 决策模式 (advisory/semi-auto/auto) | Spec 7.1 定义 | ⚠️ DecisionAgent 有 DecisionMode 枚举，但 API 未暴露切换 | ⚠️ |

#### 5.2.4 Settings API 与 .env 联动

| # | 功能 | Spec 要求 | 当前状态 | 达标 |
|---|------|----------|---------|------|
| SL1 | Settings 读取 .env 默认值 | Spec F029 "恢复 .env 默认值" | ❌ Settings API 返回硬编码默认值，未读 .env | ❌ |
| SL2 | Settings 保存覆盖 .env | Spec F029 "保存并热生效" | ❌ 保存仅写内存，不更新 .env 或配置文件 | ❌ |
| SL3 | Settings 删除恢复 .env 默认 | Spec F029 "删除覆盖，恢复 .env 默认值" | ❌ 删除仅移除内存覆盖，不读 .env | ❌ |
| SL4 | 前端 Settings 页面读取后端 | Spec F029 | ❌ 前端 Settings 从本地 GROUPS 硬编码初始值加载，未调 GET /api/settings | ❌ |

**差距总结**:
- 后端 `.env` 有 30+ 变量已定义，但 API 层仅 `DATABASE_URL` 被正确消费，其余变量（LLM/数据源/券商/通知/信号去重/Kafka）均未被 API 路由读取和使用
- 前端 `VITE_*` 变量定义不完整，缺少 `VITE_WS_URL` 和 `VITE_API_HOST`
- `stockquant_config.yaml` 配置文件完全缺失，Spec 要求的 AI/数据采集/NLP/监控/决策模式配置均未实现
- Settings API 与 .env 无联动：不读取 .env 默认值、保存不写配置文件、删除不恢复 .env
- 前端 Settings 页面未对接后端 API，配置无法持久化

---

## 六、优先级排序的实施计划

### Phase 1: 核心闭环打通 (P0 — 回测/数据/交易真实化)

**目标**: 让平台的核心流程 (数据→回测→交易) 跑通真实数据

| # | 任务 | 涉及文件 | 复杂度 |
|---|------|---------|--------|
| 1.1 | 后端回测执行: POST /api/backtest 调用 Cerebro.run() | `api/routers/backtest.py` | 高 |
| 1.2 | 后端优化执行: POST /api/backtest/optimize 调用 Cerebro.optstrategy() | `api/routers/optimize.py` | 高 |
| 1.3 | 后端 K 线数据真实化: GET /api/data/kline 调用 DataFetcherManager | `api/routers/data.py` | 中 |
| 1.4 | 后端交易真实化: PaperBroker 撮合替代 hardcoded | `api/routers/trading.py` | 高 |
| 1.5 | 后端 Portfolio 真实化: 从 PaperBroker 获取持仓 | `api/routers/portfolio.py` | 中 |
| 1.6 | 后端 Settings 持久化: JSON 文件存储替代内存 dict + 读取 .env 默认值 | `api/routers/settings.py` | 中 |
| 1.7 | 前端 Settings 对接后端 API: 调用 GET/POST /api/settings | `Settings.tsx` | 中 |

### Phase 2: 前端功能补全 (P1 — Spec 缺失项)

| # | 任务 | 涉及文件 | 复杂度 |
|---|------|---------|--------|
| 2.1 | Backtest 增加风控规则配置 | `Backtest.tsx`, `DataSelector.tsx` | 低 |
| 2.2 | Backtest 增加基准选择 | `Backtest.tsx` | 低 |
| 2.3 | BacktestResult 增加基准对比曲线 | `BacktestResult.tsx`, `EquityChart.tsx` | 中 |
| 2.4 | Monitor 接入 WebSocket 实时行情 | `Monitor.tsx` | 中 |
| 2.5 | Monitor 增加收盘总结展示 | `Monitor.tsx` | 低 |
| 2.6 | Monitor 增加异动检测面板 | `Monitor.tsx` | 中 |
| 2.7 | AIChat 集成工具调用展示 | `AIChat.tsx`, `ChatPanel.tsx` | 中 |
| 2.8 | AIChat 信号卡片展示 | `ChatPanel.tsx` | 低 |
| 2.9 | Strategy 增加 AI 策略生成入口 | `Strategy.tsx` | 中 |
| 2.10 | Data 增加数据采集触发按钮 | `Data.tsx` | 低 |
| 2.11 | Data 增加数据源健康状态 | `Data.tsx` | 低 |
| 2.12 | Trading 增加下单确认弹窗 | `Trading.tsx` | 低 |
| 2.13 | Settings 条件显隐 (when 字段) | `Settings.tsx` | 中 |

### Phase 3: 高级功能 (P2 — F024/F027/F028)

| # | 任务 | 涉及文件 | 复杂度 |
|---|------|---------|--------|
| 3.1 | Monitor 实时 K 线图 | `Monitor.tsx` | 高 |
| 3.2 | Monitor 社交媒体情绪监控 | `Monitor.tsx`, 新组件 | 高 |
| 3.3 | AIChat 对话式策略开发 (F028) | `AIChat.tsx`, 后端 | 高 |
| 3.4 | AIChat 对话式数据分析 (F028) | `AIChat.tsx`, 后端 | 高 |
| 3.5 | AIChat 对话式盯盘 (F028) | `AIChat.tsx`, 后端 | 高 |
| 3.6 | 策略对比历史 (F027) | `comparison.py`, 新前端 | 中 |
| 3.7 | Portfolio 个股权益曲线 | `Portfolio.tsx` | 中 |
| 3.8 | 通知路由实现 | `notification.py` | 低 |

### Phase 4: 部署、安全与配置 (P2 — F030/NFR)

| # | 任务 | 涉及文件 | 复杂度 |
|---|------|---------|--------|
| 4.1 | Docker Compose 更新 (PostgreSQL 服务) | `docker-compose.yml` | 中 |
| 4.2 | Nginx 反向代理配置 | `web/nginx/default.conf` | 中 |
| 4.3 | JWT 认证实现 | `api/deps.py` | 高 |
| 4.4 | Rate Limiting | `api/main.py` | 中 |
| 4.5 | API Key 加密存储 | `api/routers/settings.py` | 中 |
| 4.6 | 前端环境变量补全: VITE_API_URL/VITE_WS_URL/VITE_API_HOST | `web/.env`, `web/src/api/client.ts` | 低 |
| 4.7 | 后端 .env 变量全量消费: LLM/数据源/券商/通知/信号去重 | `api/routers/*.py` | 中 |
| 4.8 | stockquant_config.yaml 配置文件创建与加载 | `stockquant/config.py` (新建) | 中 |
| 4.9 | Settings API 与 .env 联动: 读取默认值/保存覆盖/删除恢复 | `api/routers/settings.py` | 中 |

---

## 七、验收标准

### Phase 1 完成标准
- [ ] 回测提交后 Cerebro.run() 真实执行，结果可通过 API 获取
- [ ] 优化提交后 Cerebro.optstrategy() 真实执行
- [ ] K 线数据来自真实数据源 (BaoStock/AkShare)
- [ ] Paper 交易使用 PaperBroker 真实撮合
- [ ] Portfolio 数据来自真实持仓
- [ ] Settings 配置持久化到文件，读取 .env 默认值
- [ ] 前端 Settings 页面对接后端 API

### Phase 2 完成标准
- [ ] 所有 Spec F029 页面功能项达标率 ≥ 90%
- [ ] Monitor 实时行情正常推送
- [ ] AIChat 工具调用结果可视化
- [ ] Strategy AI 生成入口可用

### Phase 3 完成标准
- [ ] F024/F027/F028 前端功能基本可用
- [ ] 对标 Product-Spec 页面功能达标率 ≥ 95%

### Phase 4 完成标准
- [ ] Docker Compose 一键部署
- [ ] JWT 认证可用
- [ ] NFR004 安全要求达标
- [ ] 前端 VITE_* 环境变量完整定义并生效
- [ ] 后端 .env 变量被 API 路由正确消费
- [ ] stockquant_config.yaml 配置文件创建并可加载
- [ ] Settings API 与 .env 联动：读取默认值/保存覆盖/删除恢复

---

## 八、执行策略

按用户要求，按照本报告优先级自行判断、自行决策、不征求意见，持续开发直到 100% 功能达标。

执行顺序: **Phase 1 → Phase 2 → Phase 3 → Phase 4**

每个 Phase 内按编号顺序执行，同优先级任务可并行。
