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
