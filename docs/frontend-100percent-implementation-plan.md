# StockQuant 前端 100% 功能达标实施计划

> 基于 `frontend-product-spec-gap-assessment.md` 评估报告，对标 `Product-Spec.md` F029
> 目标：从当前 52% 达标率提升至 100%
> 策略：Phase 1→2→3→4 顺序执行，每 Phase 内按编号顺序，同优先级可并行

---

## 当前状态总结

- **后端核心问题**：backtest/optimize 空壳（不调用 Cerebro）、K线随机数、交易硬编码、Portfolio 硬编码、Settings 不持久化、.env 变量未被 API 消费
- **前端核心问题**：缺少风控/基准配置、Monitor 无真实行情、AIChat 无工具调用展示、Strategy 无 AI 生成入口、Data 无采集触发、Trading 无确认弹窗（已实现）、Settings 无后端集成、VITE_* 环境变量不完整
- **引擎层已就绪**：Cerebro.run()、Cerebro.optstrategy()、BaoStockFeed、BacktestBroker、PaperBroker、RiskManager、CommissionInfo、BacktestMetrics 均已完整实现

---

## Phase 1: 核心闭环打通 (P0)

### 1.1 后端回测执行引擎

**文件**: `stockquant/api/routers/backtest.py`

**现状**: `submit_backtest` 仅创建内存任务，状态永远 `queued`，不调用 Cerebro

**改造方案**:
1. 导入 `Cerebro`, `BaoStockFeed`, `BacktestBroker`, `CommissionInfo`, `RiskManager`, `FixedSlippage`, `PercentSlippage`, `AdaptiveSlippage`
2. 导入策略模板映射 `STRATEGY_MAP`（从 `templates.py` 获取 7 个策略类）
3. `submit_backtest` 改为异步执行：
   - 创建任务记录（status=running）
   - 启动 `asyncio.create_task(_run_backtest(task_id, payload))`
   - 立即返回 `{task_id, status: "running"}`
4. 新增 `_run_backtest(task_id, payload)` 异步函数：
   - 根据 payload 构造 `BaoStockFeed(symbols, timeframe, start, end)`
   - 根据 `strategy_name` 从 STRATEGY_MAP 获取策略类，传入 `strategy_params`
   - 构造 `CommissionInfo(commission_rate, min_commission, stamp_tax_rate, transfer_fee_rate)`
   - 构造 `RiskManager(max_position_pct, max_daily_loss_pct, max_drawdown_pct, ...)`
   - 构造 `Cerebro(cash, broker=BacktestBroker(slippage=...), commission=..., risk_manager=...)`
   - 调用 `cerebro.add_data(feed).add_strategy(cls, **params).run()`
   - 提取结果：metrics、trades（序列化为 dict）、equity_curve
   - 更新任务状态为 `completed`，存储结果
   - 通过 WebSocket 推送进度和完成通知
5. `get_backtest` 端点从内存/数据库读取结果返回
6. 基准数据：如果请求包含 `benchmark` 字段（如 "hs300"），额外拉取沪深300数据，计算 `benchmark_returns` 传入 `BacktestMetrics.calculate()`

**请求体扩展**:
```python
{
  "strategy_name": "DualMACrossover",
  "strategy_params": {"fast_period": 5, "slow_period": 20},
  "symbols": ["sh600519", "sz000858"],
  "data_source": "baostock",
  "timeframe": "1d",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "cash": 1000000,
  "commission_rate": 0.00025,
  "slippage_type": "percent",
  "slippage_value": 0.001,
  "risk_rules": {
    "max_position_pct": 0.3,
    "max_daily_loss_pct": 0.02,
    "max_drawdown_pct": 0.15
  },
  "benchmark": "hs300"  # 新增：基准选择
}
```

### 1.2 后端优化执行引擎

**文件**: `stockquant/api/routers/optimize.py`

**现状**: 空壳，不调用 Cerebro.optstrategy()，ws_manager 未 import

**改造方案**:
1. 修复 `ws_manager` import
2. `submit_optimize` 改为异步执行：
   - 创建任务记录
   - 启动 `asyncio.create_task(_run_optimize(task_id, payload))`
3. 新增 `_run_optimize(task_id, payload)` 异步函数：
   - 构造 Cerebro 实例（同 1.1）
   - 调用 `cerebro.optstrategy(strategy_cls, param_grid, optimizer=method, target=target_metric, n_jobs=n_jobs)`
   - Walk-Forward 模式额外传 `train_window`, `test_window`, `step`
   - 遍历结果，通过 WebSocket 推送进度
   - 存储结果（排名表 + 最佳参数）

