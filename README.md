# StockQuant 2.0

> **机构级中国 A 股量化交易平台**
> 从数据采集 → 指标计算 → 策略配置 → 回测验证 → 实时盯盘 → AI 辅助决策 → 风控执行，全流程闭环。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Alpha-orange)]()
[![Tests](https://img.shields.io/badge/tests-575%20passed-brightgreen)]()

---

## 产品定位

StockQuant 2.0 是一个面向**专业量化开发者**的 **AI 原生机构级**中国 A 股量化交易平台。

**核心差异**：
- **AI Agent 全流程**：ReAct 架构 + 5 个 AI Agent 覆盖指标发现、策略生成、回测解读、辅助决策、动态风控
- **记忆 + 反幻觉**：三级持久化记忆系统 + 四步反幻觉 JSON 修复
- **机构级引擎**：事件驱动引擎 + 完整 OMS + 多资产投资组合 + 30+ 回测指标
- **渐进式平台**：简单场景简单用（自然语言 → 策略），复杂场景深度用（完整 API）

**对标框架**：backtrader / VNPy / vectorbt，同时通过 AI Agent 架构实现差异化。

**当前状态**：完成 **26/30 功能（87%）**，**575 测试通过**。

---

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
from stockquant.data import BaoStockFeed

# 定义策略
class MyStrategy(BaseStrategy):
    name = "Dual MA Crossover"
    parameters = {"fast": 5, "slow": 20}

    def on_start(self):
        self.ma_fast = self.EMA(period=self.parameters["fast"])
        self.ma_slow = self.EMA(period=self.parameters["slow"])

    def on_bar(self, bars):
        if self.ma_fast.crossed_above(self.ma_slow):
            self.order_market(self.data.close[0], 100)
        elif self.ma_fast.crossed_below(self.ma_slow):
            self.close_all()

# 运行回测
cerebro = Cerebro()
cerebro.add_data(BaoStockFeed(
    symbol="sh600519",
    timeframe="1d",
    start_date="2023-01-01",
    end_date="2024-12-31",
))
cerebro.add_strategy(MyStrategy, fast=5, slow=20)
cerebro.set_broker(BacktestBroker())
cerebro.set_commission(CommissionInfo(stamp_tax=0.0005))
results = cerebro.run()

# 查看报告
cerebro.show_report(results)
```

### 使用 AI 生成策略

```python
from stockquant.ai import StrategyAgent, NewsSearcher
from stockquant.data import DataFetcherManager

# 初始化 AI Agent
fetcher = DataFetcherManager()
searcher = NewsSearcher()
agent = StrategyAgent(
    model="gpt-4o",
    api_key="your-api-key",
    fetcher_manager=fetcher,
    news_searcher=searcher,
)

# 自然语言 → 策略代码（完整 ReAct 推理链路）
result = agent.generate("当 MACD 金叉且 RSI<30 时买入，仓位 20%，止损 5%")
print(result.code)       # 生成的策略 Python 代码
print(result.score.total)  # AI 评分（0-100）
print(result.validation.errors)  # 验证结果
```

### AI 辅助决策

```python
from stockquant.ai import DecisionAgent

decision = DecisionAgent(
    model="gpt-4o",
    mode="semi_auto",  # auto / semi_auto / read_only
    fetcher_manager=fetcher,
    news_searcher=searcher,
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

---

## 架构概览

```
stockquant/
├── engine/          # 事件驱动引擎（Cerebro / EventEngine / OMS / Portfolio / Broker / Sizer / RiskManager）
├── strategy/        # 策略框架（BaseStrategy / 模板库 7 套 / 信号管线 / YAML 加载）
├── indicators/      # 技术指标（18+ 指标 + DSL 装饰器 / 移动平均 / 振荡器 / 趋势 / 波动率）
├── data/            # 数据层（BaoStock / AkShare / CSV / Parquet / SQLite + 标准化 + 交易日历 + 故障切换）
├── models/          # 数据模型（Bar / Order / Position / Account / Trade / Portfolio）
├── agent/           # Agent 基础设施（LLMAdapter / ReActAgent / ToolRegistry）
├── ai/              # AI Agent（StrategyAgent / DecisionAgent / BacktestAgent / IndicatorAgent / RiskAgent）
├── analytics/       # 分析报表（HTML/JSON 报表 + 市场复盘）
├── execution/       # 交易执行（9 通知渠道 + 消息路由 + Markdown 图片渲染）
├── persistence/     # 持久化（SQLAlchemy ORM + 审计日志 + 策略/回测/消息存储）
├── api/             # API 网关（FastAPI RESTful + WebSocket + 3 路由）
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

| 层 | 模块 | 说明 |
|----|------|------|
| **基础设施** | `LLMAdapter` | 基于 litellm 的 provider-agnostic LLM 调用，支持模型回退链 |
| **基础设施** | `ReActAgent` | Reasoning + Acting 循环，`@tool` 装饰器自动注册 JSON Schema 工具 |
| **基础设施** | `ToolRegistry` | 工具注册中心，`@tool` 装饰器从函数签名自动生成 OpenAI tool 定义 |
| **AI Agent** | `StrategyAgent` | 6 个工具：解析意图、生成代码、验证代码、回测、评分、优化建议 |
| **AI Agent** | `DecisionAgent` | 6 个工具：信号验证、风险评估、市场环境、新闻情绪、仓位评估、决策生成 |
| **AI Agent** | `BacktestAgent` | 回测结果自动解读，过拟合检测 |
| **AI Agent** | `IndicatorAgent` | 自动推荐最优指标组合 |
| **AI Agent** | `RiskAgent` | 动态风控参数调整 |

---

## 功能清单

### 传统量化能力（F001-F018）

| 模块 | 功能 | 状态 |
|------|------|------|
| **引擎** | 事件驱动回测引擎（F001） | ✅ Done |
| **OMS** | 订单管理（5 种订单类型 + 状态机 + T+1）（F002） | ✅ Done |
| **组合** | 多资产投资组合（F003） | ✅ Done |
| **策略** | BaseStrategy 框架 + 生命周期钩子（F004） | ✅ Done |
| **指标** | 30+ 回测统计指标 Sharpe/Sortino/Calmar（F005） | ✅ Done |
| **Broker** | 回测/模拟/实盘抽象层（F006） | ✅ Done |
| **费用** | A 股佣金/滑点/印花税建模（F007） | ✅ Done |
| **优化** | 参数优化器（网格 + 随机 + Walk-Forward）（F008） | ✅ Done |
| **风控** | 风险管理模块（F009） | ✅ Done |
| **仓位** | 仓位管理 Kelly/ATR/波动率目标/FixedFraction（F010） | ✅ Done |
| **数据** | 5 数据源 + 标准化 + 交易日历 + 故障切换（F011） | ✅ Done |
| **模拟** | 模拟盘模式（PaperBroker）（F012） | ✅ Done |
| **报表** | HTML/JSON 回测报表 + 市场复盘（F013） | ✅ Done |
| **模板** | 7 套内置策略模板（F014） | ✅ Done |
| **DSL** | 自定义指标装饰器 + plot_indicator 可视化（F015） | ✅ Done |
| **Dashboard** | Web Dashboard 前端 | ⚠️ Planned（API 后端已完成） |
| **实盘** | LiveBroker 实盘骨架（F017） | ⚠️ Skeleton |
| **推送** | 9 通知渠道 + 消息路由（F018） | ✅ Done |

### AI 能力（F019-F028）

| Agent | 功能 | 状态 |
|-------|------|------|
| **信号管线** | 信号生成 + 准确率统计 + 衰减分析（F019） | ✅ Done |
| **信息处理** | 新闻搜索 + 持久化 + JSON 修复（F020） | ⚠️ Partial |
| **指标发现** | 自动推荐最优指标组合（F021） | ✅ Done |
| **策略生成** | ReAct 自然语言 → 策略代码 + 验证 + 评分（F022） | ✅ Done |
| **回测解读** | 自动解读回测结果 + 过拟合检测（F023） | ✅ Done |
| **实时盯盘** | MonitorAgent 实时盯盘 + 异动检测（F024） | ❌ Planned |
| **辅助决策** | ReAct 信号验证 + 决策建议 + 审计日志（F025） | ✅ Done |
| **动态风控** | RiskAgent 动态风控参数（F026） | ✅ Done |
| **策略对比** | 多策略横向对比 + 组合优化（F027） | ❌ Planned |
| **交互界面** | 对话式策略/数据/盯盘（F028） | ❌ Planned |

### 基础设施（F029-F030）

| 模块 | 功能 | 状态 |
|------|------|------|
| **API Gateway** | FastAPI RESTful + WebSocket（F029） | ⚠️ Partial（后端完成） |
| **Docker** | Docker Compose 一键部署（F030） | ❌ Planned |

---

## Web Dashboard

### API 后端（已完成）

FastAPI 后端已实现，提供以下 RESTful API：

| 路由 | 端点 | 功能 |
|------|------|------|
| Dashboard | `GET /api/dashboard` | 综合仪表盘数据 |
| Backtest | `POST /api/backtest`, `GET /api/backtest/<id>` | 回测创建与结果查询 |
| Strategy | `GET /api/strategy`, `POST /api/strategy` | 策略 CRUD |
| WebSocket | `WS /ws` | 实时消息推送 |

前端部分（React + Ant Design + ECharts）为规划中。

---

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

---

## 里程碑

| 版本 | 时间 | 内容 |
|------|------|------|
| **v2.0.0-alpha** | 已完成 | 事件引擎 + OMS + 投资组合 + 策略基类 + 18 指标 + 5 AI Agent |
| **v2.0.0-beta** | 已完成 | + 佣金/滑点 + 参数优化 + 风控 + 报表 + Broker 抽象 + 9 通知渠道 + API 网关 |
| **v2.0.0-rc** | 进行中 | + 数据缓存 + 模拟盘 + AI ReAct 循环 + 持久化 + 信号管线 + 575 测试 |
| **v2.0.0** | 规划中 | + 完整 Web Dashboard 前端 + AI 对话界面 + 券商 API + Docker |

**当前进度**：26/30 功能完成（87%），575 测试通过。

---

## 从 v1 迁移

StockQuant v1.x 已标记为 EOL（End of Life）。v2.0 采用全新 API，不再兼容 v1。

```python
# v2 写法（推荐）
from stockquant import BaseStrategy, Cerebro, BaoStockFeed

class MyStrategy(BaseStrategy):
    def on_start(self):
        self.MACD = self.MACD()

    def on_bar(self, bars):
        if self.MACD.line1.crossed_above(self.MACD.line2):
            self.order_market(self.data.close[0], 100)

cerebro = Cerebro()
cerebro.add_data(BaoStockFeed(symbol="sh600519", timeframe="1d",
                               start_date="2023-01-01", end_date="2024-12-31"))
cerebro.add_strategy(MyStrategy)
results = cerebro.run()
```

---

## 技术栈

| 类别 | 依赖 |
|------|------|
| **核心** | numpy, pandas, matplotlib, jinja2, tenacity, exchange-calendars, schedule, pyyaml, markdown, Pillow |
| **AI** | openai, anthropic, litellm, httpx, json-repair |
| **Web API** | fastapi, uvicorn, pydantic v2 |
| **数据** | baostock, akshare, pyarrow |
| **可选指标** | TA-Lib / pandas-ta |
| **测试** | pytest, ruff, coverage |

---

## 测试

```bash
# 运行全部测试
pytest tests/ -v

# 覆盖率
pytest tests/ --cov=stockquant --cov-report=html
```

当前：**575 tests passed, 0 failed**。

---

## 许可

MIT License

---

> **说明**：StockQuant 2.0 目前处于 Alpha 开发阶段，API 和功能尚未稳定。
> 当前版本 2.0.0-dev，完成 26/30 功能（87%），575 测试通过。
