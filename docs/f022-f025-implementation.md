# F022 AI 策略生成 Agent + F025 AI 辅助决策 Agent 实施计划

## 一、现状分析

### 1.1 已有基础设施（可复用）

| 组件 | 文件 | 能力 |
|------|------|------|
| ReActAgent | `stockquant/agent/react_agent.py` | Thought-Action-Observation 推理循环，工具注册/执行，Final Answer 提取 |
| LLMAdapter | `stockquant/agent/llm_adapter.py` | litellm 统一调用，call_with_tools，模型回退链 |
| ToolRegistry | `stockquant/agent/tool_registry.py` | @tool 装饰器，OpenAI schema 生成，工具执行 |
| BacktestAgent | `stockquant/ai/backtest_agent.py` | 规则驱动的回测解读（问题识别+改进建议+多维度分析） |
| IndicatorAgent | `stockquant/ai/indicator_agent.py` | 市场状态检测+指标推荐+指标评分 |
| RiskAgent | `stockquant/ai/risk_agent.py` | 市场环境检测+动态风控调整+异常检测+相关性监控 |
| NewsSearcher | `stockquant/ai/news_searcher.py` | 多源新闻搜索+情感分析 |
| robust_json_parse | `stockquant/ai/json_utils.py` | 4级降级 JSON 解析 |
| YamlStrategyLoader | `stockquant/strategy/yaml_loader.py` | YAML → BaseStrategy 动态类生成 |
| DataFetcherManager | `stockquant/data/fetcher_manager.py` | 多数据源故障切换 |
| TradingCalendar | `stockquant/data/calendar.py` | 交易日历 |
| Notifier 基类 | `stockquant/execution/notifier/` | 9 渠道通知 |

### 1.2 缺失项

- **F022 strategy_agent.py** — 不存在
- **F025 decision_agent.py** — 不存在
- **F022/F025 专用工具集** — 不存在（现有 ReActAgent 仅有 get_kline/search_news/calculate_indicator 3 个占位工具）
- **F022/F025 专用 Prompt** — 不存在
- **F022/F025 测试** — 不存在

### 1.3 现有 Agent 的关键差距

| 差距 | 说明 |
|------|------|
| 现有 Agent 均为规则驱动 | BacktestAgent/IndicatorAgent/RiskAgent 不调用 LLM，纯 if-else 逻辑 |
| ReActAgent 工具不完整 | calculate_indicator 仅返回占位字符串，无真实计算 |
| 无策略代码生成能力 | 没有 NL → Python 策略代码的生成/验证/执行流水线 |
| 无决策验证能力 | 没有信号验证、风险二次确认、仓位合理性检查 |
| 无人机协同模式 | 没有全自动/半自动/只读模式切换 |

---

## 二、设计方案

### 2.1 F022 AI 策略生成 Agent

**定位**：用户用自然语言描述策略意图 → AI 自动生成可执行的 BaseStrategy 子类代码 → 自动回测验证 → 评分 + 优化建议

**架构**：基于 ReActAgent 扩展，注册策略生成专用工具

```
用户输入: "当MACD金叉且RSI<30时买入，仓位20%，止损5%"
    ↓
StrategyAgent (继承 ReActAgent 的推理循环)
    ↓ 调用工具链
    ├── parse_strategy_intent()   → 解析策略要素（指标/条件/仓位/风控）
    ├── generate_strategy_code()  → LLM 生成 BaseStrategy 子类代码
    ├── validate_strategy_code()  → 语法检查 + 导入检查 + 实例化测试
    ├── backtest_strategy()       → 自动回测（Cerebro.run）
    ├── score_strategy()          → 多维度评分（复用 BacktestAgent）
    └── suggest_improvements()    → LLM 生成优化建议
    ↓
输出: 完整策略代码 + 回测结果 + 评分 + 优化建议
```

**关键设计决策**：

1. **不直接生成 YAML**：虽然 SQ 有 YamlStrategyLoader，但 NL → YAML → BaseStrategy 的表达能力有限（YAML 仅支持简单条件表达式）。F022 直接生成 Python 代码更灵活，同时提供 YAML 导出作为可选输出。

2. **代码沙箱验证**：生成的代码必须通过 3 层验证——语法检查（compile）→ 导入检查（确保只引用 stockquant 内部模块）→ 实例化测试（type() 创建类 + 检查必要方法）

3. **策略知识库**：使用 SQLite 持久化历史策略（复用 persistence 模块），支持按指标/收益率/夏普检索相似策略

### 2.2 F025 AI 辅助决策 Agent

**定位**：在交易执行前，AI 作为"第二大脑"对信号进行二次验证，给出决策建议

**架构**：基于 ReActAgent 扩展，注册决策验证专用工具

