# 借鉴 daily_stock_analysis 项目 — 实施计划

## 概要

对比分析 `D:\projects\daily_stock_analysis`（简称 DSA）与当前 StockQuant v2 项目，识别可借鉴的功能、架构设计和依赖，为 StockQuant v2 的下一步开发提供方向。

---

## 〇、两者能力全景对比

### 0.1 项目定位对比

| 维度 | DSA (daily_stock_analysis) | StockQuant v2 |
|------|---------------------------|---------------|
| **定位** | 股票智能分析应用（SaaS/工具） | 机构级量化交易框架（SDK/库） |
| **目标用户** | 个人投资者、非程序员 | 量化开发者、机构团队 |
| **使用方式** | 部署运行，配置即用 | `import stockquant`，编程调用 |
| **核心价值** | 每日自动分析 + AI 决策推送 | 事件驱动回测 + 策略研发 + 实盘执行 |
| **扩展方式** | 修改 .env / YAML 策略 | 编写 BaseStrategy 子类 |
| **部署形态** | Web 服务 / Docker / GitHub Actions / 桌面端 | Python 库 pip install |

### 0.2 核心能力矩阵

| 能力维度 | DSA | StockQuant v2 | 对比说明 |
|----------|-----|---------------|----------|
| **回测引擎** | ★★☆ 简单日线 Long-only 回测，胜率/收益率评估 | ★★★★ 事件驱动引擎，30+ 指标，5 种仓位管理，3 种滑点模型 | **SQ 远超 DSA** — SQ 是专业回测框架，DSA 仅做历史验证 |
| **技术指标** | ★★☆ MA/MACD/RSI/乖离率/量能，100分制评分 | ★★★★ 18+ 指标纯 numpy 实现，IndicatorProxy 交叉判断，DSL 装饰器 | **SQ 远超 DSA** — SQ 指标库更专业更丰富 |
| **策略框架** | ★★☆ 11 个 YAML 策略，无需写代码 | ★★★★ BaseStrategy 生命周期钩子，7 套内置模板，Signal 系统 | **SQ 更专业** — 但 DSA 的 YAML 零代码策略更易上手 |
| **数据源** | ★★★★ 6 源自动故障切换，实时行情多源补充 | ★★☆ 仅 BaoStockFeed + CSVFeed | **DSA 远超 SQ** — 多源切换是生产必备能力 |
| **AI 能力** | ★★★★ LiteLLM 统一调用，ReAct Agent，多 Key 负载均衡 | ★☆☆ BacktestAgent 仅规则引擎，未接入 LLM（**记忆系统+反幻觉仅在 Spec 中规划，未实现**） | **DSA 远超 SQ** — DSA 是 AI-Native，SQ 的 AI 是空壳 |
| **通知推送** | ★★★★ 10+ 渠道，Mixin 组合，Markdown 转图片，消息分批 | ★★☆ 4 种通知器，3 个未继承基类 | **DSA 远超 SQ** — 渠道数量和质量差距大 |
| **数据持久化** | ★★★ SQLite + SQLAlchemy ORM | ☆☆☆ 纯内存，无持久化 | **DSA 远超 SQ** — SQ 回测结果无法保存 |
| **定时调度** | ★★★ schedule + 交易日检查 + 优雅退出 | ☆☆☆ 无 | **DSA 独有** — SQ 无自动化运行能力 |
| **交易日历** | ★★★ exchange-calendars 库 | ☆☆☆ 无，T+1 释放逻辑有 bug | **DSA 独有** — SQ 缺少交易日判断 |
| **大盘分析** | ★★★ 三段式复盘（指数/资金/板块），AI 增强 | ☆☆☆ 无 | **DSA 独有** — SQ 无市场整体视角 |
| **风控系统** | ★☆☆ 无 | ★★★★ 7 层风控检查 + 全局熔断 | **SQ 远超 DSA** — SQ 有完整风控框架 |
| **仓位管理** | ☆☆☆ 无 | ★★★★ 5 种 PositionSizer（固定/凯利/ATR/波动率/等权） | **SQ 独有** — DSA 无仓位管理概念 |
| **订单管理** | ☆☆☆ 无 | ★★★★ 完整 OMS，5 种订单类型，7 种状态，部分成交 | **SQ 独有** — DSA 无订单生命周期 |
| **投资组合** | ☆☆☆ 单标的 Long-only | ★★★ Portfolio 多资产多空双向，T+1 冻结 | **SQ 独有** — DSA 无组合管理 |
| **佣金/滑点** | ☆☆☆ 无 | ★★★★ A 股完整费用模型 + 3 种滑点 | **SQ 独有** — DSA 无交易成本建模 |
| **参数优化** | ☆☆☆ 无 | ★★★ 网格/随机/Walk-Forward 三种优化 | **SQ 独有** — DSA 无参数寻优 |
| **Web API** | ★★★★ FastAPI 完整 REST + 认证 + WebSocket | ★★☆ FastAPI 骨架，无认证，WebSocket 仅心跳 | **DSA 远超 SQ** — DSA API 生产就绪 |
| **前端界面** | ★★★★ React + Vite + Tailwind + Electron | ☆☆☆ 无 | **DSA 独有** — SQ 是纯后端库 |
| **Bot 集成** | ★★★ 钉钉/飞书/Discord Stream 模式 | ☆☆☆ 无 | **DSA 独有** — SQ 无聊天机器人 |
| **搜索/情报** | ★★★ Tavily/SerpAPI/Bocha/Brave 4 搜索引擎 | ☆☆☆ 无 | **DSA 独有** — SQ 无新闻/舆情能力 |
| **AI 记忆系统** | ☆☆☆ 无 | ☆☆☆ Product-Spec 规划了 L1/L2/L3 三级记忆，但**未实现** | **SQ 独有规划** — DSA 无记忆架构，SQ 规划完整但待实现 |
| **AI 反幻觉** | ☆☆☆ 无 | ☆☆☆ Product-Spec 规划了五步纠正+幻觉数据库，但**未实现** | **SQ 独有规划** — DSA 无反幻觉机制，SQ 规划完整但待实现 |
| **CI/CD** | ★★★★ 9 个 GitHub Actions 工作流 | ☆☆☆ 无 | **DSA 独有** — 但 SQ 作为库不需要复杂 CI |
| **测试覆盖** | ★★★ 22 个测试文件 | ☆☆☆ tests/ 目录为空 | **DSA 远超 SQ** — SQ 无任何测试 |

