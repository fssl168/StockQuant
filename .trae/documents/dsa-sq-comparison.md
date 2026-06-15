# DSA vs StockQuant v2 对比分析报告

## 一、DSA 核心能力总结

DSA（Daily Stock Analysis）是一个 AI 驱动的股票智能分析系统，核心能力：

### 已实现
- **6 源数据自动故障切换**（Efinance → AkShare → Tushare → Pytdx → BaoStock → YFinance）
- **LiteLLM 统一 LLM 调用**（Gemini/Anthropic/OpenAI/DeepSeek，多 Key 负载均衡 + 跨模型 Fallback）
- **ReAct Agent**（ToolRegistry + AgentExecutor + Tool 注册表）
- **技术面分析**（MA5/10/20/60, MACD, RSI, 乖离率, 量能, 100 分制评分）
- **5 维新闻情报搜索**（Bocha/Tavily/Brave/SerpAPI 多引擎）
- **决策仪表盘**（JSON 格式：核心结论 + 数据视角 + 情报 + 作战计划 + 狙击点）
- **10+ 通知渠道**（企微/飞书/Telegram/邮件/Discord/Pushover/PushPlus/Server酱/Webhook/ASTRBot）
- **SQLite + SQLAlchemy ORM 持久化**（日线行情/分析历史/回测结果/对话记录）
- **交易日历**（exchange-calendars，CN/HK/US）
- **11 个 YAML 策略**（零代码策略定义）
- **定时调度**（schedule + 交易日检查）
- **大盘复盘**（指数/板块/资金/新闻）
- **Markdown 转图片**（imgkit + wkhtmltopdf）

### 未实现（DSA 短板）
- ❌ 无事件驱动回测引擎
- ❌ 无完整风控系统
- ❌ 无仓位管理
- ❌ 无订单管理（OMS）
- ❌ 无投资组合管理
- ❌ 无佣金/滑点建模
- ❌ 无参数优化

---

## 二、StockQuant v2 当前状态（250 tests, 26/30 功能完成）

### 已远超 DSA 的能力
- ✅ **事件驱动回测引擎**（Cerebro + EventEngine + ProgressBar）
- ✅ **18+ 技术指标**（纯 numpy 实现，IndicatorProxy 交叉判断）
- ✅ **完整风控系统**（7 层风控检查 + 全局熔断 + 动态风控 Agent）
- ✅ **5 种仓位管理**（FixedFraction/Kelly/ATR/波动率/等权）
- ✅ **完整 OMS**（5 种订单类型 + 7 种状态 + T+1 冻结）
- ✅ **投资组合管理**（多资产 + 多空双向）
- ✅ **A 股佣金/滑点建模**（完整费用模型）
- ✅ **参数优化**（网格/随机/Walk-Forward）
- ✅ **30+ 回测统计指标**
- ✅ **信号管线**（F019 已实现，含 A 股规则校验）
- ✅ **API Gateway**（FastAPI + WebSocket）
- ✅ **指标发现 Agent**（F021，市场状态检测 + 推荐 + 评分）
- ✅ **动态风控 Agent**（F026，环境检测 + 参数动态调整）

### 落后于 DSA 的能力
- ❌ **数据源**：仅 4 种（BaoStock/CSV/Parquet/SQLite），无网络 API 数据源，无自动故障切换
- ❌ **AI/LLM**：BacktestAgent 仅规则引擎，未接入任何 LLM
- ❌ **Agent 系统**：完全未实现
- ❌ **持久化**：纯内存，回测结果/行情数据无法保存
- ❌ **通知渠道**：仅 4 种，缺失 6+ 种，无报告生成
- ❌ **交易日历**：无，T+1 逻辑有简化 bug（每 5 根 Bar 解锁而非按交易日）
- ❌ **定时调度**：无
- ❌ **大盘复盘**：无
- ❌ **YAML 策略**：无，策略必须写 Python 类

---

## 三、borrow-from-dsa.md 计划复核

### 正确的判断 ✅