```
输入: 信号（来自 BaseStrategy 或 F024 盯盘 Agent）
    ↓
DecisionAgent (继承 ReActAgent 的推理循环)
    ↓ 调用工具链
    ├── verify_signal()           → 技术面二次确认（多指标交叉验证）
    ├── assess_risk()             → 风险评估（复用 RiskAgent）
    ├── check_market_env()        → 市场环境评估（复用 MarketEnvDetector）
    ├── analyze_news()            → 消息面验证（复用 NewsSearcher）
    ├── evaluate_position()       → 仓位合理性检查
    └── generate_decision()       → 综合决策建议
    ↓
输出: DecisionAdvice {
    action: "confirm" | "reject" | "modify",
    confidence: 0.0-1.0,
    reason: str,
    modified_params: dict | None,
    risk_warnings: list[str]
}
```

**关键设计决策**：

1. **信号优先级**：严格遵循 Product-Spec 定义——传统策略信号 > AI 辅助信号(F025) > AI 生成策略信号(F022)

2. **人机协同模式**：DecisionMode 枚举（AUTO/SEMI_AUTO/READ_ONLY），通过配置切换

3. **审计日志**：每笔交易的 AI 决策理由记录到 AuditLog，确保可追溯

4. **与现有 Agent 的集成**：F025 复用 RiskAgent（风控评估）、IndicatorAgent（市场状态）、NewsSearcher（消息面），不重复造轮子

---

## 三、实施步骤

### Step 1: F022 策略生成工具集

**新建文件**: `stockquant/agent/strategy_tools.py`

注册 6 个工具到 ToolRegistry：

| 工具名 | 功能 | 输入 | 输出 |
|--------|------|------|------|
| `parse_strategy_intent` | 解析自然语言为策略要素 | `description: str` | `StrategyIntent{indicators, conditions, position, risk}` |
| `generate_strategy_code` | LLM 生成 BaseStrategy 子类代码 | `intent: StrategyIntent` | `str (Python code)` |
| `validate_strategy_code` | 验证策略代码可用性 | `code: str` | `ValidationResult{valid, errors, warnings}` |
| `backtest_strategy` | 自动回测生成的策略 | `code: str, symbol: str, start: str, end: str` | `BacktestResult` |
| `score_strategy` | 多维度评分 | `backtest_result: dict` | `StrategyScore{total, dimensions}` |
| `suggest_improvements` | LLM 生成优化建议 | `code: str, score: StrategyScore` | `list[ImprovementSuggestion]` |

### Step 2: F025 决策验证工具集

**新建文件**: `stockquant/agent/decision_tools.py`

注册 6 个工具到 ToolRegistry：

| 工具名 | 功能 | 输入 | 输出 |
|--------|------|------|------|
| `verify_signal` | 技术面二次确认 | `symbol: str, signal_type: str, direction: str` | `SignalVerification{confirmed, indicators_summary}` |
| `assess_risk` | 风险评估 | `symbol: str, position_pct: float, direction: str` | `RiskAssessment{level, warnings, adjusted_params}` |
| `check_market_env` | 市场环境评估 | `symbol: str` | `MarketEnvResult{environment, suggestion}` |
| `analyze_news_sentiment` | 消息面验证 | `symbol: str` | `SentimentResult{score, key_events, warnings}` |
| `evaluate_position` | 仓位合理性检查 | `symbol: str, current_positions: dict, proposed_trade: dict` | `PositionEvaluation{reasonable, suggestion}` |
| `generate_decision` | 综合决策建议 | `verification, risk, env, sentiment, position` | `DecisionAdvice{action, confidence, reason, modifications}` |

### Step 3: F022 StrategyAgent

**新建文件**: `stockquant/ai/strategy_agent.py`

```python
class StrategyAgent:
    """F022 AI 策略生成与配置 Agent"""
    
    def __init__(self, model, api_key, ...):
        self._react = ReActAgent(model=model, api_key=api_key, max_steps=15)
        # 注册策略生成工具
        self._react.register_tools(
            parse_strategy_intent_tool,
            generate_strategy_code_tool,
            validate_strategy_code_tool,
            backtest_strategy_tool,
            score_strategy_tool,
            suggest_improvements_tool,
        )
    
    def generate(self, description: str, symbol: str = "sh600519",
                 start: str = None, end: str = None) -> StrategyGenerationResult:
        """从自然语言生成策略"""
        ...
    
    def improve(self, strategy_code: str, backtest_result: dict) -> StrategyImprovementResult:
        """基于回测结果改进策略"""
        ...
```

**Prompt 设计**（策略生成专用系统提示词）：

