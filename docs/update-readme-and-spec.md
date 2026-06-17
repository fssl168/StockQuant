# 计划：更新 README.md 和 Product-Spec.md

## 摘要

项目已完成 87% 功能（26/30），但两份核心文档仍停留在"规划阶段"状态，严重滞后于实际开发进度。需要全面更新以反映当前真实状态。

## 当前问题分析

### README.md 问题（共 10 项）

| # | 问题 | 严重程度 |
|---|------|---------|
| 1 | 所有功能状态标记为 "Planned"，实际 26/30 已完成（87%） | 严重 |
| 2 | 架构概览目录树过时：缺少 `agent/`、`persistence/`、`models/`；多了不存在的 `web/`、`utils/` | 严重 |
| 3 | 快速开始代码引用不存在的 API：`AIOrchestrator`、`DataFeed.baostock()`、`AShareCommission`、`cerebro.backtest()` | 严重 |
| 4 | AI 安装依赖错误：列了 `chromadb`、`sentence-transformers` 但 setup.py 中没有 | 中 |
| 5 | 安装步骤包含 `cd web && npm install` 但 web/ 目录不存在 | 中 |
| 6 | 技术栈表列了不存在的依赖：Tushare、DuckDB、Docker、Jest、Cypress、mypy、black | 中 |
| 7 | AI Agent 数量描述为"6 个"但实际已实现 5 个（Strategy/Decision/Backtest/Indicator/Risk），1 个未实现（Monitor） | 低 |
| 8 | Web Dashboard 10 页面描述但前端代码不存在，应标注为规划中 | 中 |
| 9 | 缺少 agent/ 基础设施层（ReActAgent、LLMAdapter、ToolRegistry）的介绍 | 中 |
| 10 | 核心数据流描述引用不存在的模块（DataAgent、NLP 情感分析） | 中 |

### Product-Spec.md 问题（共 8 项）

| # | 问题 | 严重程度 |
|---|------|---------|
| 1 | 文档状态标注 "Ready for Development"，实际已完成 87% | 严重 |
| 2 | F001-F018 传统量化功能无实现状态标注，全部看起来像规划 | 严重 |
| 3 | F020-F028 AI 功能无实现状态标注，5 个已实现的功能看起来像未开始 | 严重 |
| 4 | 测试套件数量过时（文档未提及实际 432+ tests） | 中 |
| 5 | 架构章节缺少 agent/ 基础设施层的描述 | 中 |
| 6 | 技术栈缺少实际依赖：litellm、tenacity、exchange-calendars、schedule、json-repair | 中 |
| 7 | 缺少对已实现模块的代码引用和实际类/方法名 | 低 |
| 8 | 风险与缓解章节未反映已解决的风险项 | 低 |

## 修改方案

### 一、README.md 更新

#### 1.1 功能状态表全面更新

将所有功能的状态从 "Planned" 更新为实际状态：

**传统量化（F001-F018）**：
| 功能 | 新状态 |
|------|--------|
| F001 事件驱动回测引擎 | ✅ Done |
| F002 订单管理系统 | ✅ Done |
| F003 投资组合模拟 | ✅ Done |
| F004 策略框架 | ✅ Done |
| F005 回测统计指标 | ✅ Done |
| F006 Broker 抽象层 | ✅ Done |
| F007 佣金与滑点建模 | ✅ Done |
| F008 参数优化器 | ✅ Done |
| F009 风险管理 | ✅ Done |
| F010 仓位管理 | ✅ Done |
| F011 数据层 | ✅ Done |
| F012 模拟盘模式 | ✅ Done |
| F013 报表 | ✅ Done |
| F014 策略模板 | ✅ Done |
| F015 自定义指标 DSL | ✅ Done |
| F016 Streamlit Dashboard | ❌ Not Started |
| F017 券商 API | ⚠️ Skeleton |
| F018 消息推送 | ✅ Done |

**AI 能力（F019-F028）**：
| 功能 | 新状态 |
|------|--------|
| F019 信号管线系统 | ✅ Done |
| F020 AI 信息处理全流程 | ⚠️ Partial（基础设施完成，记忆/反幻觉/爬虫未实现） |
| F021 指标发现 Agent | ✅ Done |
| F022 策略生成 Agent | ✅ Done |
| F023 回测解读 Agent | ✅ Done |
| F024 实时盯盘 Agent | ❌ Not Started |
| F025 辅助决策 Agent | ✅ Done |
| F026 动态风控 Agent | ✅ Done |
| F027 策略对比 Agent | ❌ Not Started |
| F028 交互界面 | ❌ Not Started |

**基础设施（F029-F030）**：
| 功能 | 新状态 |
|------|--------|
| F029 Web Dashboard | ⚠️ Partial（API 后端完成，前端未实现） |
| F030 Docker 部署 | ❌ Not Started |

#### 1.2 架构概览目录树更新

