# StockQuant 100% 功能达标 — 执行计划

> 基于 `frontend-100percent-implementation-plan.md`，按 Phase 1→2→3→4 顺序执行
> 自行判断优先级、自行决策、不征求意见、持续开发直到 100% 功能达标

---

## 执行总览

| Phase | 任务数 | 核心目标 |
|-------|--------|---------|
| Phase 1 | 7 | 核心闭环打通：回测/优化/K线/交易/Portfolio/Settings 真实化 |
| Phase 2 | 13 | 前端功能补全：风控/基准/Monitor/AIChat/Strategy/Data/Trading/Settings |
| Phase 3 | 8 | 高级功能：实时K线/情绪/对话式AI/策略对比/个股曲线/通知 |
| Phase 4 | 9 | 部署安全配置：Docker/Nginx/JWT/RateLimit/环境变量/YAML |

---

## Phase 1: 核心闭环打通

### Task 1.1: 后端回测执行引擎

**文件**: `stockquant/api/routers/backtest.py`

**改造内容**:
1. 新增导入:
   ```python
   import asyncio
   from stockquant.engine.cerebro import Cerebro
   from stockquant.engine.broker import BacktestBroker
   from stockquant.engine.commission import CommissionInfo, FixedSlippage, PercentSlippage, AdaptiveSlippage
   from stockquant.engine.risk import RiskManager
   from stockquant.data.providers.baostock_feed import BaoStockFeed
   from stockquant.strategy.templates import (
       DualMACrossoverStrategy, RSIReversalStrategy, BollingerBounceStrategy,
       MACDDivergenceStrategy, DualThrustStrategy, MeanReversionStrategy, MomentumStrategy,
   )
   from stockquant.api.websocket import ws_manager
   ```

2. 新增策略映射:
   ```python
   STRATEGY_MAP = {
       "DualMACrossover": DualMACrossoverStrategy,
       "DualMACrossoverStrategy": DualMACrossoverStrategy,
       "RSIReversal": RSIReversalStrategy,
       "RSIReversalStrategy": RSIReversalStrategy,
       "BollingerBounce": BollingerBounceStrategy,
       "BollingerBounceStrategy": BollingerBounceStrategy,
       "MACDDivergence": MACDDivergenceStrategy,
       "MACDDivergenceStrategy": MACDDivergenceStrategy,
       "DualThrust": DualThrustStrategy,
       "DualThrustStrategy": DualThrustStrategy,
       "MeanReversion": MeanReversionStrategy,
       "MeanReversionStrategy": MeanReversionStrategy,
       "Momentum": MomentumStrategy,
       "MomentumStrategy": MomentumStrategy,
   }
   ```

3. 新增辅助函数 `_build_slippage(slippage_type, slippage_value)`:
   - `"none"` → None
   - `"fixed"` → FixedSlippage(slippage_value or 0.01)
   - `"percent"` → PercentSlippage(slippage_value or 0.001)
   - `"adaptive"` → AdaptiveSlippage()

4. 新增 `_run_backtest(task_id, payload)` 异步函数:
   - 在 `asyncio.get_event_loop().run_in_executor(None, _run_backtest_sync, ...)` 中执行同步 Cerebro.run()
   - `_run_backtest_sync` 函数:
     a. 构造 BaoStockFeed: `BaoStockFeed(symbols, timeframe, start, end)`
     b. 获取策略类: `STRATEGY_MAP[strategy_name]`
     c. 构造 CommissionInfo: 从 payload 读取 commission_rate/min_commission/stamp_tax_rate/transfer_fee_rate
     d. 构造 RiskManager: 从 payload.risk_rules 读取 max_position_pct/max_daily_loss_pct/max_drawdown_pct
     e. 构造 BacktestBroker(slippage=_build_slippage(...))
     f. 构造 Cerebro(cash, broker, commission, risk_manager)
     g. `cerebro.add_data(feed).add_strategy(cls, **strategy_params).run()`
     h. 序列化结果: metrics (dict), trades (每个 TradeData 转为 dict), equity_curve (转为 [float])
     i. 基准处理: 如果 payload.benchmark 存在，额外拉取基准数据，计算 benchmark_returns
     j. 更新 _tasks[task_id] 状态为 completed，存储结果
   - 完成后通过 ws_manager.push("complete", {...}, task_id) 推送
   - 失败时更新状态为 failed，存储 error 信息