```
你是一个专业的 A 股量化策略工程师。你的任务是根据用户的自然语言描述，
生成可在 StockQuant 框架中运行的 BaseStrategy 子类代码。

工作流程（严格按顺序）：
1. 解析策略意图：提取技术指标、入场/出场条件、仓位管理、风控参数
2. 生成策略代码：基于 BaseStrategy 编写完整的 Python 类
3. 验证策略代码：确保语法正确、导入合法、可实例化
4. 回测验证：使用 Cerebro 引擎运行回测
5. 评分：从收益/风险/交易质量/稳定性 4 个维度评分
6. 优化建议：基于评分给出具体改进方向

策略代码规范：
- 必须继承 BaseStrategy
- 必须实现 on_start() 和 on_bar()
- 使用 self.EMA/SMA/RSI/MACD/BOLL/ATR/KDJ 等指标方法
- 使用 self.order_market() / self.order_sell() 下单
- 使用 self.log() 记录交易日志

A 股特殊规则：
- 买入数量必须为 100 的整数倍
- T+1 卖出限制
- 涨跌停板限制（10%/20%/30%）
- 佣金万2.5 + 印花税千1
```

### Step 4: F025 DecisionAgent

**新建文件**: `stockquant/ai/decision_agent.py`

```python
class DecisionMode(Enum):
    AUTO = "auto"           # AI 建议自动下单
    SEMI_AUTO = "semi_auto" # AI 建议 → 用户确认 → 下单
    READ_ONLY = "read_only" # AI 只推送建议

class DecisionAgent:
    """F025 AI 辅助决策 Agent"""
    
    def __init__(self, model, api_key, mode=DecisionMode.SEMI_AUTO, ...):
        self._react = ReActAgent(model=model, api_key=api_key, max_steps=10)
        self._mode = mode
        # 注册决策验证工具
        self._react.register_tools(
            verify_signal_tool,
            assess_risk_tool,
            check_market_env_tool,
            analyze_news_sentiment_tool,
            evaluate_position_tool,
            generate_decision_tool,
        )
    
    def evaluate(self, signal: Signal, portfolio: Portfolio = None) -> DecisionAdvice:
        """评估交易信号，给出决策建议"""
        ...
    
    def batch_evaluate(self, signals: list[Signal]) -> list[DecisionAdvice]:
        """批量评估信号"""
        ...
```

**Prompt 设计**（决策验证专用系统提示词）：

```
你是一个专业的 A 股交易决策顾问。你的任务是对交易信号进行二次验证，
给出是否执行、如何执行的建议。

工作流程（严格按顺序）：
1. 技术面验证：多指标交叉确认信号可靠性
2. 风险评估：检查仓位/回撤/集中度风险
3. 市场环境：判断当前牛/熊/震荡/暴跌，调整仓位建议
4. 消息面验证：搜索最新新闻，确认是否有利空/利好
5. 仓位合理性：检查是否过度集中、是否超出风控限制
6. 综合决策：综合以上分析，给出 confirm/reject/modify 建议

决策原则：
- 信号优先级：传统策略信号 > AI 辅助信号 > AI 生成策略信号
- 风险优先：有疑虑则否决，宁可错过不可做错
- 仓位保守：建议仓位不超过信号原始建议的 80%
- 止损必设：每笔交易必须设置止损点
- T+1 意识：当日买入不可卖出，注意流动性风险

输出格式：
{
    "action": "confirm" | "reject" | "modify",
    "confidence": 0.0-1.0,
    "reason": "决策理由",
    "modified_params": {"qty": ..., "price": ...} | null,
    "risk_warnings": ["风险1", "风险2"],
    "stop_loss": 止损价,
    "take_profit": 止盈价
}
```

### Step 5: 数据模型

**新建文件**: `stockquant/ai/models.py`

```python
@dataclass
class StrategyIntent:
    """策略意图解析结果"""
    indicators: list[dict]      # [{"name": "MACD", "params": {...}}]
    entry_conditions: list[str] # ["MACD 金叉", "RSI < 30"]
    exit_conditions: list[str]  # ["MACD 死叉", "止损 5%"]
    position_method: str        # "FixedFraction"
    position_params: dict       # {"pct": 0.2}
    risk_params: dict           # {"stop_loss": 0.05}

@dataclass
class StrategyScore:
    """策略评分"""
    total: float                # 0-100 综合分
    profitability: float        # 收益维度
    risk_control: float         # 风险维度
    trading_quality: float      # 交易质量维度
    stability: float            # 稳定性维度
    overfitting_risk: str       # "low" / "medium" / "high"

@dataclass
class DecisionAdvice:
    """决策建议"""
    action: str                 # "confirm" / "reject" / "modify"
    confidence: float           # 0.0-1.0
    reason: str
    modified_params: dict | None
    risk_warnings: list[str]
    stop_loss: float | None
    take_profit: float | None

@dataclass
class AuditLog:
    """决策审计日志"""
    timestamp: datetime
    signal_source: str          # "strategy" / "F024" / "F022"
    symbol: str
    direction: str              # "BUY" / "SELL"
    original_signal: dict
    ai_decision: DecisionAdvice
    final_action: str           # 实际执行的动作
    user_confirmed: bool | None # 半自动模式下用户是否确认
```