| 判断 | 准确性 | 说明 |
|------|--------|------|
| 数据源单点脆弱，需多源切换 | ✅ 完全正确 | SQ 仅 BaoStock/CSV/Parquet/SQLite，无网络 API 数据源 |
| AI 模块未接入 LLM | ✅ 完全正确 | BacktestAgent/IndicatorAgent/RiskAgent 全是纯规则引擎 |
| Agent 系统完全缺失 | ✅ 完全正确 | SQ 无任何 Agent 实现 |
| 交易日历缺失 | ✅ 完全正确 | SQ 的 T+1 每 5 根 Bar 解锁，非交易日判断 |
| 通知渠道仅 4 种 | ✅ 部分正确 | 实际 4 种 + AI 推送方法已添加，但缺失报告生成和 6+ 渠道 |
| 持久化完全缺失 | ✅ 完全正确 | SQ 纯内存 |
| 定时调度缺失 | ✅ 正确 | SQ 无自动化运行能力 |

### 遗漏的借鉴方向 ⚠️

#### 1. **JSON 响应修复机制（高优先级）**
DSA 使用 `json_repair` 库修复 LLM 输出的 malformed JSON（trailing commas, True/False → true/false, markdown code block 提取）。这是生产级 LLM 集成的**必备能力**。borrow-from-dsa.md 完全没有提及。

#### 2. **LLM Tool Calling 能力（高优先级）**
DSA 的 `LLMToolAdapter.call_with_tools()` 支持模型原生工具调用（function calling），不是简单的 prompt injection。这使得 Agent 能够：
- 动态选择工具
- 并行执行工具调用
- 根据工具返回结果进行多轮推理
- `to_openai_tools()` 自动生成 OpenAI 工具定义

这是 ReAct Agent 的**核心基础设施**，borrow-from-dsa.md 提及了 AgentExecutor 但遗漏了工具调用的重要性。

#### 3. **回测评价引擎（中优先级 — 互补而非重复）**
DSA 的 `BacktestEngine` 评估的是 **AI 分析预测准确性**（买入/卖出后 N 天方向正确率、止盈止损触发率），这与 SQ 的 `BacktestMetrics`（交易执行性能 30+ 指标）**互补**。SQ 已有交易级回测，但缺少 AI 信号级评价。borrow-from-dsa.md 提到了"AI 驱动分析"但没明确区分这两种回测的差异。

#### 4. **Markdown 转图片 + 消息分块（中优先级）**
DSA 的 `md2img.py`（imgkit/wkhtmltopdf）和消息分块发送是通知系统的**生产必备**。borrow-from-dsa.md 只提了 "Markdown 转图片" 为低优先级，但对于生产环境这是必要的。

#### 5. **数据标准化列模式（高优先级）**
DSA 的 `STANDARD_COLUMNS`（date, open, high, low, close, volume, amount, pct_chg）和自动计算 MA5/MA10/MA20 + volume_ratio，这是一个**极佳的统一数据格式抽象**。borrow-from-dsa.md 提到了列规范化但没具体说明可以统一 SQ 所有数据源的输出格式。

#### 6. **异常层次体系（高优先级）**
DSA 的异常层次：`DataFetchError → RateLimitError, DataSourceUnavailableError`，配合 `tenacity` 的指数退避重试。SQ 目前只有简单的 `raise ValueError`。borrow-from-dsa.md 完全遗漏了异常处理和重试机制。

#### 7. **信号级回测评价（中优先级）**
DSA 能评估 AI 建议的历史准确率（方向胜率、止盈止损触发率、每类建议的胜率 breakdown）。这可以作为 SQ 的 `SignalManager` 的补充：评估信号管线产生的信号的准确度。borrow-from-dsa.md 未提及。

#### 8. **报告文件保存（低优先级）**
DSA 自动生成 `reports/report_YYYYMMDD.md` 文件。SQ 的 ReportGenerator 只生成 HTML/JSON/Console，无文件保存。borrow-from-dsa.md 未提及。

### 需要修正的判断 ❌

| borrow-from-dsa.md 判断 | 问题 | 修正 |
|-------------------------|------|------|
| "通知器 3 个未继承基类" | **已过时** — 上一轮已修复，所有 notifier 现在都正确继承 Notifier ABC | 通知继承问题已解决 |
| "测试覆盖 DSA 远超 SQ" | **已过时** — SQ 已有 250 tests, 0 failed，DSA 仅约 40+ tests | 测试差距已大幅缩小 |
| "SQLAlchemy 需新增到 install_requires" | SQLAlchemy 应作为可选依赖（extras_require.storage），不是核心依赖 | borrow-from-dsa.md 的依赖建议方向正确 |
| "OpenAI/Anthropic 直接调用应改为 LiteLLM" | LiteLLM 是统一封装，但某些场景可能不需要（如纯规则引擎） | 建议保留两种模式，而非强制替换 |
| "Vision AI 图片提股不建议借鉴" | 部分同意 — 但对非程序员用户可能是有用功能 | 可作为 Web Dashboard 的未来功能 |