5. 修改 `submit_backtest`:
   - task 初始 status 改为 "running"
   - 调用 `asyncio.create_task(_run_backtest(task_id, payload))`
   - 返回 `{task_id, status: "running", created_at}`

6. 修改 `get_backtest`:
   - 返回完整 task 信息，包括新增字段: benchmark_metrics, benchmark_equity_curve

### Task 1.2: 后端优化执行引擎

**文件**: `stockquant/api/routers/optimize.py`

**改造内容**:
1. 新增导入（同 1.1）+ 修复 ws_manager import:
   ```python
   from stockquant.api.websocket import ws_manager
   ```

2. 新增 `_run_optimize(task_id, payload)` 异步函数:
   - 在 executor 中执行同步 Cerebro.optstrategy()
   - 构造 Cerebro 实例（同 1.1 的数据源/策略/佣金/风控构造逻辑）
   - 调用 `cerebro.optstrategy(strategy_cls, param_grid, optimizer=method, target=target_metric, n_jobs=n_jobs, train_window=train_window, test_window=test_window, step=step)`
   - 遍历结果，每 10% 进度通过 ws_manager.push("progress", {...}, task_id) 推送
   - 完成后推送 "complete"
   - 存储结果到 _optimize_tasks

3. 修改 `submit_optimize`:
   - status 改为 "running"
   - 调用 `asyncio.create_task(_run_optimize(task_id, payload))`

4. 修改 `push_optimize_progress` 和 `push_optimize_complete`:
   - 修复 ws_manager 引用，改为 await ws_manager.push() (异步调用)

### Task 1.3: 后端 K 线数据真实化

**文件**: `stockquant/api/routers/data.py`

**改造内容**:
1. 新增导入:
   ```python
   from stockquant.data.providers.baostock_feed import BaoStockFeed
   from stockquant.data.fetcher_manager import DataFetcherManager
   import os
   ```

2. 新增全局 DataFetcherManager 单例:
   ```python
   _data_manager = DataFetcherManager()
   _baostock_feed_instance = None  # 延迟初始化
   ```

3. 重写 `get_kline`:
   - 使用 BaoStockFeed 获取真实数据:
     ```python
     feed = BaoStockFeed(symbols=[symbol], timeframe="1d", start=start, end=end)
     feed.start()
     df = feed.get_dataframe()
     feed.stop()
     ```
   - 将 DataFrame 转为前端格式: `[{date, open, high, low, close, volume}, ...]`
   - 异常时返回空数据 + error 信息（不 crash）

4. 重写 `get_cache_stats`:
   - 扫描缓存目录获取真实文件大小和 symbol 数量
   - 返回真实统计

5. 新增 `POST /api/data/collect`:
   - 接收 `{symbol, source, start, end}`
   - 触发数据采集，返回 `{task_id, status: "collecting"}`

6. 新增 `GET /api/data/health`:
   - 返回各数据源健康状态: `[{provider, healthy, last_check, error}]`

### Task 1.4: 后端交易真实化 (PaperBroker)

**文件**: `stockquant/api/routers/trading.py`

**改造内容**:
1. 新增导入:
   ```python
   from stockquant.engine.broker import PaperBroker
   from stockquant.engine.commission import CommissionInfo
   from stockquant.models.order import Order, OrderSide, OrderType, OrderStatus
   from stockquant.models.portfolio import Portfolio
   from stockquant.data.providers.baostock_feed import BaoStockFeed
   ```

2. 新增全局实例:
   ```python
   _paper_broker = PaperBroker()
   _commission_info = CommissionInfo()
   _paper_portfolio = Portfolio(initial_cash=1_000_000)
   _paper_account = {"total_equity": 1_000_000, "available_cash": 1_000_000, "position_value": 0, "today_pnl": 0, "broker_mode": "paper"}
   ```

