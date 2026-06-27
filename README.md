# StockQuant 2.0

> **机构级中国 A 股量化交易平台**
> 从数据采集 → 指标计算 → 策略配置 → 回测验证 → 实时盯盘 → AI 辅助决策 → 风控执行，全流程闭环。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Alpha-orange)]()
[![Tests](https://img.shields.io/badge/tests-1250%20passed-brightgreen)]()

***

## 产品定位

StockQuant 2.0 是一个面向**专业量化开发者**的 **AI 原生机构级**中国 A 股量化交易平台。

**核心差异**：

- **AI Agent 全流程**：ReAct 架构 + 7+ 个 AI Agent 覆盖指标发现、策略生成、回测解读、辅助决策、动态风控、实时盯盘、信息采集
- **记忆 + 反幻觉**：三级持久化记忆系统 + 四步反幻觉 JSON 修复
- **机构级引擎**：事件驱动引擎 + 完整 OMS + 多资产投资组合 + 30+ 回测指标
- **渐进式平台**：简单场景简单用（自然语言 → 策略），复杂场景深度用（完整 API）

**对标框架**：backtrader / VNPy / vectorbt，同时通过 AI Agent 架构实现差异化。

**当前状态**：完成 **30/30 功能（96%+）**，**1250 测试通过**，11 skipped。

***

## 快速开始

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/fssl168/quantclaw.git
cd StockQuant

# 2. 安装核心依赖
pip install -e .

# 3. 安装 AI 模块（可选）
pip install -e ".[ai]"

# 4. 安装 API 网关（可选）
pip install -e ".[web]"

# 5. 安装可选指标库（可选）
pip install -e ".[talib]"   # TA-Lib 高性能 C 库
# 或
pip install -e ".[pandas-ta]"  # 纯 Python 实现
```

### 运行第一个回测

```python
from stockquant import Cerebro, BaseStrategy, BacktestBroker, CommissionInfo
from stockquant.data.providers import BaoStockFeed

# 定义策略
class MyStrategy(BaseStrategy):
    name = "Dual MA Crossover"
    parameters = {"fast": 5, "slow": 20}

    def on_start(self):
        self.ma_fast = self.EMA(self.data, self.parameters["fast"])
        self.ma_slow = self.EMA(self.data, self.parameters["slow"])

    def on_bar(self, bars):
        bar = bars["sh600519"]
        if self.ma_fast.crossed_above(self.ma_slow):
            self.order_market(bar, 100)
        elif self.ma_fast.crossed_below(self.ma_slow):
            self.close_all()

# 运行回测
cerebro = Cerebro()
cerebro.add_data(BaoStockFeed(
    symbols=["sh600519"],
    timeframe="1d",
    start="2023-01-01",
    end="2024-12-31",
))
cerebro.add_strategy(MyStrategy, fast=5, slow=20)
cerebro.broker = BacktestBroker()
cerebro.commission = CommissionInfo(stamp_tax=0.0005)
results = cerebro.run()

# 查看报告
cerebro.show_report(results)
```

### 使用 AI 生成策略

```python
from stockquant.ai import StrategyAgent

# 初始化 AI Agent
agent = StrategyAgent(
    model="deepseek/deepseek-chat",  # 或 "gpt-4o"
    api_key="your-api-key",
)

# 自然语言 → 策略代码（完整 ReAct 推理链路）
result = agent.generate("当 MACD 金叉且 RSI<30 时买入，仓位 20%，止损 5%")
print(result.code)       # 生成的策略 Python 代码
print(result.score.total)  # AI 评分（0-100）
print(result.validation.errors)  # 验证结果
```

### AI 辅助决策

```python
from stockquant.ai import DecisionAgent, DecisionMode

decision = DecisionAgent(
    model="gpt-4o",
    mode=DecisionMode.SEMI_AUTO,  # DecisionMode.AUTO / SEMI_AUTO / READ_ONLY
)

advice = decision.evaluate({
    "symbol": "sh600519",
    "direction": "BUY",
    "qty": 100,
    "price": 1800.0,
})
print(advice.action)         # confirm / reject / modify
print(advice.confidence)     # 0.0-1.0
print(advice.risk_warnings)  # 风险警告列表
```

***

## 架构概览

```
stockquant/
├── engine/          # 事件驱动引擎（Cerebro / EventEngine / OMS / Portfolio / Broker / Sizer / RiskManager）
├── strategy/        # 策略框架（BaseStrategy / 模板库 7 套 / 信号管线 / YAML 加载）
├── indicators/      # 技术指标（18+ 指标 + DSL 装饰器 / 移动平均 / 振荡器 / 趋势 / 波动率）
├── data/            # 数据层（BaoStock / AkShare / CSV / Parquet / SQLite + DataService 统一服务）
├── models/          # 数据模型（Bar / Order / Position / Account / Trade / Portfolio）
├── agent/           # Agent 基础设施（LLMAdapter / ReActAgent / ToolRegistry）
├── ai/              # AI Agent + FinMem 三模块（Profiling/Memory/Decision）+ 反幻觉 + 信息管线 + AIService
├── analytics/       # 分析报表（HTML/JSON 报表 + 市场复盘）
├── execution/       # 交易执行（9 通知渠道 + 消息路由 + Markdown 图片渲染 + 券商接入）
├── persistence/     # 持久化（SQLAlchemy ORM + 审计日志 + 策略/回测/消息存储）
├── api/             # API 网关（FastAPI 127 端点 / 23 router / 6 WebSocket）
└── scheduler.py     # 定时调度器（schedule + 交易日检查）
```

### 核心数据流

```
用户策略 → Cerebro → EventEngine → BarEvent → BaseStrategy.on_bar()
  → Broker.place_order() → RiskManager.check() → Sizer → 撮合引擎 → 更新 Portfolio

ReAct 循环:
  LLMAdapter.call_with_tools() → ToolRegistry.execute() → Observation → 下一轮推理
  → StrategyAgent.generate() / DecisionAgent.evaluate()

消息推送:
  DecisionAgent → MessageRouter → [钉钉/飞书/Telegram/邮件/Discord/PushPlus/Server酱/Webhook/企微]
```

### Agent 基础设施

StockQuant 使用三层 Agent 架构：

| 层            | 模块                                    | 说明                                                                                   |
| ------------ | ------------------------------------- | ------------------------------------------------------------------------------------ |
| **基础设施**     | `LLMAdapter`                          | 基于 litellm 的 provider-agnostic LLM 调用，支持模型回退链                                        |
| **基础设施**     | `ReActAgent`                          | Reasoning + Acting 循环，`@tool` 装饰器自动注册 JSON Schema 工具                                 |
| **基础设施**     | `ToolRegistry`                        | 工具注册中心，`@tool` 装饰器从函数签名自动生成 OpenAI tool 定义                                           |
| **AI Agent** | `StrategyAgent`                       | 6 个工具：解析意图、生成代码、验证代码、回测、评分、优化建议                                                      |
| **AI Agent** | `DecisionAgent`                       | 6 个工具：信号验证、风险评估、市场环境、新闻情绪、仓位评估、决策生成 + 自动止损止盈                                         |
| **AI Agent** | `BacktestAgent`                       | 回测结果自动解读，过拟合检测                                                                       |
| **AI Agent** | `IndicatorAgent`                      | 自动推荐最优指标组合                                                                           |
| **AI Agent** | `RiskAgent`                           | 动态风控参数调整                                                                             |
| **风险偏好**     | `RiskProfile` / `ProfileTransitioner` | 风险偏好枚举（conservative/neutral/aggressive）+ 7 天冷却期动态转换                                  |
| **多因子评分**    | `RecallScorer`                        | 三因子召回评分（α·relevance + β·recency + γ·importance）                                      |
| **分层记忆**     | `L2Store` / `L3Store`                 | 分层记忆（shallow 3d / intermediate 90d / deep 365d / working 1d）                         |
| **分层记忆**     | `WorkingMemory`                       | 三组件：Summarization / Observation / Reflection                                         |
| **洞察转决策**    | `InsightsBridge`                      | 3 层记忆检索 + Reflection → DecisionContext 组装                                            |
| **反幻觉**      | `ClaimVerifier`                       | FINGROUND 六类声明验证（numeric/temporal/entity\_attr/comparative/regulatory/computational） |
| **反幻觉**      | `CrossValidator`                      | 多模型并行验证（asyncio.gather + majority vote）                                              |
| **采集端**      | `CollectorAuditLog`                   | 环形缓冲 + 线程安全 + 持久化回调                                                                  |
| **采集端**      | `SourceVerifier`                      | FAKE\_SOURCES 黑名单 + SHA-256 指纹变更检测                                                   |
| **管线**       | `PipelineScheduler`                   | 基于 asyncio 的 4 级调度（realtime/minute/hourly/daily）                                     |
| **统一服务**     | `AIService`                           | AI 服务统一入口（Agent Orchestrator + Memory + Hallucination + Pipeline）                    |
| **统一服务**     | `DataService`                         | 行情数据统一服务（BaoStock/AkShare 缓存 + 标准化）                                                  |

***

## 功能清单

### 传统量化能力（F001-F018）

| 模块            | 功能                                         | 状态     |
| ------------- | ------------------------------------------ | ------ |
| **引擎**        | 事件驱动回测引擎（F001）                             | ✅ Done |
| **OMS**       | 订单管理（5 种订单类型 + 状态机 + T+1）（F002）            | ✅ Done |
| **组合**        | 多资产投资组合（F003）                              | ✅ Done |
| **策略**        | BaseStrategy 框架 + 生命周期钩子（F004）             | ✅ Done |
| **指标**        | 30+ 回测统计指标 Sharpe/Sortino/Calmar（F005）     | ✅ Done |
| **Broker**    | 回测/模拟/实盘抽象层（F006）                          | ✅ Done |
| **费用**        | A 股佣金/滑点/印花税建模（F007）                       | ✅ Done |
| **优化**        | 参数优化器（网格 + 随机 + Walk-Forward）（F008）        | ✅ Done |
| **风控**        | 风险管理模块（F009）                               | ✅ Done |
| **仓位**        | 仓位管理 Kelly/ATR/波动率目标/FixedFraction（F010）   | ✅ Done |
| **数据**        | 5 数据源 + 标准化 + 交易日历 + 故障切换（F011）            | ✅ Done |
| **模拟**        | 模拟盘模式（PaperBroker）（F012）                   | ✅ Done |
| **报表**        | HTML/JSON 回测报表 + 市场复盘（F013）                | ✅ Done |
| **模板**        | 7 套内置策略模板（F014）                            | ✅ Done |
| **DSL**       | 自定义指标装饰器 + plot\_indicator 可视化（F015）       | ✅ Done |
| **Dashboard** | Web Dashboard 前端（React SPA 完全替代 Streamlit） | ✅ Done |
| **实盘**        | LiveBroker + XTP/QMT/CTP 券商接入（F017）        | ✅ Done |
| **推送**        | 9 通知渠道 + 消息路由（F018）                        | ✅ Done |

### AI 能力（F019-F028）

| Agent    | 功能                                      | 状态     |
| -------- | --------------------------------------- | ------ |
| **信号管线** | 信号生成 + 准确率统计 + 衰减分析（F019）               | ✅ Done |
| **信息处理** | 记忆三模块 + 4 阶段管线 + 反幻觉 + 4 级调度（F020）      | ✅ Done |
| **指标发现** | 自动推荐最优指标组合（F021）                        | ✅ Done |
| **策略生成** | ReAct 自然语言 → 策略代码 + 验证 + 评分（F022）       | ✅ Done |
| **回测解读** | 自动解读回测结果 + 过拟合检测（F023）                  | ✅ Done |
| **实时盯盘** | MonitorAgent 实时盯盘 + 异动检测（F024）          | ✅ Done |
| **辅助决策** | ReAct 信号验证 + 决策建议 + 审计日志 + 自动止损止盈（F025） | ✅ Done |
| **动态风控** | RiskAgent 动态风控参数（F026）                  | ✅ Done |
| **策略对比** | 多策略横向对比 + 组合优化（F027）                    | ✅ Done |
| **交互界面** | 对话式策略/数据/盯盘（F028）                       | ✅ Done |

### 基础设施（F029-F030）

| 模块              | 功能                                                                      | 状态                    |
| --------------- | ----------------------------------------------------------------------- | --------------------- |
| **API Gateway** | FastAPI RESTful 23 router + 6 WebSocket（F029）                           | ✅ Partial（后端 100% 完成） |
| **Docker**      | Docker Compose 一键部署（F030）                                               | ✅ Done                |
| **API 基础设施**    | repository\_v2（427 行全新持久化层 + 18 ORM 模型）                                 | ✅ Done                |
| **AI Service**  | AIService 统一编排层（Agent Orchestrator + Memory + Hallucination + Pipeline） | ✅ Done                |

***

## Web Dashboard

### API 后端（已完成）

FastAPI 后端已实现，提供以下 RESTful API：

| 路由            | 端点                                             | 功能                 |
| ------------- | ---------------------------------------------- | ------------------ |
| Dashboard     | `GET /api/dashboard`                           | 综合仪表盘数据            |
| Backtest      | `POST /api/backtest`, `GET /api/backtest/<id>` | 回测创建与结果查询          |
| Strategy      | `GET /api/strategy`, `POST /api/strategy`      | 策略 CRUD            |
| Monitor       | `GET/PUT /api/monitor`                         | 盯盘配置与行情推送          |
| AI Chat       | `POST /api/ai/chat`                            | AI 对话（SSE 流式）      |
| Comparison    | `GET/POST /api/comparison`                     | 策略横向对比             |
| Notification  | `GET/POST /api/notification`                   | 通知管理               |
| Data          | `GET /api/data`                                | 数据管理               |
| Settings      | `GET/POST/DELETE /api/settings`                | 配置管理（14 分组）        |
| Trading       | `GET/POST /api/trading`                        | 交易执行               |
| Portfolio     | `GET /api/portfolio`                           | 投资组合               |
| Optimize      | `POST /api/optimize`                           | 参数优化               |
| Auth          | `POST /api/auth`                               | JWT 登录/注册          |
| Signal        | `GET/POST /api/signal`                         | 信号管理               |
| Scheduler     | `GET/POST/DELETE /api/scheduler`               | 定时调度               |
| Memory        | `GET/POST /api/memory`                         | 记忆系统               |
| Hallucination | `GET/POST /api/hallucination`                  | 反幻觉系统              |
| Pipeline      | `GET/POST /api/pipeline`                       | AI 信息管线            |
| Audit         | `GET /api/audit`                               | 审计日志               |
| Monitoring    | `GET /api/health`                              | 健康检查               |
| WebSocket     | 6 端点                                           | 实时行情/回测进度/通知/AI 对话 |

前端（React 18 + TypeScript + Ant Design 5 + ECharts + Monaco Editor）已完整开发，17 个页面（16 个页面 + 1 个别名路由）、26 个组件、11 个 API 客户端、8 个 Zustand stores。

***

## 配置说明

### AI 配置（环境变量驱动）

StockQuant 通过环境变量解析 LLM API Key，无需硬编码：

```bash
export OPENAI_API_KEY="sk-..."
# 或
export ANTHROPIC_API_KEY="sk-ant-..."
# 或
export DEEPSEEK_API_KEY="sk-..."
```

```python
from stockquant.agent import LLMAdapter

# 自动从环境变量读取 API Key
adapter = LLMAdapter(model="gpt-4o")
# 或指定模型
adapter = LLMAdapter(model="deepseek/deepseek-chat", fallback_models=["gpt-4o"])
```

### AI 辅助决策配置

```python
from stockquant.ai import DecisionAgent, DecisionMode

agent = DecisionAgent(
    model="gpt-4o",
    mode=DecisionMode.SEMI_AUTO,  # auto / semi_auto / read_only
)
advice = agent.evaluate({
    "symbol": "sh600519",
    "direction": "BUY",
    "qty": 100,
})
```

***

## 里程碑

| 版本               | 时间  | 内容                                                                                     |
| ---------------- | --- | -------------------------------------------------------------------------------------- |
| **v2.0.0-alpha** | 已完成 | 事件引擎 + OMS + 投资组合 + 策略基类 + 18 指标 + 5 AI Agent                                          |
| **v2.0.0-beta**  | 已完成 | + 佣金/滑点 + 参数优化 + 风控 + 报表 + Broker 抽象 + 9 通知渠道 + API 网关                                 |
| **v2.0.0-rc**    | 已完成 | + 数据缓存 + 模拟盘 + AI ReAct 循环 + 持久化 + 信号管线 + 763 测试                                       |
| **v2.0.1**       | 已完成 | + 记忆系统 + 反幻觉 + 信息管线 + AI 对话 + 盯盘 + 策略对比 + 完整前端                                         |
| **v2.0.2**       | 已完成 | + DataService/AIService 统一层 + config 治理 + 数据库持久化完整化 + API 基础设施 (repository\_v2)        |
| **v2.0.3**       | 已完成 | + FinMem 三模块架构（Profiling/Memory/Decision）+ 反幻觉系统 + 信息处理管线四阶段 + 4 级调度 + 采集端增强 + 427 新测试 |

**当前进度**：30/30 功能完成（96%+），1250 测试通过，11 skipped。

***

## 从 v1 迁移

StockQuant v1.x 已标记为 EOL（End of Life）。v2.0 采用全新 API，不再兼容 v1。

```python
# v2 写法（推荐）
from stockquant import BaseStrategy, Cerebro
from stockquant.data.providers import BaoStockFeed

class MyStrategy(BaseStrategy):
    def on_start(self):
        self.macd = self.MACD(self.data, fast=12, slow=26, signal=9)

    def on_bar(self, bars):
        bar = bars["sh600519"]
        if self.macd["MACD"].crossed_above(self.macd["MACDSignal"]):
            self.order_market(bar, 100)

cerebro = Cerebro()
cerebro.add_data(BaoStockFeed(
    symbols=["sh600519"],
    timeframe="1d",
    start="2023-01-01",
    end="2024-12-31",
))
cerebro.add_strategy(MyStrategy)
results = cerebro.run()
```

***

## 技术栈

| 类别          | 依赖                                                                                                                                 |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **核心**      | numpy, pandas, matplotlib, jinja2, tenacity, exchange-calendars, schedule, pyyaml, markdown, Pillow, requests, sqlalchemy, pyarrow |
| **AI**      | openai, anthropic, litellm, httpx, json-repair                                                                                     |
| **Web API** | fastapi, uvicorn, pydantic v2, python-jose, python-socketio, aiohttp, gunicorn, slowapi                                            |
| **数据**      | baostock, akshare                                                                                                                  |
| **可选指标**    | TA-Lib / pandas-ta                                                                                                                 |
| **前端**      | react 18, typescript, vite, ant-design 5, echarts-for-react, zustand, axios, monaco-editor, dayjs, marked, sass                    |
| **测试**      | pytest, ruff, coverage                                                                                                             |

***

## 测试

```bash
# 运行全部测试
pytest tests/ -v

# 覆盖率
pytest tests/ --cov=stockquant --cov-report=html
```

当前：**1250 tests collected, 0 failed, 11 skipped**。

***

## 最近变更

| 日期         | 提交         | 摘要                                                                                                                                                                                |
| ---------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-06-27 | `acb0ba17` | **F020 FinMem 三模块架构增强完整落地（Phase A-F）**：Profiling + 分层记忆 + WorkingMemory + 反幻觉（ClaimVerifier/CrossValidator）+ 管线四阶段 + 4 级调度 + 采集端增强；15 新文件 + 18 修改 + 427 新测试；135 文件变更，+19837/-7067 |
| 2026-06-27 | `5f1ac893` | **AI 子系统完善 + API 对齐 + 前端修复**：`AIService` 统一编排层（156 行）、`repository_v2` 427 行全新持久化、auth/monitor/trading 端点对齐、事件引擎优化、broker 层重构、41 文件变更                                              |
| 2026-06-26 | `63f834a4` | **AI 基础设施 API + 记忆/反幻觉/管线 + 全面测试**：761→763 测试通过；记忆/反幻觉管线 API 端点完整化；openapi 代码生成（Service + Models 2000+ 行）；195 文件变更                                                                |
| 2026-06-25 | `e316570f` | **数据层统一 + AI 层对齐 + 前端对齐**：DataService/AIService 集成、前端 store 对齐后端 API、config 治理                                                                                                    |
| 2026-06-25 | `b961c239` | **前端构建修复**：App.tsx never type、Data.tsx map 类型、vite/tsconfig 配置、monitor global 修复                                                                                                  |

***

## 许可

MIT License

***

> **说明**：StockQuant 2.0 目前处于 Alpha 开发阶段，API 和功能尚未稳定。
> 当前版本 2.0.2-dev，完成 30/30 功能（97%+），1250 测试通过，6 skipped。

