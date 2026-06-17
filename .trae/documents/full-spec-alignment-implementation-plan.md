# StockQuant 对齐 Product-Spec 全量实施计划

> **目标**: 修复 31 项 Todo，从当前 55% 达标率推进至 100%
> **原则**: 自行判断优先级、自行决策、按依赖链顺序执行
> **策略**: 先修核心闭环 → 再补功能缺失 → 最后完善高级功能和 NFR

---

## 执行顺序与依赖关系

```
Phase 0 (前置) ─→ Phase 1 (核心闭环) ─→ Phase 2 (功能完善) ─→ Phase 3 (高级+NFR)
  0.1 登录页         1.1 交易撮合         2.1 AIChat模式        3.1 LiveBroker
  0.2 Orchestrator   1.2 权益曲线         2.2 Settings条件      3.2 F028对话
  0.3 信号管线API     1.3 Monitor WS       2.3 通知持久化        3.3 Docker部署
                     1.4 JWT+登录联动      2.4 对比持久化        3.4 NFR测试
                     1.5 PaperBroker       2.5 通知通道补全      3.5 F020闭环
                     1.6 决策模式UI        2.6 报表API           3.6 幻觉数据库
                                          2.7 调度器API         3.7 F027组合优化
                                          2.8 F020采集          3.8 F027生命周期
                                          2.9 F020记忆          3.9 NFR AI测试
                                          2.10 F020反幻觉       3.10 NFR可靠性
                                          2.11 F024消息面联动
                                          2.12 F024信号融合
```

---

## Phase 0: 前置依赖 (3 项)

### 0.1 登录页面实现

**涉及文件**:
- 新建 `web/src/pages/Login.tsx`
- 修改 `web/src/App.tsx` — 添加 `/login` 路由 + 路由守卫
- 新建 `web/src/stores/authStore.ts` — 认证状态管理
- 修改 `web/src/api/client.ts` — 请求拦截器自动附加 JWT token

**实现方案**:
1. 创建 `Login.tsx`: Ant Design Form (用户名+密码)，调用 `POST /api/auth/login`，成功后存 token 到 localStorage + authStore
2. 创建 `authStore.ts`: Zustand store，管理 token/user/isAuthenticated，提供 login/logout/checkAuth
3. 修改 `App.tsx`: 添加 `/login` 路由（无 Layout），其他路由添加认证守卫（未登录重定向到 /login）
4. 修改 `api/client.ts`: axios 拦截器自动从 localStorage 读取 token 附加到 Authorization header
5. 修改 `api/client.ts`: 401 响应自动跳转 /login

**验收**: 未登录访问任何页面→重定向 /login；登录后→跳转 Dashboard；token 过期→自动跳转 /login

### 0.2 Agent Orchestrator 骨架

**涉及文件**:
- 新建 `stockquant/ai/orchestrator.py`
- 修改 `stockquant/models/base.py` — 添加 MemoryUpdateEvent
- 修改 `stockquant/api/main.py` — 启动时初始化 Orchestrator

**实现方案**:
1. 创建 `AgentOrchestrator` 类: 统一管理所有 Agent 实例，提供 `route_request(task_type, payload)` 方法
2. Agent 注册表: 字典映射 task_type → Agent 实例
3. AIEvent 事件总线: 基于 EventEngine，添加 `MemoryUpdateEvent` 事件类型
4. Agent 间通信: 通过 EventEngine 发布/订阅 AIEvent
5. 集成到 FastAPI lifespan: `create_app()` 启动时创建 Orchestrator 单例

**验收**: Orchestrator 可路由请求到正确 Agent；Agent 间可通过事件总线通信

### 0.3 F019 信号管线 API 暴露

**涉及文件**:
- 新建 `stockquant/api/routers/signal.py`
- 修改 `stockquant/api/main.py` — 注册 signal 路由
- 新建 `web/src/api/signal.ts` — 前端 API 客户端
- 修改 `web/src/pages/Monitor.tsx` — 添加信号面板