3. 重写 `place_order`:
   - 构造 Order 对象
   - 获取最新行情 Bar（从 BaoStockFeed 获取当日收盘价）
   - 调用 `_paper_broker.place_order(order, bar)` 撮合
   - 如果成交，更新 _paper_portfolio 和 _paper_account
   - 计算手续费使用 _commission_info

4. 重写 `get_positions`:
   - 从 _paper_portfolio.positions 读取真实持仓

5. 重写 `get_account`:
   - 从 _paper_portfolio 计算真实账户余额

6. 重写 `get_trades`:
   - 从 _paper_broker.trade_log 读取成交记录

7. 重写 `cancel_order`:
   - 调用 _paper_broker.cancel_order()

### Task 1.5: 后端 Portfolio 真实化

**文件**: `stockquant/api/routers/portfolio.py`

**改造内容**:
1. 从 trading.py 导入共享实例:
   ```python
   from stockquant.api.routers.trading import _paper_portfolio, _paper_broker, _paper_account
   ```

2. 重写 `get_positions`:
   - 从 _paper_portfolio.positions 动态生成

3. 重写 `get_account`:
   - 从 _paper_portfolio 计算汇总

4. 重写 `get_sector`:
   - 基于持仓标的动态计算行业分布（简单映射表）

5. 重写 `get_pnl`:
   - 基于成交记录计算盈亏分析

### Task 1.6: 后端 Settings 持久化 + .env 联动

**文件**: `stockquant/api/routers/settings.py`

**改造内容**:
1. 持久化到 JSON 文件:
   ```python
   _SETTINGS_FILE = Path.home() / ".stockquant" / "settings.json"

   def _load_settings():
       if _SETTINGS_FILE.exists():
           with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
               return json.load(f)
       return {}

   def _save_settings_to_file():
       _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
       with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
           json.dump(_settings, f, ensure_ascii=False, indent=2)
   ```

2. _DEFAULT_SETTINGS 从 .env 读取:
   ```python
   _DEFAULT_SETTINGS = {
       "trading.broker": os.environ.get("TRADING_BROKER", "paper"),
       "trading.admin_token": os.environ.get("TRADING_ADMIN_TOKEN", ""),
       "data_provider.source": os.environ.get("DATA_PROVIDER_SOURCE", "baostock"),
       "data_provider.api_key": os.environ.get("DATA_PROVIDER_API_KEY", ""),
       "ai.model": os.environ.get("OPENAI_MODEL", "gpt-4o"),
       "ai.temperature": float(os.environ.get("OPENAI_TEMPERATURE", "0.7")),
       "ai.max_tokens": int(os.environ.get("OPENAI_MAX_TOKENS", "4096")),
       ...
   }
   ```

3. 启动时加载: `_settings = {**_DEFAULT_SETTINGS, **_load_settings()}`

4. `save_settings` 写入文件: 调用 `_save_settings_to_file()`

5. `reset_setting` 恢复 .env 默认值: `_settings[key] = _DEFAULT_SETTINGS[key]` + `_save_settings_to_file()`

6. 新增 `GET /api/settings/health`: 返回配置状态

### Task 1.7: 前端 Settings 对接后端 API

**文件**: `web/src/pages/Settings.tsx`

**改造内容**:
1. 新增 API 调用:
   ```typescript
   import { client } from '../api/client';
   // 页面加载时
   useEffect(() => {
     client.get('/settings').then(res => {
       if (res?.settings) setValues(res.settings);
     });
   }, []);
   ```

2. 保存时调用后端:
   ```typescript
   const handleSave = async () => {
     const updates = {};
     dirtyKeys.forEach(k => { updates[k] = values[k]; });
     await client.post('/settings/save', { settings: updates });
     setDirtyKeys(new Set());
   };
   ```

3. 删除时调用后端:
   ```typescript
   const handleReset = async (key) => {
     await client.delete(`/settings/${key}`);
     // 重新从后端获取值
   };
   ```

---

## Phase 2: 前端功能补全

### Task 2.1: Backtest 增加风控规则配置

**文件**: `web/src/components/Backtest/ParamForm.tsx`