**请求体扩展**:
```python
{
  "strategy_name": "DualMACrossover",
  "strategy_params": {"fast_period": 5, "slow_period": 20},
  "symbols": ["sh600519"],
  "data_source": "baostock",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "cash": 1000000,
  "param_grid": {"fast_period": [3,5,7], "slow_period": [15,20,25]},
  "method": "grid",
  "target_metric": "Sharpe Ratio",
  "max_iters": 100,
  "n_jobs": 4,
  "train_window": 252,
  "test_window": 63
}
```

### 1.3 后端 K 线数据真实化

**文件**: `stockquant/api/routers/data.py`

**现状**: `get_kline` 用 `random.uniform` 生成假数据

**改造方案**:
1. 导入 `DataFetcherManager`, `BaoStockFeed`
2. 创建全局 `DataFetcherManager` 单例，注册 BaoStockFeed
3. `get_kline` 改为调用 `manager.fetch(symbol, timeframe, start, end)`
4. 将 DataFrame 转换为前端期望的格式（date, open, high, low, close, volume）
5. `get_cache_stats` 返回真实缓存状态（文件大小、symbol 数量等）
6. 新增 `POST /api/data/collect` 端点：手动触发数据采集/下载
7. 新增 `GET /api/data/health` 端点：返回数据源健康状态

### 1.4 后端交易真实化 (PaperBroker)

**文件**: `stockquant/api/routers/trading.py`

**现状**: 持仓/账户硬编码，成交价 100.0 兜底，不更新状态

**改造方案**:
1. 创建全局 `PaperBroker` 实例 + `Portfolio` 实例
2. `place_order` 改为：
   - 构造 `Order` 对象
   - 获取当前行情（从 DataFetcherManager 获取最新 Bar）
   - 调用 `broker.place_order(order, bar)` 撮合
   - 更新 Portfolio 持仓和账户
3. `get_positions` 从 Portfolio 读取真实持仓
4. `get_account` 从 Portfolio 读取真实账户余额
5. `cancel_order` 调用 `broker.cancel_order()`
6. `get_trades` 从 broker.trade_log 读取成交记录

### 1.5 后端 Portfolio 真实化

**文件**: `stockquant/api/routers/portfolio.py`

**现状**: 全部硬编码

**改造方案**:
1. 与 trading.py 共享同一个 Portfolio 实例
2. `get_positions` 从 Portfolio 读取
3. `get_account` 从 Portfolio 读取
4. `get_sector` 动态计算行业分布（基于持仓标的）
5. `get_pnl` 基于真实成交记录计算盈亏

### 1.6 后端 Settings 持久化 + .env 联动

**文件**: `stockquant/api/routers/settings.py`

**现状**: 内存 dict，重启丢失，不读取 .env 默认值

**改造方案**:
1. 持久化到 JSON 文件 `stockquant_settings.json`
2. 启动时从文件加载，保存时写入文件
3. **读取 .env 默认值**：Settings API 的 `_DEFAULT_SETTINGS` 从 `os.environ.get()` 读取，而非硬编码
4. 加入配置值校验（类型、范围）
5. 新增 `GET /api/settings/health` 端点返回配置状态
6. `DELETE /api/settings/{key}` 恢复时从 .env 重新读取默认值

### 1.7 前端 Settings 对接后端 API

**文件**: `web/src/pages/Settings.tsx`

**现状**: 前端 Settings 从本地 GROUPS 硬编码初始值加载，未调 GET /api/settings

**改造方案**:
1. 页面加载时调用 `GET /api/settings` 获取配置值
2. 保存时调用 `POST /api/settings/save` 提交修改
3. 删除时调用 `DELETE /api/settings/{key}` 恢复默认
4. 保留 GROUPS 作为 UI 元数据定义（label/description/type/options），值从后端获取

---

## Phase 2: 前端功能补全 (P1)

### 2.1 Backtest 增加风控规则配置

**文件**: `web/src/components/Backtest/ParamForm.tsx`, `web/src/pages/Backtest.tsx`

**改造**:
1. ParamForm 增加风控规则区域：
   - 单票最大仓位 (Slider 0-100%)
   - 单日最大亏损 (Slider 0-10%)
   - 累计最大回撤熔断 (Slider 5-50%)
   - 订单频率限制 (InputNumber)
2. 表单提交时将风控参数打包到 `risk_rules` 字段

### 2.2 Backtest 增加基准选择

**文件**: `web/src/pages/Backtest.tsx`