### 0.3 能力雷达图（5分制）

| 维度 | DSA | SQ | 说明 |
|------|-----|-----|------|
| 回测深度 | 2 | 5 | SQ 事件驱动回测远超 DSA 简单验证 |
| 指标丰富度 | 2 | 4 | SQ 18+ 指标，DSA 仅 6 种基础指标 |
| 策略专业度 | 2 | 4 | SQ 有完整策略框架，DSA 仅 YAML 配置 |
| 数据源可靠性 | 5 | 2 | DSA 6 源切换，SQ 单源脆弱 |
| AI 智能 | 5 | 1 | DSA AI-Native，SQ AI 空壳 |
| 通知能力 | 5 | 2 | DSA 10+ 渠道，SQ 4 种且 3 个有 bug |
| 持久化 | 3 | 0 | DSA 有 SQLite，SQ 无任何持久化 |
| 风控能力 | 0 | 5 | SQ 7 层风控，DSA 无风控 |
| 交易执行 | 0 | 4 | SQ 完整 OMS + 仓位管理，DSA 无交易能力 |
| 易用性 | 5 | 2 | DSA 配置即用，SQ 需编程 |
| AI 记忆系统 | 0 | 0 | DSA 无规划，SQ 有完整 L1/L2/L3 规划但未实现 |
| AI 反幻觉 | 0 | 0 | DSA 无规划，SQ 有五步纠正+幻觉数据库规划但未实现 |
| **总分** | **34** | **29** | 各有所长，互补性强 |

### 0.4 互补关系总结

