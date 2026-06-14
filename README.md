# StockQuant 2.0

> **机构级中国 A 股量化交易平台**
> 从数据采集 → 指标计算 → 策略配置 → 回测验证 → 实时盯盘 → AI 辅助决策 → 风控执行，全流程闭环。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Alpha-orange)]()

---

## 产品定位

StockQuant 2.0 是一个面向**专业量化开发者**的 **AI 原生机构级**中国 A 股量化交易平台。

**核心差异**：
- **AI Agent 全流程**：6 个 AI Agent 覆盖数据采集、指标发现、策略生成、回测解读、实时盯盘、动态风控
- **记忆 + 反幻觉**：三级记忆系统 + 五步反幻觉纠正，深度嵌入信息处理的每个环节
- **机构级引擎**：事件驱动引擎 + 完整 OMS + 多资产投资组合 + 30+ 回测指标
- **渐进式平台**：简单场景简单用（自然语言 → 策略），复杂场景深度用（完整 API）

**对标框架**：backtrader / VNPy / vectorbt，同时通过 AI Agent 架构实现差异化。

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
pip install openai anthropic chromadb sentence-transformers

# 4. 安装前端依赖（可选，需 node.js 18+）
cd web && npm install && cd ..

# 5. 安装后端 API 依赖（可选）
pip install fastapi uvicorn pydantic python-jose
```

### 运行第一个回测

```python
from stockquant.engine import Cerebro
from stockquant.strategy import BaseStrategy
from stockquant.data import DataFeed
from stockquant.broker import BacktestBroker
from stockquant.commission import AShareCommission

# 定义策略
class MyStrategy(BaseStrategy):
    name = "Dual MA Crossover"
    parameters = {"fast": 5, "slow": 20}

    def on_start(self):
        self.ma_fast = self.EMA(period=self.parameters["fast"])
        self.ma_slow = self.EMA(period=self.parameters["slow"])

    def on_bar(self):
        if self.ma_fast.crossed_above(self.ma_slow):
            self.order_market(self.data.close[0], 100)
        elif self.ma_fast.crossed_below(self.ma_slow):
            self.close_all()

# 运行回测
cerebro = Cerebro(
    cash=1_000_000,
    broker=BacktestBroker(),
    commission=AShareCommission(),
)

cerebro.add_data(DataFeed.baostock(
    symbols=["sh600519", "sz000858"],
    timeframe="1d",
    start="2020-01-01",
    end="2024-12-31",
))
cerebro.add_strategy(MyStrategy, fast=5, slow=20)
results = cerebro.run()

# 查看报告
cerebro.show_report(results)
```

### 使用 AI 生成策略

```python
from stockquant.ai import AIOrchestrator

ai = AIOrchestrator(
    llm_provider="openai",
    llm_model="gpt-4o",
    data_sources=["baostock", "eastmoney"],
)

# 自然语言 → 策略代码
strategy = ai.generate_strategy(
    "在日线级别，当 MACD 金叉且东方财富论坛情绪超过 70% 时买入，"
    "仓位不超过总资产的 20%，止损 5%"
)

# AI 自动回测 + 解读
results = cerebro.backtest(strategy)
analysis = ai.analyze_backtest(results)
print(analysis.summary)    # 自然语言总结
print(analysis.suggestions)  # 改进建议
```

---

## 架构概览

```
stockquant/
├── engine/          # 事件驱动引擎（Cerebro / EventEngine / OMS / Portfolio）
├── strategy/        # 策略框架（BaseStrategy / 模板库）
├── indicators/      # 技术指标（18+ 指标）
├── analytics/       # 分析报表（HTML/PDF/JSON 报表 + Plotly 可视化）
├── data/            # 数据层（DataFeed ABC + 本地缓存 + 多数据源）
├── execution/       # 交易执行（LiveBroker + 消息推送）
├── ai/              # AI 层（Agent 编排 / 信息处理全流程 / 记忆 / 反幻觉 / LLM 适配 / 爬虫 / NLP）
├── api/             # API 网关（FastAPI RESTful + WebSocket）
├── web/             # Web 前端（React + Ant Design + ECharts）
└── utils/           # 工具层（时间 / 日志 / 配置）
```

### 核心数据流

```
用户策略 → Cerebro → EventEngine → BarEvent → BaseStrategy.on_bar()
  → Broker.place_order() → RiskManager.check() → 撮合引擎 → 更新 Portfolio

DataAgent 采集新闻/公告 → NLP 情感分析 → MonitorAgent 实时监控
  → DecisionAgent 融合技术面+消息面 → 生成交易建议 → 推送用户