**改造**:
1. 在 DataSelector 或独立区域增加基准选择 Select：
   - 无基准 / 沪深300 / 中证500 / 创业板指
2. 提交时将 `benchmark` 字段传入后端

### 2.3 BacktestResult 增加基准对比曲线

**文件**: `web/src/components/Chart/EquityChart.tsx`, `web/src/pages/BacktestResult.tsx`

**改造**:
1. EquityChart 扩展 props：
   - `benchmarkData?: number[]` — 基准权益曲线
   - `dates?: string[]` — 日期轴
   - `benchmarkLabel?: string` — 基准名称
2. 图表增加第二条折线（基准），不同颜色/样式
3. BacktestResult 页面从后端结果中提取 benchmark 数据传入

### 2.4 Monitor 接入 WebSocket 实时行情

**文件**: `web/src/pages/Monitor.tsx`

**改造**:
1. 连接 `/ws/monitor` WebSocket
2. 接收 `quote` 类型消息更新自选股实时价格
3. 替换 Mock 随机价格生成逻辑
4. 接收 `alert` 类型消息展示异动告警

### 2.5 Monitor 增加收盘总结展示

**文件**: `web/src/pages/Monitor.tsx`

**改造**:
1. 新增"收盘总结"Card 区域
2. 调用 `monitorApi.summary()` 获取总结内容
3. 在页面底部或 Tab 中展示

### 2.6 Monitor 增加异动检测面板

**文件**: `web/src/pages/Monitor.tsx`

**改造**:
1. 新增"异动检测"区域：
   - 放量突破列表
   - 涨停/跌停列表
   - 异动成交量列表
2. 数据来源：后端 MonitorAgent 的 scan 结果 + WS 推送

### 2.7 AIChat 集成工具调用展示

**文件**: `web/src/pages/AIChat.tsx`, `web/src/components/AI/ChatPanel.tsx`

**改造**:
1. ChatPanel 增加工具调用消息类型渲染：
   - `tool_call` 类型消息：展示工具名 + 参数
   - `tool_result` 类型消息：展示结果（表格/列表/图表）
2. 后端 AI chat 返回中包含工具调用信息
3. 前端解析并渲染

### 2.8 AIChat 信号卡片展示

**文件**: `web/src/components/AI/ChatPanel.tsx`, `web/src/components/AI/SignalCard.tsx`

**改造**:
1. ChatPanel 检测 AI 回复中的交易建议，自动附加 SignalCard
2. SignalCard 增加 type 视觉区分（买入绿色/卖出红色）
3. SignalCard 增加点击交互（查看详情）

### 2.9 Strategy 增加 AI 策略生成入口

**文件**: `web/src/pages/Strategy.tsx`

**改造**:
1. 新增"AI 生成策略"按钮
2. 点击弹出 Modal：自然语言输入框
3. 调用后端 `/api/ai/strategy/generate`（新增端点）
4. 返回策略代码后自动填入 Monaco Editor
5. 后端端点调用 `StrategyAgent.generate()`

### 2.10 Data 增加数据采集触发按钮

**文件**: `web/src/pages/Data.tsx`

**改造**:
1. 数据源表格每行增加"采集"按钮
2. 点击调用 `POST /api/data/collect`
3. 展示采集进度和结果

### 2.11 Data 增加数据源健康状态

**文件**: `web/src/pages/Data.tsx`

**改造**:
1. 调用 `GET /api/data/health` 获取数据源健康状态
2. 数据源表格增加"状态"列（健康/不健康/检查中）
3. 状态用 Tag 组件展示（绿色/红色/黄色）

### 2.12 Trading 增加下单确认弹窗

**文件**: `web/src/pages/Trading.tsx`

**现状**: 已有确认弹窗（Modal 展示股票/方向/类型/价格/数量/预估金额）

**改造**:
1. 确认弹窗增加手续费预估（佣金 + 印花税 + 过户费）
2. 增加 A 股规则提示（T+1、100 股整数倍）
3. 增加风控检查前置提示

### 2.13 Settings 条件显隐 (when 字段)

**文件**: `web/src/pages/Settings.tsx`

**现状**: `isVisible()` 函数已实现基础逻辑，部分分组缺少 when 条件

**改造**:
1. 补全所有分组的 when 条件定义：
   - 券商通道：QMT 参数 when `trading.broker === 'qmt'`
   - 数据源：API Key/URL when `source !== 'csv'`
   - AI 模型：strategy_llm_* when `ai_model.provider !== 'default'`
2. 后端 API 集成：调用 `GET /api/settings` 和 `POST /api/settings/save`