```
                    DSA 擅长                          SQ 擅长
            ┌─────────────────────┐          ┌─────────────────────┐
            │  多源数据获取        │          │  事件驱动回测        │
            │  AI 驱动分析         │          │  技术指标计算        │
            │  多渠道通知推送      │          │  风控系统            │
            │  数据持久化          │          │  仓位管理            │
            │  定时调度            │          │  订单管理 OMS        │
            │  情报搜索            │          │  投资组合管理        │
            │  易用性（零代码）    │          │  佣金/滑点建模       │
            │  Web/Bot 前端        │          │  参数优化            │
            └─────────────────────┘          └─────────────────────┘
                         ↓                            ↓
                    ┌───────────────────────────────────────┐
                    │       借鉴 DSA 补全 SQ 短板：         │
                    │  多源切换 + AI + 持久化 + 通知 + 调度  │
                    │       = 完整的量化交易平台              │
                    └───────────────────────────────────────┘
```

---

## 一、可借鉴功能对比

| 借鉴方向 | DSA 实现 | StockQuant 现状 | 优先级 |
|----------|----------|----------------|--------|
| 多数据源自动故障切换 | DataFetcherManager 6源优先级切换 | 仅 BaoStockFeed 单源 | **高** |
| AI 驱动分析（LiteLLM） | LiteLLM 统一调用 Gemini/Anthropic/OpenAI/DeepSeek | BacktestAgent 仅规则引擎，未接入 LLM | **高** |
| ReAct Agent 智能体 | AgentExecutor + ToolRegistry + 11种策略 | 无 Agent 实现 | **高** |
| 交易日历 | exchange-calendars 库 | 无，T+1 释放逻辑粗糙 | **高** |
| 策略 YAML 配置 | 11 个 YAML 策略文件，无需写代码 | 策略必须写 Python 类 | **中** |
| 多渠道通知（10+） | 企微/飞书/Telegram/邮件/Discord/PushPlus 等 | 仅钉钉/企微/邮件/Telegram 4种 | **中** |
| SQLite + ORM 持久化 | SQLAlchemy ORM 存储分析历史/回测结果 | 纯内存，无持久化 | **中** |
| 定时调度 | schedule 库 + 交易日检查 | 无定时调度 | **中** |
| 大盘复盘 | 三段式复盘策略（指数/资金/板块） | 无 | **中** |
| Markdown 转图片 | md2img + imgkit | 无 | **低** |
| 消息分批/路由 | 按渠道自动分批，按股票路由到不同邮箱 | 无 | **低** |
| 图片识别提股 | Vision LLM 从截图提取股票代码 | 无 | **低** |
| Web 前端 | React + Vite + Tailwind | 无前端 | **低** |
| 桌面客户端 | Electron | 无 | **低** |
| CI/CD | 9 个 GitHub Actions 工作流 | 无 | **低** |

---

## 二、架构设计借鉴

### 2.1 数据源层：多源策略 + 自动故障切换（高优先级）

**DSA 方案**：`DataFetcherManager` 管理多个 `BaseFetcher`，按优先级排序，主源失败自动切换次源。

```
EfinanceFetcher(P0) > AkshareFetcher(P1) > TushareFetcher(P2) > PytdxFetcher(P2) > BaostockFetcher(P3) > YfinanceFetcher(P4)
```

**StockQuant 借鉴方案**：

- 重构 `stockquant/data/feed.py` 中的 `DataFeed` 体系
- 新增 `DataFeedManager` 类，管理多个 `DataFeed` 实例
- 新增 `AkShareFeed`、`EfinanceFeed`、`PytdxFeed`、`YFinanceFeed` 数据源
- 实现按优先级自动故障切换逻辑
- 实时行情支持多源补充（主源缺字段时从次源补充）

**涉及文件**：
- `stockquant/data/feed.py` — 新增 `DataFeedManager`
- `stockquant/data/providers/` — 新增 `akshare_feed.py`、`efinance_feed.py`、`pytdx_feed.py`、`yfinance_feed.py`

### 2.2 AI 模块：LiteLLM 统一调用（高优先级）

**DSA 方案**：通过 `litellm` 库统一调用 Gemini/Anthropic/OpenAI/DeepSeek，支持多 Key 负载均衡和跨模型 Fallback。

**StockQuant 借鉴方案**：

- 重构 `stockquant/ai/backtest_agent.py`，接入 LiteLLM
- 新增 `LLMConfig` 配置类（模型选择、API Key、Fallback 链）
- BacktestAgent 支持两种模式：规则驱动（当前）+ LLM 驱动（新增）
- 新增 AI 信号生成能力（SignalSource.AI_MONITOR/AI_DECISION 的真正实现）