### 优先级调整建议

| 当前优先级 | borrow-from-dsa.md 建议 | 实际优先级（基于完整分析） |
|-----------|------------------------|--------------------------|
| **高** | 多数据源故障切换 | ✅ 高（正确）|
| **高** | 交易日历 | ✅ 高（正确）|
| **高** | AI 接入 LiteLLM | ✅ 高（正确）|
| **高** | ReAct Agent | ✅ 高（正确）|
| **中** | 策略 YAML 配置 | ⬆️ 中高（Agent 必需）|
| **中** | 通知渠道扩展 | ✅ 中（正确）|
| **中** | 数据持久化 | ✅ 中（正确）|
| **中** | 定时调度 | ✅ 中（正确）|
| **低** | Markdown 转图片 | ⬆️ 中（生产必备）|
| **遗漏** | JSON 响应修复 | ⬆️ **高（AI 集成必备）** |
| **遗漏** | 异常处理 + 重试 | ⬆️ **高（数据源必备）** |
| **遗漏** | 数据列标准化 | ⬆️ **高（数据源必备）** |
| **遗漏** | LLM 工具调用 | ⬆️ **高（Agent 必备）** |

---

## 四、遗漏项深度分析

### 4.1 JSON 响应修复机制（高优先级 — AI 集成必备）

**问题**：LLM 输出的 JSON 经常格式异常（尾随逗号、布尔值大小写、Markdown 代码块包裹、注释等），不做修复则 AI 功能不可用。

**DSA 方案**：`json_repair` 库 + 四级渐进降级

```
Level 1: Markdown 代码块提取 → json.loads() → 失败则 repair_json()
Level 2: 原始文本 → json.loads()
Level 3: 原始文本 → repair_json() → json.loads()
Level 4: 花括号定位提取 → json.loads() → 失败则 repair_json()
```

另外还有手动预处理：移除 `//`/`/* */` 注释、修复尾随逗号、`True`→`true`/`False`→`false`。

**SQ 借鉴方案**：
- 新增 `stockquant/ai/json_utils.py`
- 实现 `robust_json_parse(content: str) -> dict | None`，复用 DSA 的四级降级策略
- 在 BacktestAgent/SignalAgent 的 LLM 输出解析中使用
- 依赖：`json-repair>=0.7` 加入 `extras_require.ai`

---

### 4.2 LLM Tool Calling 能力（高优先级 — Agent 必备）

**问题**：ReAct Agent 需要模型原生工具调用（function calling），不是简单的 prompt injection。没有 Tool Calling，Agent 无法动态选择工具、并行执行、多轮推理。

**DSA 方案**：`LLMToolAdapter.call_with_tools()` + `ToolRegistry.to_openai_tools()`

```
工具定义流程：
  ToolDefinition(name, description, parameters) → to_openai_tool() → OpenAI tools 格式
  @tool 装饰器 → 自动从函数签名推断参数类型

调用流程：
  call_with_tools(messages, tools)
    → 模型降级链（主模型 → fallback 模型）
    → litellm.completion(messages, tools=tools)
    → 解析 response.choices[0].message.tool_calls
    → 返回 LLMResponse(content, tool_calls, reasoning_content, usage)

关键：litellm 统一适配层，所有 provider 工具声明用 OpenAI 格式，底层自动转换
```

**SQ 借鉴方案**：
- 新增 `stockquant/agent/llm_adapter.py`（参考 DSA 的 LLMToolAdapter）
- 新增 `stockquant/agent/tool_registry.py`（工具注册 + OpenAI schema 生成）
- `@tool` 装饰器：从函数签名自动推断参数类型
- 内置工具：`get_kline`、`calculate_indicator`、`run_backtest`、`search_news`
- 与现有 `BaseStrategy` 和 `SignalManager` 集成

---

### 4.3 数据标准化列模式（高优先级 — 数据源必备）

**问题**：不同数据源返回的列名不同（BaoStock 用 `date/open/high/low/close/volume`，AkShare 用 `日期/开盘/收盘`），SQ 当前无统一格式，多源切换时下游代码无法兼容。

**DSA 方案**：`STANDARD_COLUMNS` + 四步流水线