---

## Phase 3: 高级功能 (P2)

### 3.1 Monitor 实时 K 线图

**文件**: `web/src/pages/Monitor.tsx`, 新组件 `web/src/components/Chart/RealtimeKline.tsx`

**改造**:
1. 新建 `RealtimeKline` 组件：ECharts candlestick + 实时更新
2. 从 WebSocket 接收实时行情数据更新 K 线
3. 支持技术指标叠加（MA/EMA/BOLL）
4. Monitor 页面增加 K 线图区域

### 3.2 Monitor 社交媒体情绪监控

**文件**: `web/src/pages/Monitor.tsx`, 新组件 `web/src/components/Monitor/SentimentPanel.tsx`

**改造**:
1. 新建 `SentimentPanel` 组件：情绪仪表盘 + 趋势图
2. 调用后端情绪分析 API
3. 展示社交媒体情绪突变告警

### 3.3 AIChat 对话式策略开发 (F028)

**文件**: `web/src/pages/AIChat.tsx`, 后端新增端点

**改造**:
1. AI 对话增加"策略开发"模式
2. 用户输入策略意图 → AI 生成策略代码
3. 代码块可一键复制到 Strategy 页面
4. 后端复用 StrategyAgent

### 3.4 AIChat 对话式数据分析 (F028)

**文件**: `web/src/pages/AIChat.tsx`

**改造**:
1. AI 对话增加"数据分析"模式
2. 用户提问 → AI 查询数据 → 生成图表 + 分析
3. 工具调用展示数据表格和 ECharts 图表

### 3.5 AIChat 对话式盯盘 (F028)

**文件**: `web/src/pages/AIChat.tsx`

**改造**:
1. AI 对话增加"盯盘"模式
2. 用户指定监控标的 → AI 启动监控 → 推送信号
3. 信号通过 SignalCard 展示

### 3.6 策略对比历史 (F027)

**文件**: `stockquant/api/routers/comparison.py`, 新前端页面或组件

**改造**:
1. 后端 `GET /api/comparison/history` 返回真实对比数据
2. 前端新增对比图表组件
3. 支持多策略指标横向对比

### 3.7 Portfolio 个股权益曲线

**文件**: `web/src/pages/Portfolio.tsx`

**改造**:
1. 持仓表格每行增加"权益曲线"按钮
2. 点击弹出 Modal 展示个股级别权益曲线
3. 数据从后端获取

### 3.8 通知路由实现

**文件**: `stockquant/api/routers/notification.py`

**改造**:
1. 实现 `GET /api/notifications` 端点
2. 实现 `PUT /api/notifications/{id}/read` 端点
3. 实现 `DELETE /api/notifications/{id}` 端点
4. 前端 notificationStore 对接

---

## Phase 4: 部署、安全与配置 (P2)

### 4.1 Docker Compose 更新

**文件**: `docker-compose.yml`

**改造**:
1. 添加 PostgreSQL 服务
2. 添加 ChromaDB 服务（AI 记忆）
3. 更新 backend 环境变量
4. 添加 healthcheck

### 4.2 Nginx 反向代理配置

**文件**: `web/nginx/default.conf`（新建）

**改造**:
1. 前端 `/` → Nginx SPA
2. 后端 `/api/*` → FastAPI
3. WebSocket `/ws/*` → FastAPI
4. Gzip 压缩

### 4.3 JWT 认证实现

**文件**: `stockquant/api/deps.py`

**改造**:
1. 实现 JWT Token 生成和验证
2. 登录端点 `POST /api/auth/login`
3. 所有受保护端点添加认证依赖

### 4.4 Rate Limiting

**文件**: `stockquant/api/main.py`

**改造**:
1. 集成 `slowapi` 限流
2. 默认 100 req/min

### 4.5 API Key 加密存储

**文件**: `stockquant/api/routers/settings.py`

**改造**:
1. 使用 `cryptography` 库加密 API Key
2. 读取时解密，存储时加密
3. 掩码展示

### 4.6 前端环境变量补全

**文件**: `web/.env`, `web/.env.production`, `web/src/api/client.ts`, WebSocket 连接处

**改造**:
1. 创建 `web/.env` 定义：
   - `VITE_API_URL=http://localhost:8000/api`
   - `VITE_WS_URL=ws://localhost:8000`
   - `VITE_API_HOST=localhost:8000`
2. `client.ts` 的 baseURL 改为 `import.meta.env.VITE_API_URL`
3. 所有 WebSocket 连接改用 `import.meta.env.VITE_WS_URL`
4. 创建 `web/.env.production` 用于生产环境