**涉及文件**：
- `stockquant/ai/backtest_agent.py` — 重构，接入 LiteLLM
- `stockquant/ai/llm_config.py` — 新增 LLM 配置
- `stockquant/ai/signal_agent.py` — 新增 AI 信号 Agent

### 2.3 Agent 智能体：ReAct 模式（高优先级）

**DSA 方案**：`AgentExecutor` 实现 ReAct 循环（推理-行动-观察），通过 `ToolRegistry` 注册工具，支持多步推理。

**StockQuant 借鉴方案**：

- 新增 `stockquant/agent/` 包
- 实现 `ReActExecutor`（ReAct 循环 + 最大步数限制）
- 实现 `ToolRegistry`（工具注册表）
- 实现内置工具集：`DataTools`（行情数据）、`IndicatorTools`（技术指标）、`BacktestTools`（回测触发）、`SearchTools`（情报搜索）
- 与现有 `BaseStrategy` 和 `SignalManager` 集成

**涉及文件**：
- `stockquant/agent/__init__.py` — 新增
- `stockquant/agent/executor.py` — ReAct 执行器
- `stockquant/agent/tools.py` — 工具注册表 + 内置工具
- `stockquant/agent/conversation.py` — 会话管理

### 2.4 交易日历（高优先级）

**DSA 方案**：使用 `exchange-calendars` 库判断交易日，非交易日自动跳过。

**StockQuant 借鉴方案**：

- 新增 `stockquant/data/trading_calendar.py`
- 封装 `exchange-calendars` 库，提供 A股/港股/美股交易日查询
- 修复 Cerebro 中 T+1 释放逻辑：按实际交易日切换而非每 5 根 Bar

**涉及文件**：
- `stockquant/data/trading_calendar.py` — 新增交易日历模块
- `stockquant/engine/cerebro.py` — 修复 T+1 释放逻辑

### 2.5 策略 YAML 配置（中优先级）

**DSA 方案**：11 个 YAML 策略文件，定义指标参数、买卖条件、风控规则，无需写代码即可添加新策略。

**StockQuant 借鉴方案**：

- 新增 `stockquant/strategy/yaml_loader.py`
- 支持 YAML 文件定义策略（指标参数、信号条件、仓位规则）
- YAML 策略自动转换为 `BaseStrategy` 子类实例
- 约定 YAML schema：`indicators`、`entry_signal`、`exit_signal`、`risk_rules`、`position_sizing`

**涉及文件**：
- `stockquant/strategy/yaml_loader.py` — 新增 YAML 策略加载器

### 2.6 通知渠道扩展（中优先级）

**DSA 方案**：10+ 通知渠道，Mixin 模式组合，Markdown 转图片，消息自动分批。

**StockQuant 借鉴方案**：

- 新增 `PushPlusNotifier`、`ServerChanNotifier`、`DiscordNotifier`、`LarkNotifier`（飞书）
- 修复现有通知器继承关系（3 个未继承 Notifier 基类）
- 新增消息分批逻辑（按渠道限制自动拆分）
- 新增 Markdown 转图片能力（对不支持 Markdown 的渠道）

**涉及文件**：
- `stockquant/execution/notifier/` — 新增多个通知器 + 修复继承

### 2.7 数据持久化（中优先级）

**DSA 方案**：SQLite + SQLAlchemy ORM，存储分析历史、回测结果、日线行情。

**StockQuant 借鉴方案**：

- 新增 `stockquant/data/storage.py`
- 使用 SQLAlchemy ORM 定义数据模型：`KlineData`、`BacktestResult`、`AnalysisHistory`
- SQLite 作为默认存储，可扩展 PostgreSQL
- Cerebro 回测完成后自动保存结果

**涉及文件**：
- `stockquant/data/storage.py` — 新增 ORM 存储层

### 2.8 定时调度（中优先级）

**DSA 方案**：`schedule` 库 + 交易日检查 + 优雅退出。

**StockQuant 借鉴方案**：

- 新增 `stockquant/execution/scheduler.py`
- 支持每日定时执行策略/回测
- 集成交易日历，非交易日自动跳过
- 信号捕获实现优雅退出

**涉及文件**：
- `stockquant/execution/scheduler.py` — 新增调度器

---

## 三、依赖借鉴