替换为实际目录结构：
```
stockquant/
├── engine/          # 事件驱动引擎（Cerebro / EventEngine / OMS / Portfolio）
├── strategy/        # 策略框架（BaseStrategy / 模板库 / 信号管线 / YAML 加载）
├── indicators/      # 技术指标（18+ 指标 + DSL 装饰器）
├── data/            # 数据层（5 数据源 + 标准化 + 交易日历 + 故障切换）
├── models/          # 数据模型（Bar / Order / Position / Account / Trade / Portfolio）
├── agent/           # Agent 基础设施（LLMAdapter / ReActAgent / ToolRegistry）
├── ai/              # AI Agent（5 Agent + JSON 修复 + 新闻搜索）
├── analytics/       # 分析报表（HTML/JSON 报表 + 市场复盘）
├── execution/       # 交易执行（9 通知渠道 + 消息路由 + Markdown 渲染）
├── persistence/     # 持久化（SQLAlchemy ORM + 5 数据表）
├── api/             # API 网关（FastAPI RESTful + WebSocket）
└── scheduler.py     # 定时调度器
```

#### 1.3 快速开始代码修正

- 修正回测示例：使用实际存在的 API（`BacktestBroker`、`CommissionInfo`）
- 修正 AI 示例：使用 `StrategyAgent` 替代不存在的 `AIOrchestrator`
- 移除 `cd web && npm install` 步骤
- 修正安装依赖列表与 setup.py 一致

#### 1.4 技术栈表更新

与 setup.py 保持一致：
- 核心：numpy, pandas, matplotlib, jinja2, tenacity, exchange-calendars, schedule, pyyaml, markdown, Pillow
- 可选指标：TA-Lib / pandas-ta, plotly
- AI：openai, anthropic, litellm, httpx, json-repair
- Web API：FastAPI, Uvicorn, Pydantic v2
- 数据：BaoStock, PyArrow
- 测试：pytest, ruff, coverage
- 移除不存在的：chromadb, sentence-transformers, Tushare, DuckDB, Docker, Jest, Cypress, mypy, black

#### 1.5 Web Dashboard 章节标注

在 Web Dashboard 章节开头添加状态说明：前端部分为规划中，API 后端已实现。

#### 1.6 核心数据流更新

替换为实际实现的数据流，移除不存在的 DataAgent/NLP 引用。

#### 1.7 补充 Agent 基础设施介绍

新增 agent/ 层的简要介绍：LLMAdapter、ReActAgent、ToolRegistry。

### 二、Product-Spec.md 更新

#### 2.1 文档状态更新

- 状态从 "Ready for Development" 更新为 "In Development (87% Complete)"
- 更新日期改为当前日期

#### 2.2 每个功能需求添加实现状态标注

在 F001-F030 每个功能章节的标题行添加状态标签：

格式：`### F001 事件驱动回测引擎 [✅ Done]`

状态分类：
- `[✅ Done]` — 已完成（22 个）
- `[⚠️ Partial]` — 部分完成（3 个：F017, F020, F029）
- `[❌ Planned]` — 未开始（5 个：F016, F024, F027, F028, F030）

#### 2.3 已完成功能补充实际实现说明

在每个已完成功能的验收标准之后，添加"实际实现"小节，说明：
- 实际实现的类/方法名
- 关键文件路径
- 与规格的差异（如有）

#### 2.4 架构章节更新

- 5.1 包结构：添加 `agent/`、`persistence/`、`models/` 的描述
- 5.2-5.3：标注 API 网关已实现，Web 前端为规划中

#### 2.5 技术栈章节更新

- 添加实际依赖：litellm, tenacity, exchange-calendars, schedule, json-repair, Pillow, markdown
- 移除不存在的依赖

#### 2.6 测试策略章节更新

- 更新测试数量：432+ passed
- 更新覆盖率目标现状

#### 2.7 风险与缓解章节更新

- 标注已解决的风险项

## 文件修改清单

| 文件 | 修改类型 | 修改量 |
|------|---------|--------|
| `README.md` | 全面重写 | 大（约 80% 内容需更新） |
| `Product-Spec.md` | 增量更新 | 中（添加状态标注 + 补充实现说明） |

## 假设与决策

1. **功能完成度以 dsa-sq-comparison-evaluation.md 的 26/30 (87%) 为准**，这是最新的评估
2. **README.md 采用全面重写方式**，因为过时内容太多，逐行修改不如重写清晰
3. **Product-Spec.md 采用增量更新方式**，在现有结构上添加状态标注，不改变文档结构
4. **代码示例使用实际可运行的 API**，基于 `__init__.py` 导出的公共接口
5. **Web Dashboard 前端部分保留描述但标注为规划中**，因为 Product-Spec 中已有完整设计
6. **不修改 Product-Spec-CHANGELOG.md**，变更记录应追加而非修改

## 验证步骤

1. 检查 README.md 中所有代码示例引用的类/方法是否在 `__init__.py` 中导出
2. 检查功能状态标注是否与实际代码文件一致
3. 检查技术栈表是否与 `setup.py` 一致
4. 检查目录结构是否与实际文件系统一致
5. 检查 Product-Spec.md 状态标注的完成数（22 Done + 3 Partial + 5 Planned = 30）是否正确