```

---

## 功能清单

### 传统量化能力（F001-F018）

| 模块 | 功能 | 状态 |
|------|------|------|
| **引擎** | 事件驱动回测引擎（F001） | Planned |
| **OMS** | 订单管理（5 种订单类型 + 状态机 + T+1）（F002） | Planned |
| **组合** | 多资产投资组合（F003） | Planned |
| **策略** | BaseStrategy 框架 + 生命周期钩子（F004） | Planned |
| **指标** | 30+ 回测统计指标 Sharpe/Sortino/Calmar（F005） | Planned |
| **Broker** | 回测/模拟/实盘抽象层（F006） | Planned |
| **费用** | A 股佣金/滑点/印花税建模（F007） | Planned |
| **优化** | 参数优化器（网格 + 随机 + Walk-Forward）（F008） | Planned |
| **风控** | 风险管理模块（F009） | Planned |
| **仓位** | 仓位管理 Kelly/ATR/波动率目标（F010） | Planned |
| **数据** | 数据层抽象 + 本地缓存（F011） | Planned |
| **模拟** | 模拟盘模式（F012） | Planned |
| **报表** | HTML/JSON 回测报表（F013） | Planned |
| **模板** | 7 套内置策略模板（F014） | Planned |
| **DSL** | 自定义指标装饰器（F015） | Planned |
| **Dashboard** | Web Dashboard（F029） | Planned |
| **实盘** | 券商 API（中泰 XTP / CTP）（F017） | Planned |
| **推送** | 钉钉/邮件/企微/Telegram 推送（F018） | Planned |

### AI 能力（F020-F028）

| Agent | 功能 | 状态 |
|-------|------|------|
| **DataAgent** | 多源数据采集 + 情感分析 + 结构化（F020） | Planned |
| **IndicatorAgent** | 自动推荐最优指标组合（F021） | Planned |
| **StrategyAgent** | 自然语言 → 策略代码（F022） | Planned |
| **BacktestAgent** | 自动解读回测结果 + 过拟合检测（F023） | Planned |
| **MonitorAgent** | 实时盯盘 + 异动检测（F024） | Planned |
| **DecisionAgent** | AI 辅助决策 + 风险预警（F025） | Planned |
| **RiskAgent** | 动态风控 + 黑天鹅防护（F026） | Planned |
| **对比 Agent** | 多策略横向对比 + 组合优化（F027） | Planned |
| **交互界面** | 对话式策略/数据/盯盘（F028） | Planned |

### 基础设施（F030）

| 模块 | 功能 | 状态 |
|------|------|------|
| **部署** | Docker Compose 一键部署（F030） | Planned |
| **测试** | pytest + CI/CD + 覆盖率 ≥ 90% | Planned |

---

## Web Dashboard

StockQuant 2.0 提供完整的 Web 前端，涵盖 10 个核心页面：

| 页面 | 路由 | 功能 |
|------|------|------|
| 主页仪表盘 | `/` | 权益曲线、持仓汇总、通知、系统状态 |
| 回测配置 | `/backtest` | 数据选择 + 策略配置 + 启动回测 |
| 回测结果 | `/backtest/:id` | 30+ 指标 + 资金曲线/回撤/热力图 + AI 解读 |
| 策略管理 | `/strategy` | 策略列表 + Monaco 代码编辑器 |
| 实时盯盘 | `/monitor` | 自选股 + 实时行情 + AI 信号推送 |
| AI 对话 | `/ai-chat` | 与 AI 对话：策略开发、数据分析 |
| 投资组合 | `/portfolio` | 持仓汇总 + 行业分布 + 盈亏分析 |
| 数据管理 | `/data` | 数据源配置 + 缓存管理 |
| 系统设置 | `/settings` | 运行配置中心（14 分组、向导/专家双模式） |
| 登录 | `/login` | 用户认证（未来） |

### 技术栈

| 层次 | 技术 |
|------|------|
| 前端框架 | React 18 + TypeScript + Vite |
| UI 组件 | Ant Design 5 |
| 图表 | ECharts 5 |
| 状态管理 | Zustand |
| 代码编辑 | Monaco Editor |
| 后端 API | FastAPI + Uvicorn + WebSocket |
| 部署 | Docker Compose + Nginx |

### 系统设置页

系统设置页参考成熟的配置管理体系，提供 14 个配置分组、70+ 参数项：

| 分组 | 参数项 | 说明 |
|------|--------|------|
| 系统总控 | 6 项 | 交易模式、日志级别、Web 端口、初始资金、强制运行、Tick 间隔 |
| 数据源 | 10 项 | 主数据源（BaoStock/Tushare/TDX/DuckDB/MySQL/PG）及连接参数 |
| 交易成本 | 4 项 | 佣金率、最低佣金、印花税率、过户费率 |
| 执行参数 | 3 项 | 滑点、最小手数、涨跌停限制 |
| 交易时段 | 4 项 | 早盘/午盘开收盘时间 |
| 券商通道 | 5 项 | 通道类型（内部/QMT/HTTP）、轮询间隔、QMT/HTTP 网关参数 |
| 风控阈值 | 5 项 | 单笔止损、单票仓位、总仓位、日亏熔断、回撤限制 |
| AI 模型 | 14 项 | LLM 提供商、API 地址/密钥、模型、温度、Token、超时、策略专用 LLM |
| 策略进化 | 10 项 | 进化开关、LLM 配置、重试、降级 |
| 通知推送 | 8 项 | 企微/钉钉/SMTP/邮箱/Telegram |
| 基本面适配 | 10 项 | 启用开关、回测/实时启用、缓存配置 |
| 信号管理 | 3 项 | 去重冷却、DB 兜底、审计拒单 |
| 历史同步 | 14 项 | 写入模式、定时间隔、并发、股票池 |
| 消息总线 | 3 项 | Kafka 开关、集群地址、消费者组 |

**UI 特性**：暗色科技感主题、向导/专家双视图、动态表单控件、条件显隐、密钥掩码、Dirty 追踪、浮动保存条、管理员口令二次确认。

---

## 配置说明

### AI 配置（YAML 驱动）

```yaml
# stockquant_config.yaml
ai:
  llm:
    provider: "openai"          # openai / anthropic / local
    model: "gpt-4o"
    api_key: "${AI_API_KEY}"    # 从环境变量读取
    temperature: 0.3
    max_tokens: 2048

  data_collection:
    enabled: true
    frequency: "5min"
    sources:
      - name: "eastmoney_news"
        type: "web_scraper"
        schedule: "*/5 * * * *"
      - name: "cls_news"
        type: "rss"

  nlp:
    sentiment_model: "clue/albert-base-chinese-sst"
    fallback_provider: "openai"

  decision_mode: "advisory"    # advisory / semi-auto / auto