### Step 6: 审计日志持久化

**修改文件**: `stockquant/persistence/models.py`

新增 `AuditLogModel` SQLAlchemy 模型，记录每笔 AI 决策的完整信息。

**修改文件**: `stockquant/persistence/repository.py`

新增 `save_audit_log` / `list_audit_logs` / `get_audit_log` 方法。

### Step 7: 更新包导出

**修改文件**: `stockquant/ai/__init__.py`

新增导出：`StrategyAgent`, `DecisionAgent`, `DecisionMode`, `DecisionAdvice`, `StrategyScore`, `AuditLog`

### Step 8: 测试

**新建文件**: `tests/test_strategy_agent.py`

- test_parse_intent_basic — 基本策略意图解析
- test_parse_intent_complex — 复杂策略意图（多指标+仓位+风控）
- test_generate_code_simple — 简单策略代码生成
- test_generate_code_with_risk — 含风控的策略代码生成
- test_validate_code_valid — 合法代码验证通过
- test_validate_code_syntax_error — 语法错误检测
- test_validate_code_missing_method — 缺少必要方法检测
- test_score_strategy_excellent — 优秀策略评分
- test_score_strategy_poor — 糟糕策略评分
- test_suggest_improvements — 优化建议生成
- test_full_pipeline — 完整流水线（NL → 代码 → 验证 → 回测 → 评分 → 建议）

**新建文件**: `tests/test_decision_agent.py`

- test_verify_signal_confirmed — 信号确认
- test_verify_signal_rejected — 信号否决（指标矛盾）
- test_assess_risk_high — 高风险评估
- test_assess_risk_low — 低风险评估
- test_check_market_env_bull — 牛市环境
- test_check_market_env_crash — 暴跌环境
- test_analyze_news_positive — 正面消息
- test_analyze_news_negative — 负面消息
- test_evaluate_position_overconcentrated — 过度集中
- test_generate_decision_confirm — 确认决策
- test_generate_decision_reject — 否决决策
- test_generate_decision_modify — 修改决策（调整仓位）
- test_decision_mode_auto — 全自动模式
- test_decision_mode_semi_auto — 半自动模式
- test_decision_mode_read_only — 只读模式
- test_audit_log_recording — 审计日志记录
- test_signal_priority — 信号优先级验证

---

## 四、文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| **新建** | `stockquant/agent/strategy_tools.py` | F022 策略生成工具集（6 个 @tool 函数） |
| **新建** | `stockquant/agent/decision_tools.py` | F025 决策验证工具集（6 个 @tool 函数） |
| **新建** | `stockquant/ai/strategy_agent.py` | F022 StrategyAgent 主类 |
| **新建** | `stockquant/ai/decision_agent.py` | F025 DecisionAgent 主类 |
| **新建** | `stockquant/ai/models.py` | F022/F025 共享数据模型 |
| **新建** | `tests/test_strategy_agent.py` | F022 测试 |
| **新建** | `tests/test_decision_agent.py` | F025 测试 |
| **修改** | `stockquant/ai/__init__.py` | 新增导出 |
| **修改** | `stockquant/persistence/models.py` | 新增 AuditLogModel |
| **修改** | `stockquant/persistence/repository.py` | 新增审计日志 CRUD |

---

## 五、验证步骤

1. `python -m pytest tests/test_strategy_agent.py tests/test_decision_agent.py -v` — 全部测试通过
2. `python -m pytest --tb=short -q` — 全量测试无回归
3. 手动验证 F022 流水线：
   ```python
   from stockquant.ai import StrategyAgent
   agent = StrategyAgent(model="deepseek/deepseek-chat", api_key="...")
   result = agent.generate("当MACD金叉且RSI<30时买入，仓位20%，止损5%", symbol="sh600519")
   print(result.code)       # 生成的策略代码
   print(result.score)      # 评分
   print(result.suggestions) # 优化建议
   ```
4. 手动验证 F025 决策流程：
   ```python
   from stockquant.ai import DecisionAgent, DecisionMode
   agent = DecisionAgent(model="deepseek/deepseek-chat", api_key="...", mode=DecisionMode.SEMI_AUTO)
   advice = agent.evaluate(signal={"symbol": "sh600519", "direction": "BUY", "qty": 100})
   print(advice.action)          # confirm/reject/modify
   print(advice.confidence)      # 0.0-1.0
   print(advice.risk_warnings)   # 风险警告
   ```
5. 验证审计日志持久化：检查 SQLite 中 audit_logs 表记录