```python
STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']

四步流水线：
  _fetch_raw_data()   → 各数据源原始格式
  _normalize_data()   → 列名映射到 STANDARD_COLUMNS
  _clean_data()       → 类型转换 + 去空 + 排序
  _calculate_indicators() → 自动追加 ma5/ma10/ma20/volume_ratio
```

**SQ 借鉴方案**：
- 在 `stockquant/data/feed.py` 中定义 `STANDARD_COLUMNS`
- 所有 DataFeed 子类的 `get_dataframe()` 输出统一为 STANDARD_COLUMNS 格式
- 新增 `normalize_columns()` 和 `clean_dataframe()` 工具函数
- BarData 从 STANDARD_COLUMNS 构建，确保数据一致性

---

### 4.4 异常层次体系 + tenacity 重试（高优先级 — 数据源必备）

**问题**：SQ 当前只有 `raise ValueError`，无异常分类，无重试机制。网络请求失败直接崩溃，无法区分限流/超时/数据源不可用。

**DSA 方案**：异常层次 + tenacity + 双重防护

```
异常层次：
  DataFetchError
    ├── RateLimitError          → 不重试，触发故障切换
    └── DataSourceUnavailableError → 不重试，触发故障切换

tenacity 重试配置：
  网络瞬态错误（ConnectionError/TimeoutError）→ 指数退避重试（2-30秒，最多3次）
  限流错误（RateLimitError）→ 不重试，交给 DataFetcherManager 切换数据源

双重防护：
  tenacity：处理网络瞬态错误（自动重试）
  DataFetcherManager：处理数据源级错误（自动切换）

防封禁：
  random_sleep(1-3秒)：每次请求前随机延迟
  EfinanceFetcher：stop_after_attempt(1)，不重试（东财对频繁请求敏感）
```

**SQ 借鉴方案**：
- 新增 `stockquant/data/exceptions.py`
  - `DataFetchError` 基类
  - `RateLimitError`（限流，不重试，触发切换）
  - `DataSourceUnavailableError`（数据源不可用，触发切换）
  - `DataValidationError`（数据格式异常）
- 所有 DataFeed 子类使用 `@retry` 装饰器
- 依赖：`tenacity>=8.0` 加入 `install_requires`（核心依赖）
- DataFeedManager 捕获 `RateLimitError` 触发故障切换

---

## 五、修正后的优先级总表

| 优先级 | 借鉴方向 | 来源 | 说明 |
|--------|----------|------|------|
| **P0** | 多数据源自动故障切换 | DSA DataFetcherManager | 解决单源脆弱问题 |
| **P0** | 异常层次 + tenacity 重试 | DSA DataFetchError + tenacity | 数据源可靠性基础设施 |
| **P0** | 数据列标准化 | DSA STANDARD_COLUMNS | 多源切换的前提条件 |
| **P0** | 交易日历 | DSA exchange-calendars | 修复 T+1 bug |
| **P0** | AI 接入 LiteLLM | DSA GeminiAnalyzer | 让 AI 模块真正可用 |
| **P0** | JSON 响应修复 | DSA json_repair + 四级降级 | AI 集成的必要前提 |
| **P0** | LLM Tool Calling | DSA LLMToolAdapter | Agent 的核心基础设施 |
| **P1** | ReAct Agent | DSA AgentExecutor | 智能策略问股 |
| **P1** | 策略 YAML 配置 | DSA 11 个 YAML 策略 | 降低策略编写门槛 |
| **P1** | 通知渠道扩展 | DSA 10+ 渠道 | 提升通知能力 |
| **P1** | Markdown 转图片 | DSA md2img | 通知生产必备 |
| **P1** | 数据持久化 | DSA SQLAlchemy ORM | 回测结果/行情持久化 |
| **P1** | 定时调度 | DSA schedule + 交易日检查 | 自动化运行 |
| **P2** | 大盘复盘 | DSA 三段式复盘 | 市场整体视角 |
| **P2** | 信号级回测评价 | DSA BacktestEngine | AI 信号准确率评估 |
| **P2** | 消息分批/路由 | DSA 按渠道分批 | 通知体验优化 |
| **P2** | 报告文件保存 | DSA report_YYYYMMDD.md | 报表持久化 |

> **P0 = 阻塞性依赖**（不做则后续功能无法实现）
> **P1 = 核心功能**（显著提升平台能力）
> **P2 = 体验优化**（锦上添花）