**改造**: 新增风控规则 Card:
- 单票最大仓位 Slider (0-100%, default 30%)
- 单日最大亏损 Slider (0-10%, default 5%)
- 累计最大回撤熔断 Slider (5-50%, default 15%)
- 订单频率限制 InputNumber (default 10)

**文件**: `web/src/pages/Backtest.tsx`
- 提交时将风控参数打包到 `risk_rules` 字段

### Task 2.2: Backtest 增加基准选择

**文件**: `web/src/pages/Backtest.tsx`

**改造**: DataSelector 区域增加基准 Select:
- Options: 无基准 / 沪深300 (hs300) / 中证500 (zz500) / 创业板指 (cyb)
- 提交时传 `benchmark` 字段

### Task 2.3: BacktestResult 增加基准对比曲线

**文件**: `web/src/components/Chart/EquityChart.tsx`

**改造**: 扩展 props:
```typescript
interface EquityChartProps {
  data: number[];
  benchmarkData?: number[];
  dates?: string[];
  benchmarkLabel?: string;
  height?: number;
}
```
- 图表增加第二条折线（虚线，不同颜色）
- X 轴使用日期

**文件**: `web/src/pages/BacktestResult.tsx`
- 从后端结果提取 benchmark_equity_curve 传入 EquityChart

### Task 2.4: Monitor 接入 WebSocket 实时行情

**文件**: `web/src/pages/Monitor.tsx`

**改造**:
- 使用 `useWebSocket('/ws/monitor')` 连接
- 接收 `quote` 消息更新 livePrices
- 接收 `alert` 消息展示异动告警
- 移除 Mock 随机价格生成逻辑

### Task 2.5: Monitor 增加收盘总结展示

**文件**: `web/src/pages/Monitor.tsx`

**改造**:
- 新增"收盘总结" Card
- 调用 `monitorApi.summary()` 获取内容
- 展示 Markdown 渲染的总结文本

### Task 2.6: Monitor 增加异动检测面板

**文件**: `web/src/pages/Monitor.tsx`

**改造**:
- 新增"异动检测"区域: 放量突破/涨停跌停/异动成交量
- 数据来源: monitorApi.scan() + WS 推送

### Task 2.7: AIChat 集成工具调用展示

**文件**: `web/src/components/AI/ChatPanel.tsx`

**改造**:
- Message 类型扩展: 增加 `tool_call` / `tool_result` 类型
- `tool_call`: 展示工具名 + 参数 (Card 组件)
- `tool_result`: 展示结果（表格/列表）

### Task 2.8: AIChat 信号卡片展示

**文件**: `web/src/components/AI/SignalCard.tsx`, `web/src/components/AI/ChatPanel.tsx`

**改造**:
- SignalCard 增加 type 视觉区分 (BUY 绿/SELL 红)
- ChatPanel 检测 AI 回复中的交易建议，附加 SignalCard

### Task 2.9: Strategy 增加 AI 策略生成入口

**文件**: `web/src/pages/Strategy.tsx`

**改造**:
- 新增"AI 生成策略"按钮
- 点击弹出 Modal: 自然语言输入
- 调用 `POST /api/ai/strategy/generate`
- 返回代码填入 Monaco Editor

**后端新增**: `stockquant/api/routers/ai_chat.py` 增加 `POST /api/ai/strategy/generate`

### Task 2.10: Data 增加数据采集触发按钮

**文件**: `web/src/pages/Data.tsx`

**改造**:
- 数据源表格每行增加"采集"按钮
- 调用 `POST /api/data/collect`
- 展示采集进度

### Task 2.11: Data 增加数据源健康状态

**文件**: `web/src/pages/Data.tsx`

**改造**:
- 调用 `GET /api/data/health`
- 数据源表格增加"状态"列 (Tag: 健康/不健康/检查中)

### Task 2.12: Trading 确认弹窗增加手续费预估

**文件**: `web/src/pages/Trading.tsx`

**改造**:
- 确认弹窗增加手续费预估 (佣金 + 印花税 + 过户费)
- 增加 A 股规则提示 (T+1, 100股整数倍)

### Task 2.13: Settings 条件显隐补全