**实现方案**:
1. 创建 signal 路由: `GET /api/signals` (活跃信号列表), `POST /api/signals` (手动添加信号), `DELETE /api/signals/{id}` (移除信号), `GET /api/signals/audit` (审计日志)
2. 路由内导入 `SignalManager` 实例，暴露其方法
3. 前端 signal API 客户端
4. Monitor 页面添加信号列表 Tab

**验收**: 前端可查看活跃信号、审计日志；信号去重和冲突解决可视化

---

## Phase 1: 核心闭环修复 (6 项)

### 1.1 交易撮合引擎集成

**涉及文件**:
- 修改 `stockquant/api/routers/trading.py`

**实现方案**:
1. 将 `place_order()` 中的自写撮合逻辑替换为 `PaperBroker.submit_order()` 调用
2. LIMIT 订单: 提交到 PaperBroker 待撮合队列，启动后台定时任务检查撮合（每 5 秒用最新行情检查限价单）
3. 移除硬编码 100.0 回退: 行情获取失败时返回错误而非使用假价格
4. 保留 A 股佣金模型（CommissionInfo）
5. 订单状态流转: SUBMITTED → FILLED/PARTIALLY_FILLED/CANCELLED

**验收**: MARKET 订单即时成交；LIMIT 订单挂单等待撮合；行情失败返回错误

### 1.2 Portfolio 权益曲线真实化

**涉及文件**:
- 修改 `stockquant/api/routers/portfolio.py`

**实现方案**:
1. 修改 `GET /portfolio/equity-curve`: 调用 `_compute_live_equity_curve()` 基于真实交易记录 + K 线数据计算
2. 修改 `GET /portfolio/equity-curve/{symbol}`: 基于该标的的买入/卖出记录 + K 线数据计算
3. 修复 `_compute_live_equity_curve()` 的连续性缺陷: 确保第一天和后续天权益值连续
4. 添加缓存: 计算结果缓存 60 秒，避免重复计算

**验收**: 权益曲线基于真实交易数据计算，数值连续无跳变

### 1.3 Monitor WS 主动推送

**涉及文件**:
- 修改 `stockquant/api/main.py` — /ws/monitor 端点
- 修改 `stockquant/api/routers/monitor.py` — 启动后台推送任务

**实现方案**:
1. 修改 `/ws/monitor` 端点: 连接后启动后台 asyncio.Task 定时推送行情
2. 推送逻辑: 每 5 秒从 BaoStockFeed 获取自选股最新价格，通过 WS 推送 `quote` 消息
3. 盘中检测: 9:30-15:00 期间推送，非交易时间停止
4. 异动检测: 价格变动超过阈值时推送 `alert` 消息
5. 断线处理: 客户端断开时取消推送任务

**验收**: 连接 /ws/monitor 后每 5 秒收到自选股行情推送；异动时收到 alert

### 1.4 JWT 认证 + 登录页面联动

**涉及文件**:
- 修改 `stockquant/api/deps.py`
- 修改 `stockquant/api/routers/trading.py` — 使用 `get_required_user`
- 修改 `stockquant/api/routers/settings.py` — 使用 `get_required_user`

**实现方案**:
1. 修改 `deps.py`: JWT secret 从环境变量读取，无默认值（强制配置）
2. 敏感路由（trading, settings）使用 `get_required_user` 替代 `get_current_user`
3. 非敏感路由（dashboard, data, backtest 只读）保持 `get_current_user` 允许匿名
4. 前端已实现登录页（Phase 0.1），此处确保后端强制验证生效