### 3.1 建议新增到 `install_requires`

| 依赖 | 版本 | 用途 | 来源 |
|------|------|------|------|
| `tenacity>=8.0` | — | 指数退避重试（数据源切换、API 调用） | DSA requirements.txt |
| `python-dotenv>=1.0` | — | .env 环境变量加载 | DSA requirements.txt |

### 3.2 建议新增到 `extras_require`

| 依赖组 | 依赖 | 用途 | 来源 |
|--------|------|------|------|
| `ai` | `litellm>=1.0` | 统一 LLM 调用（替代直接 openai/anthropic） | DSA requirements.txt |
| `data` | `akshare>=1.10` | AkShare 数据源 | DSA requirements.txt |
| `data` | `efinance>=0.5` | Efinance 数据源 | DSA requirements.txt |
| `data` | `pytdx>=1.7` | 通达信数据源 | DSA requirements.txt |
| `data` | `yfinance>=0.2` | 美股数据源 | DSA requirements.txt |
| `data` | `exchange-calendars>=4.0` | 交易日历 | DSA requirements.txt |
| `storage` | `sqlalchemy>=2.0` | ORM 持久化 | DSA requirements.txt |
| `scheduler` | `schedule>=1.1` | 定时调度 | DSA requirements.txt |
| `notify` | `lark-oapi>=1.0` | 飞书通知 | DSA requirements.txt |
| `notify` | `discord.py>=2.0` | Discord 通知 | DSA requirements.txt |
| `search` | `tavily-python>=0.3` | 新闻搜索 | DSA requirements.txt |
| `notify` | `imgkit>=1.0` | Markdown 转图片 | DSA requirements.txt |

### 3.3 建议调整现有依赖

| 当前 | 调整 | 原因 |
|------|------|------|
| `extras_require.ai`: `openai>=1.0, anthropic>=0.18, httpx>=0.25` | 改为 `litellm>=1.0` | LiteLLM 统一封装了 OpenAI/Anthropic，且支持多 Key 负载均衡和 Fallback |
| `extras_require.web`: `fastapi>=0.100, uvicorn>=0.20, pydantic>=2.0` | 保持不变 | 合理 |
| `extras_require.pyarrow`: `pyarrow>=12.0` | 移入 `storage` 组 | 与 SQLAlchemy 同属持久化 |

---

## 四、不建议借鉴的部分

| DSA 功能 | 不借鉴原因 |
|----------|-----------|
| React 前端 | StockQuant 定位为量化框架库，非应用产品；前端应由使用者自行搭建 |
| Electron 桌面端 | 同上 |
| 9 个 CI/CD 工作流 | 过度工程化，StockQuant 是库不是 SaaS |
| Vision AI 图片提股 | 非量化框架核心功能 |
| Bot 平台（钉钉/飞书 Stream） | 属于应用层集成，非框架核心 |
| GitHub Actions 定时执行 | 部署方式，非框架功能 |
| newspaper3k 网页提取 | 非量化框架核心功能 |

---

## 五、实施优先级建议

### 第一批（高优先级，核心能力补全）

1. **多数据源自动故障切换** — 解决单源不可用问题
2. **交易日历** — 修复 T+1 逻辑，支持交易日判断
3. **AI 接入 LiteLLM** — 让 BacktestAgent 真正具备 AI 能力
4. **ReAct Agent** — 实现智能策略问股

### 第二批（中优先级，体验提升）

5. **策略 YAML 配置** — 降低策略编写门槛
6. **通知渠道扩展 + 修复继承** — 提升通知能力
7. **数据持久化（SQLAlchemy）** — 回测结果/行情数据持久化
8. **定时调度** — 支持自动化运行

### 第三批（低优先级，锦上添花）

9. 大盘复盘模块
10. Markdown 转图片
11. 消息分批/路由

---

## 六、验证步骤

每个借鉴功能实施后需验证：

1. 新增模块可正常导入：`from stockquant.data import DataFeedManager`
2. 现有 v2 API 不受影响：`from stockquant import Cerebro, BaseStrategy`
3. 新增依赖仅在 `extras_require` 中声明，核心安装不受影响
4. `pip install -e .` 成功
5. `pip install -e ".[ai,data,storage]"` 成功安装可选依赖