### 4.7 后端 .env 变量全量消费

**文件**: `stockquant/api/routers/*.py`, `stockquant/api/main.py`

**改造**:
1. AI 对话路由读取 `OPENAI_API_KEY`/`OPENAI_API_BASE`/`OPENAI_MODEL`/`OPENAI_MAX_TOKENS`/`OPENAI_TEMPERATURE`
2. 数据路由读取 `TUSHARE_TOKEN`/`AKSHARE_PROXY`/`CACHE_DIR`
3. 交易路由读取 `QMT_PATH`/`QMT_ACCOUNT`/`QMT_PASSWORD`
4. 通知路由读取 `WECHAT_WEBHOOK_URL`/`DINGTALK_WEBHOOK_URL`/`SMTP_*`/`EMAIL_*`
5. 信号路由读取 `SIGNAL_DEDUP_*`
6. 启动变量 `HOST`/`PORT`/`DEBUG` 在 main.py 中生效

### 4.8 stockquant_config.yaml 配置文件

**文件**: `stockquant/config.py`（新建）, `stockquant_config.yaml`（新建）

**改造**:
1. 创建 `stockquant/config.py` 配置加载模块：
   - `load_config(path)` 读取 YAML 配置
   - `get_config(key, default)` 获取配置值
   - 配置优先级：Settings API 覆盖 > YAML 文件 > .env 环境变量 > 代码默认值
2. 创建 `stockquant_config.yaml` 模板：
   - AI 配置 (provider/model/api_key/temperature)
   - 数据采集 (frequency/sources/schedule)
   - NLP 配置 (sentiment_model/fallback_provider)
   - 监控配置 (symbols/alert_threshold/channels)
   - 决策模式 (advisory/semi-auto/auto)
3. API 启动时加载配置

### 4.9 Settings API 与 .env 完整联动

**文件**: `stockquant/api/routers/settings.py`

**改造**:
1. `GET /api/settings` 返回值优先级：Settings JSON 覆盖 > .env 环境变量 > 代码默认值
2. `POST /api/settings/save` 保存到 Settings JSON 文件，同时热生效（更新内存中的运行时配置）
3. `DELETE /api/settings/{key}` 删除 JSON 覆盖，回退到 .env 值
4. `GET /api/settings/whitelist` 返回所有可配置项及其来源（.env / yaml / override）

---

## 验证计划

### Phase 1 验证
- [ ] 提交回测任务后 Cerebro.run() 真实执行，返回 30+ 指标
- [ ] 提交优化任务后 Cerebro.optstrategy() 真实执行，返回排名表
- [ ] K 线数据来自 BaoStock 真实数据
- [ ] Paper 交易使用 PaperBroker 真实撮合
- [ ] Portfolio 数据来自真实持仓
- [ ] Settings 配置持久化到文件，读取 .env 默认值
- [ ] 前端 Settings 页面对接后端 API

### Phase 2 验证
- [ ] Backtest 页面可配置风控规则和基准
- [ ] BacktestResult 页面显示基准对比曲线
- [ ] Monitor 页面显示实时行情和异动检测
- [ ] AIChat 展示工具调用结果和 SignalCard
- [ ] Strategy 页面有 AI 策略生成入口
- [ ] Data 页面可触发数据采集
- [ ] Trading 确认弹窗显示手续费预估
- [ ] Settings 条件显隐完整且对接后端

### Phase 3 验证
- [ ] Monitor 实时 K 线图正常渲染
- [ ] AIChat 对话式策略/数据/盯盘功能可用
- [ ] Portfolio 个股权益曲线可查看
- [ ] 通知路由正常工作

### Phase 4 验证
- [ ] Docker Compose 一键部署
- [ ] JWT 认证可用
- [ ] Rate Limiting 生效
- [ ] API Key 加密存储
- [ ] 前端 VITE_* 环境变量完整定义并生效
- [ ] 后端 .env 变量被 API 路由正确消费
- [ ] stockquant_config.yaml 配置文件创建并可加载
- [ ] Settings API 与 .env 联动：读取默认值/保存覆盖/删除恢复

---

## 执行策略

按用户要求：自行判断优先级、自行决策、不征求意见、持续开发直到 100% 功能达标。

执行顺序：**Phase 1 → Phase 2 → Phase 3 → Phase 4**

每个 Phase 内按编号顺序执行。Phase 1 是核心闭环，必须先完成。Phase 2 是前端补全，依赖 Phase 1 的后端改造。Phase 3 是高级功能，Phase 4 是部署安全。