**验收**: 未登录访问 /api/trading/* 返回 401；登录后正常访问

### 1.5 PaperBroker 实时数据集成

**涉及文件**:
- 修改 `stockquant/engine/broker.py` — PaperBroker 类

**实现方案**:
1. 修改 `PaperBroker.get_positions()`: 从交易状态获取真实持仓
2. 修改 `PaperBroker.get_balance()`: 从交易状态获取真实余额
3. 修改 `PaperBroker.get_history()`: 从交易状态获取真实成交记录
4. 添加 `PaperBroker.on_bar()`: 接收实时 Bar 数据，检查 LIMIT 订单是否可成交
5. PaperBroker 与 trading.py 的 Portfolio 实例绑定

**验收**: PaperBroker 返回真实持仓/余额/成交记录；LIMIT 订单可被 on_bar 触发成交

### 1.6 F025 决策模式前端 UI

**涉及文件**:
- 修改 `web/src/pages/Settings.tsx` — 添加 decision.mode 配置项
- 修改 `web/src/pages/Monitor.tsx` — 添加决策模式切换按钮

**实现方案**:
1. Settings.tsx: 在 AI 模型分组中添加 `decision.mode` 下拉选择（全自动/半自动/只读）
2. Monitor.tsx: 在扫描控制区域添加决策模式 Segmented 切换
3. 切换时调用 `POST /api/settings/save` 保存决策模式
4. 后端 settings.py 已有 `decision.mode` 配置项，无需修改

**验收**: 前端可切换决策模式；切换后设置持久化

---

## Phase 2: 功能完善 (12 项)

### 2.1 AIChat 模式切换接入

**涉及文件**:
- 修改 `web/src/pages/AIChat.tsx`

**实现方案**:
1. AIChat.tsx 已有 `mode` state 和 `setMode`，只需将 `mode` 和 `onModeChange={setMode}` 传给 ChatPanel
2. `handleSend` 中将 `mode` 传给 `streamChat()` 的 `mode` 参数（已有）
3. ChatPanel 根据 mode 显示不同的欢迎语和工具提示

**验收**: 切换模式后 ChatPanel 感知当前模式；不同模式发送不同 system prompt

### 2.2 Settings 条件显隐

**涉及文件**:
- 修改 `web/src/pages/Settings.tsx`

**实现方案**:
1. GROUPS 中为需要条件显隐的项添加 `when` 字段: `{ field: "trading.broker", values: ["qmt"] }`
2. 渲染时检查 `when` 条件: 获取 when.field 的当前值，如果不在 when.values 中则隐藏
3. 当 when.field 的值变化时，重新计算显隐状态
4. 需要条件显隐的配置项: QMT 相关参数（when broker=qmt）、SMTP 参数（when notification.email_enabled=true）、各通知渠道参数（when 对应渠道启用）

**验收**: 选择 QMT 券商时显示 QMT 配置项；切换为其他券商时隐藏

### 2.3 通知数据持久化

**涉及文件**:
- 修改 `stockquant/api/routers/notification.py`

**实现方案**:
1. 将 `_notifications` 列表替换为 SQLite 持久化
2. 使用 `persistence/repository.py` 的模式，新建 `save_notification()` / `list_notifications()` / `mark_notification_read()` / `delete_notification()` 函数
3. 新建 `notifications` ORM 表: id, type, title, message, read, created_at
4. 启动时从数据库加载未读通知

**验收**: 通知数据重启后不丢失

### 2.4 对比历史持久化

**涉及文件**:
- 修改 `stockquant/api/routers/comparison.py`

**实现方案**:
1. 将 `_comparison_history` 列表替换为 SQLite 持久化
2. 新建 `comparison_results` ORM 表: id, strategy_ids(JSON), metrics(JSON), ai_suggestion(TEXT), created_at
3. 使用 `persistence/repository.py` 的模式

**验收**: 对比历史重启后不丢失

### 2.5 通知通道补全

**涉及文件**:
- 修改 `web/src/components/Settings/NotifierForm.tsx`
- 修改 `stockquant/api/routers/settings.py` — 添加 ServerChan/Webhook 配置项

**实现方案**:
1. NotifierForm.tsx: 添加飞书 Webhook、Discord Webhook、PushPlus Token、ServerChan SendKey、自定义 Webhook URL 配置项
2. settings.py: 在 `_ENV_VAR_MAP` 和 `_SCHEMA` 中添加 `notification.feishu_webhook`、`notification.discord_webhook`、`notification.pushplus_token`、`notification.serverchan_key`、`notification.custom_webhook_url`
3. 每个通道添加"测试发送"按钮，调用 `POST /api/settings/test-notification?type=feishu`

**验收**: 9 个通知通道均可配置和测试

### 2.6 F013 报表 API 暴露

**涉及文件**:
- 修改 `stockquant/api/routers/backtest.py` — 添加报表端点
- 修改 `web/src/pages/BacktestResult.tsx` — 添加下载按钮

**实现方案**:
1. 添加 `GET /api/backtest/{task_id}/report?format=html|json` 端点
2. 调用 `ReportGenerator.generate_html()` 或 `generate_json()`，返回文件流
3. BacktestResult.tsx: 添加"导出报表"按钮，下载 HTML/JSON 文件
4. 添加 `POST /api/backtest/{task_id}/report/email` 端点（可选，邮件发送）

**验收**: 回测结果页可下载 HTML/JSON 报表

### 2.7 调度器 API 暴露

**涉及文件**:
- 新建 `stockquant/api/routers/scheduler.py`
- 修改 `stockquant/api/main.py` — 注册路由 + lifespan 启动调度器
- 新建 `web/src/api/scheduler.ts`
- 修改 `web/src/pages/Settings.tsx` — 添加调度管理 Tab

**实现方案**:
1. 创建 scheduler 路由: `GET /api/scheduler/tasks` (任务列表), `POST /api/scheduler/tasks` (添加任务), `DELETE /api/scheduler/tasks/{id}` (删除任务), `POST /api/scheduler/start` (启动), `POST /api/scheduler/stop` (停止)
2. FastAPI lifespan 中启动 StockScheduler
3. 前端 Settings 页面添加"定时任务"分组，显示任务列表和添加表单
4. 预置任务: 每日收盘总结、每日数据采集

**验收**: 前端可管理定时任务；调度器按计划执行

### 2.8 F020 采集环节

**涉及文件**:
- 新建 `stockquant/ai/collectors/` 目录
- 新建 `stockquant/ai/collectors/base.py` — 采集器基类
- 新建 `stockquant/ai/collectors/news_collector.py` — 新闻采集
- 新建 `stockquant/ai/collectors/announcement_collector.py` — 公告采集
- 新建 `stockquant/ai/collectors/social_collector.py` — 社交媒体采集
- 新建 `stockquant/ai/collectors/orchestrator.py` — 采集编排器
- 新建 `stockquant/ai/collectors/verifier.py` — 来源验证+事实初筛
- 新建 `stockquant/ai/collectors/config.yaml` — 数据源配置
- 修改 `stockquant/ai/orchestrator.py` — 集成采集编排器

**实现方案**:
1. `BaseCollector` 抽象类: `collect()` → 返回 `List[RawInfoItem]`，含 url/source/content/timestamp/sentiment_score
2. `NewsCollector`: 使用 AkShare 获取东方财富/新浪财经新闻
3. `AnnouncementCollector`: 使用 AkShare 获取巨潮资讯公告
4. `SocialCollector`: 使用 AkShare 获取雪球/股吧帖子
5. `CollectionOrchestrator`: asyncio 并行调用多个 Collector，汇总结果
6. `SourceVerifier`: 与 L2 记忆对比 URL（仿冒检测），与 L2/L3 缓存对比（事实初筛）
7. 采集结果自动写入 L2 记忆
8. 语义去重: 使用 TF-IDF 相似度 >95% 去重
9. `config.yaml`: 定义数据源列表、采集频率、启停状态

**验收**: 可并行采集 ≥3 个数据源；来源验证标记仿冒源；去重率 ≥90%

### 2.9 F020 记忆系统 L2/L3

**涉及文件**:
- 修改 `stockquant/ai/memory/` 目录下文件
- 新建 `stockquant/ai/memory/l2_store.py` — L2 短期记忆
- 新建 `stockquant/ai/memory/l3_store.py` — L3 长期记忆
- 新建 `stockquant/ai/memory/manager.py` — 记忆管理器
- 新建 `stockquant/ai/memory/forgetting.py` — 遗忘机制
- 新建 `stockquant/ai/memory/compressor.py` — 记忆压缩

**实现方案**:
1. `L2Store`: 基于 SQLite，存储原始信息条目（url/source/content/timestamp/sentiment/verified/expires_at），支持语义检索（TF-IDF 向量化 + 余弦相似度）
2. `L3Store`: 基于 ChromaDB，存储验证后的市场规律/策略逻辑/信源可信度，支持向量搜索
3. `MemoryManager`: 统一管理 L1/L2/L3，提供 `write(level, item)` / `search(query, levels, top_k)` / `compress()` 方法
4. `ForgettingMechanism`: 时效性遗忘（过期删除）、置信度遗忘（低置信度降权）、冗余压缩（相似条目合并）
5. `Compressor`: L2→L3 压缩（200条→1条摘要，保留核心事实 ≥95%）
6. 写入规则表: 8 种环节→层级→触发条件映射

**验收**: L2 可写入/检索/过期清理；L3 可向量搜索；压缩保留率 ≥95%

### 2.10 F020 反幻觉检查点

**涉及文件**:
- 修改 `stockquant/ai/hallucination/` 目录
- 新建 `stockquant/ai/hallucination/checkpoints.py` — 8 个检查点
- 新建 `stockquant/ai/hallucination/corrector.py` — 五步纠正
- 新建 `stockquant/ai/hallucination/modes.py` — 4 种触发模式

**实现方案**:
1. 8 个检查点函数: `source_verify()`, `fact_screen()`, `consistency_filter()`, `prompt_constraint()`, `summary_verify()`, `reasoning_verify()`, `cross_validation()`, `confidence_score()`
2. 五步纠正: 事实验证→来源验证→逻辑一致性→交叉验证→置信度评分，每步失败→下一步，全部失败→低置信度标记
3. 4 种触发模式: strict(全部检查点), standard(关键检查点), relaxed(仅置信度), emergency(跳过验证)
4. 检查点接入采集/总结/升华各环节: 采集后→source_verify+fact_screen，总结后→summary_verify，升华后→reasoning_verify+cross_validation
5. 幻觉事件记录到 L2 记忆

**验收**: 采集数据经过来源验证；总结经过事后验证；升华经过推理链验证

### 2.11 F024 消息面联动

**涉及文件**:
- 修改 `stockquant/ai/monitor_agent.py` — 添加消息面联动分析
- 修改 `stockquant/api/routers/monitor.py` — 添加联动分析端点

**实现方案**:
1. `MonitorAgent` 添加 `analyze_news_correlation(symbol, news_items, positions)` 方法
2. 联动逻辑: 获取持仓标的 → 从 L2 记忆检索相关新闻 → LLM 分析新闻对持仓的影响 → 生成联动报告
3. API 端点: `GET /api/monitor/news-correlation` — 返回持仓标的与最新新闻的联动分析
4. WS 推送: 采集到新新闻时，自动触发联动分析，推送 `news_alert` 消息

**验收**: 持仓标的出现重大新闻时自动推送联动分析

### 2.12 F024 AI 信号融合

**涉及文件**:
- 新建 `stockquant/ai/signal_fusion.py`
- 修改 `stockquant/ai/orchestrator.py` — 集成信号融合

**实现方案**:
1. `SignalFusion` 类: 接收技术面信号（指标突破）、情绪面信号（社交媒体情绪）、基本面信号（公告/财报），输出融合信号
2. 融合逻辑: 加权投票（技术面 0.4 + 情绪面 0.3 + 基本面 0.3），权重可配置
3. 冲突处理: 三面信号方向不一致时，输出 HOLD + 低置信度
4. API 端点: `GET /api/monitor/fused-signals` — 返回融合信号列表
5. WS 推送: 融合信号变化时推送 `fused_signal` 消息

**验收**: 技术面+情绪面+基本面信号可融合输出；方向冲突时降级

---

## Phase 3: 高级功能与 NFR (10 项)

### 3.1 LiveBroker 券商 API

**涉及文件**:
- 修改 `stockquant/engine/broker.py` — LiveBroker 类
- 新建 `stockquant/execution/brokers/qmt_broker.py` — QMT 券商实现

**实现方案**:
1. `LiveBroker` 类: 继承 Broker 抽象基类，实现 place_order/cancel_order/get_positions/get_balance/get_history
2. QMT 实现: 通过 xtquant SDK 连接 QMT 客户端（需 QMT 客户端运行）
3. 订单审计日志: 每笔下单记录原因/时间/价格/数量/AI建议
4. 合规检查: 检查订单是否符合 A 股交易规则（T+1、涨跌停、100 股整数倍）
5. 实盘/模拟盘切换: trading.py 根据 broker_mode 选择 PaperBroker 或 LiveBroker

**验收**: 可通过 QMT 模拟账户下单；审计日志完整

### 3.2 F028 对话式交互完善

**涉及文件**:
- 修改 `stockquant/ai/chat_agent.py` — 不同模式不同 system prompt
- 修改 `stockquant/api/routers/ai_chat.py` — mode 参数传递
- 修改 `web/src/pages/AIChat.tsx` — 模式感知 UI

**实现方案**:
1. ChatAgent 添加 mode 参数，根据 mode 选择不同 system prompt:
   - general: 通用助手
   - strategy: 策略开发专家（可用工具: generate_strategy, validate_strategy, backtest_strategy）
   - analysis: 数据分析专家（可用工具: query_market_data, search_news, analyze_backtest）
   - monitor: 盯盘助手（可用工具: scan_stock, get_brief, get_summary, analyze_news）
2. 不同模式暴露不同的工具集给 ReAct Agent
3. 前端 ChatPanel 根据 mode 显示不同的工具调用结果

**验收**: 切换到策略模式后 AI 以策略专家身份对话；盯盘模式可调用扫描工具

### 3.3 Docker Compose 完整部署

**涉及文件**:
- 修改 `docker-compose.yml`
- 修改 `web/nginx/default.conf` — 反向代理配置
- 新建 `.env.production`
- 修改 `stockquant/api/main.py` — CORS 生产配置

**实现方案**:
1. docker-compose.yml: 添加 Redis 服务、Nginx 服务（反向代理 frontend + backend）
2. Nginx 配置: `/` → frontend SPA, `/api/*` → backend:8000, `/ws/*` → backend:8000 WebSocket
3. `.env.production`: 生产环境变量模板
4. CORS: 改为只允许 Nginx 域名
5. 健康检查: backend `/api/health`, frontend `/`, postgres pg_isready, chromadb heartbeat
6. backend 使用 gunicorn + uvicorn worker 多进程

**验收**: `docker compose up -d` 一键启动；前后端通信正常；Nginx 反向代理正确

### 3.4 NFR 性能基准测试

**涉及文件**:
- 新建 `tests/test_nfr_performance.py`

**实现方案**:
1. 回测性能: 测试 5000 bar/s 日线回测速度
2. 数据缓存: 测试 10 年日线数据读取 <100ms
3. 指标计算: 测试单次指标计算 <1ms
4. 风控检查: 测试 <1ms/订单
5. 前端首屏: Lighthouse 测试 ≥80 分
6. WS 推送延迟: 测试 <500ms

**验收**: 所有性能指标达到 Spec 要求

### 3.5 F020 降噪/总结/升华闭环

**涉及文件**:
- 新建 `stockquant/ai/pipeline/denoiser.py` — 信息降噪
- 新建 `stockquant/ai/pipeline/summarizer.py` — 信息总结
- 新建 `stockquant/ai/pipeline/elevator.py` — 信息升华
- 修改 `stockquant/ai/pipeline/orchestrator.py` — 串联 4 环节

**实现方案**:
1. `Denoiser`: 信源降权（基于 L3 历史准确度）+ 时效性降权（7天/30天/永久）+ 一致性过滤（已证伪信息阻断）+ 冗余压缩（相似内容合并）
2. `Summarizer`: 三源检索（L1/L2/L3）+ Prompt 约束注入 + LLM 总结 + 总结后验证 + 验证后存储 + 多级总结（会话/日/周/月）+ 记忆压缩
3. `Elevator`: L3 检索 + 多源融合 + 推理链验证 + 交叉验证 + 升华结果存储
4. `PipelineOrchestrator`: 串联 采集→降噪→总结→升华，每个环节插入反幻觉检查点

**验收**: 完整 4 环节闭环可运行；降噪冗余保留 ≤5%；总结准确率 ≥90%

### 3.6 幻觉数据库

**涉及文件**:
- 新建 `stockquant/ai/hallucination/database.py`
- 修改 `stockquant/persistence/models.py` — 添加 HallucinationRecord ORM

**实现方案**:
1. `HallucinationRecord` ORM: id, timestamp, agent, input_summary, hallucination_type, detection_method, original_output, corrected_output, confidence, user_feedback
2. `HallucinationDatabase` 类: record() / query() / analyze_patterns() / optimize_prompt()
3. `analyze_patterns()`: 统计幻觉类型分布、高频触发场景、Agent 差异
4. `optimize_prompt()`: 基于幻觉模式自动生成 Prompt 优化建议

**验收**: 幻觉事件可记录和查询；模式分析可输出优化建议

### 3.7 F027 策略组合优化

**涉及文件**:
- 修改 `stockquant/ai/comparison_agent.py` — 添加组合优化
- 修改 `stockquant/api/routers/comparison.py` — 添加优化端点
- 修改 `web/src/pages/Comparison.tsx` — 添加组合优化 Tab

**实现方案**:
1. `ComparisonAgent` 添加 `optimize_portfolio(strategy_results)` 方法
2. 计算策略间相关性矩阵（基于收益率序列）
3. 使用均值-方差模型推荐最优权重组合（最小化组合回撤）
4. API: `POST /api/comparison/optimize` — 返回最优权重 + 预期指标
5. 前端: 对比页添加"组合优化"Tab，展示权重饼图 + 预期指标

**验收**: 可分析策略相关性并推荐最优组合权重

### 3.8 F027 策略生命周期建议

**涉及文件**:
- 修改 `stockquant/ai/comparison_agent.py` — 添加生命周期建议
- 修改 `web/src/pages/Comparison.tsx` — 添加生命周期建议面板

**实现方案**:
1. `ComparisonAgent` 添加 `lifecycle_advice(strategy_id, recent_performance)` 方法
2. 基于近期表现（最近 30 天收益率、夏普、最大回撤）给出启用/停用/调整建议
3. 前端: 对比页添加"生命周期建议"面板

**验收**: 可基于近期表现给出策略启用/停用建议

### 3.9 NFR008/009 AI 可靠性测试

**涉及文件**:
- 新建 `tests/test_nfr_ai_reliability.py`

**实现方案**:
1. 情感分析准确率: 标注 100 条文本，测试 ≥75%
2. 信息抽取准确率: 标注 50 条新闻，测试 ≥85%
3. AI 信号一致性: 同一输入 10 次调用，一致性 ≥70%
4. 事实验证通过率: 100 条已知事实，验证 ≥99%
5. 幻觉检出率: 50 条含幻觉输出，检出 ≥80%
6. AI 决策延迟: 轻量 <200ms, 完整 <3s
7. LLM 调用成本: 模拟 1 天使用，计算成本 ≤2 元

**验收**: 所有 AI 可靠性指标达到 Spec 要求

### 3.10 NFR002 可靠性补全

**涉及文件**:
- 修改 `stockquant/api/routers/trading.py` — 订单幂等性
- 修改 `stockquant/engine/broker.py` — 崩溃恢复
- 新建 `tests/test_nfr_reliability.py`

**实现方案**:
1. 订单幂等性: 每个订单生成唯一 idempotency_key，重复提交返回相同结果
2. 崩溃恢复: 交易状态定期持久化到 SQLite，启动时从数据库恢复
3. 回测确定性: 同一参数多次运行，结果完全一致（固定随机种子）
4. 测试: 验证以上三项

**验收**: 重复下单幂等；崩溃后可恢复；回测结果确定

---

## 执行策略

1. **每完成一项**，运行 `pytest tests/` 确保不引入回归
2. **每完成一个 Phase**，运行完整验收标准检查
3. **F020 相关任务**（2.8/2.9/2.10/3.5/3.6）是最大复杂度区域，需要最多迭代
4. **3.1 LiveBroker** 依赖外部 QMT 客户端，可能需要 mock 测试
5. **3.3 Docker 部署** 需要实际 `docker compose up` 验证