```

---

## 里程碑

| 版本 | 时间 | 内容 |
|------|------|------|
| **v2.0.0-alpha** | 第 10 周 | 事件引擎 + OMS + 投资组合 + 策略基类 + 18 指标 + AI 数据采集 Agent |
| **v2.0.0-beta** | 第 18 周 | + 佣金/滑点 + 参数优化 + 风控 + 报表 + Broker 抽象 + AI 策略生成 + AI 辅助决策 + API 网关 |
| **v2.0.0-rc** | 第 24 周 | + 数据缓存 + 模拟盘 + AI 回测解读 + AI 盯盘 + 动态风控 + Web Dashboard Alpha + 测试 ≥ 90% |
| **v2.0.0** | 第 36 周 | + Web Dashboard 完整版 + AI 对话界面 + 券商 API + Docker 一键部署 |
| **v2.1.0** | 第 48 周 | 高级功能：多用户、Streamlit 高级分析、移动端适配 |

**总工期**：约 40-52 周（10-13 个月）

---

## 从 v1 迁移

StockQuant v1.x 已标记为 EOL（End of Life）。v2.0 采用全新 API，不再兼容 v1。

提供 `v1_compat` 模块，可包装 v1 风格策略在 v2 引擎中运行（有限支持，仅单标的日线回测）。

```python
# v1 写法（不再推荐）
from stockquant.quant import *
config.loads('config.json')
class Strategy:
    def __init__(self):
        self.trade = Trade(config_file="config.json")
        kline = Market.kline("sh600519", "1d")
        for i in range(10, len(kline)):
            bt.initialize(kline[:i+1])

# v2 写法（推荐）
from stockquant.strategy import BaseStrategy
from stockquant.engine import Cerebro

class MyStrategy(BaseStrategy):
    def on_bar(self):
        if self.is_last_bar():
            pass  # 不再需要手动迭代

cerebro = Cerebro()
cerebro.add_data(DataFeed.baostock("sh600519", "1d"))
cerebro.add_strategy(MyStrategy)
cerebro.run()
```

---

## 技术栈

| 类别 | 依赖 |
|------|------|
| **核心** | numpy, pandas, TA-Lib / pandas-ta, plotly |
| **API** | FastAPI, Uvicorn, Pydantic v2 |
| **前端** | React 18, Ant Design 5, ECharts 5, Zustand, Monaco Editor |
| **AI** | OpenAI, Anthropic Claude, ChromaDB, sentence-transformers |
| **数据** | BaoStock, Tushare, SQLAlchemy, PyArrow, DuckDB |
| **部署** | Docker, Docker Compose, Nginx |
| **测试** | pytest, coverage, Jest, Cypress |
| **开发** | ruff, mypy, black |

---

## 路线图

详见 [Product-Spec.md](Product-Spec.md)（产品需求文档，30 个功能需求完整规格）。

---

## 许可

MIT License

---

> **说明**：StockQuant 2.0 目前处于 Alpha 开发阶段，API 和功能尚未稳定。本文档描述的是目标架构，部分功能仍在实现中。当前版本（v1.2.0）可参考旧的 README 分支使用。