**文件**: `web/src/pages/Settings.tsx`

**改造**:
- 补全 when 条件: 券商 QMT 参数、数据源 API Key/URL、AI strategy_llm_*
- 已在 1.7 完成后端 API 集成

---

## Phase 3: 高级功能

### Task 3.1: Monitor 实时 K 线图
- 新建 `web/src/components/Chart/RealtimeKline.tsx`
- ECharts candlestick + WS 实时更新
- 支持 MA/EMA/BOLL 叠加

### Task 3.2: Monitor 社交媒体情绪监控
- 新建 `web/src/components/Monitor/SentimentPanel.tsx`
- 情绪仪表盘 + 趋势图

### Task 3.3: AIChat 对话式策略开发 (F028)
- AI 对话增加"策略开发"模式
- 自然语言 → 策略代码 → 一键复制

### Task 3.4: AIChat 对话式数据分析 (F028)
- AI 对话增加"数据分析"模式
- 提问 → 查询数据 → 图表 + 分析

### Task 3.5: AIChat 对话式盯盘 (F028)
- AI 对话增加"盯盘"模式
- 指定标的 → 启动监控 → 推送信号

### Task 3.6: 策略对比历史 (F027)
- 后端 `GET /api/comparison/history` 返回真实数据
- 前端对比图表组件

### Task 3.7: Portfolio 个股权益曲线
- 持仓表格增加"权益曲线"按钮
- Modal 展示个股级别曲线

### Task 3.8: 通知路由实现
- `GET /api/notifications`
- `PUT /api/notifications/{id}/read`
- `DELETE /api/notifications/{id}`
- 前端 notificationStore 对接

---

## Phase 4: 部署、安全与配置

### Task 4.1: Docker Compose 更新
- 添加 PostgreSQL 服务
- 添加 ChromaDB 服务
- 更新环境变量 + healthcheck

### Task 4.2: Nginx 反向代理配置
- 新建 `web/nginx/default.conf`
- SPA + API 代理 + WS 代理 + Gzip

### Task 4.3: JWT 认证实现
- `stockquant/api/deps.py` 实现 JWT
- `POST /api/auth/login`
- 受保护端点添加认证

### Task 4.4: Rate Limiting
- `stockquant/api/main.py` 集成 slowapi
- 默认 100 req/min

### Task 4.5: API Key 加密存储
- `stockquant/api/routers/settings.py` 使用 cryptography 加密

### Task 4.6: 前端环境变量补全
- 创建 `web/.env` + `web/.env.production`
- VITE_API_URL / VITE_WS_URL / VITE_API_HOST
- client.ts 和 WebSocket 连接使用环境变量

### Task 4.7: 后端 .env 变量全量消费
- AI/数据/交易/通知/信号路由读取 .env

### Task 4.8: stockquant_config.yaml 配置文件
- 新建 `stockquant/config.py` 配置加载模块
- 新建 `stockquant_config.yaml` 模板
- 配置优先级: Settings API > YAML > .env > 代码默认值

### Task 4.9: Settings API 与 .env 完整联动
- GET 返回值优先级: JSON 覆盖 > .env > 代码默认值
- 保存写入 JSON + 热生效
- 删除回退到 .env 值

---

## 关键设计决策

1. **回测异步执行**: 使用 `asyncio.create_task` + `run_in_executor`，因为 Cerebro.run() 是 CPU 密集型同步操作
2. **交易共享状态**: trading.py 和 portfolio.py 共享 `_paper_portfolio` 实例，通过模块级导入
3. **Settings 持久化**: 使用 JSON 文件而非数据库，因为配置项少且结构简单
4. **K 线数据**: 每次请求创建 BaoStockFeed 实例，后续可加缓存
5. **WebSocket 推送**: 复用现有 ws_manager，回测/优化完成后推送
6. **策略映射**: STRATEGY_MAP 同时支持简写名和完整类名

## 验证方式

每个 Task 完成后:
1. 后端: 启动 Uvicorn，用 curl/httpie 测试 API 端点
2. 前端: 启动 Vite，在浏览器验证页面功能
3. 集成: 前端调用后端 API 验证数据流
