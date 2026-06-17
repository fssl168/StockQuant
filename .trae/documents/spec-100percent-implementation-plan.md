# Spec 对齐 100% 达标实施计划

> **目标**: 将 v3 评估报告中的 88% 达标率提升至 95%+
> **用户确认方案**: 规则引擎+LLM混合 / 添加闭环配置项 / 补全环境变量映射

---

## 实施步骤（8 步）

### Step 1: 修复 `/monitor/risk-control` 端点（P0）

**文件**: `stockquant/api/routers/monitor.py`

前端 `Monitor.tsx` 已调用 `GET /monitor/risk-control`，但后端无此端点。

添加端点，返回动态风控参数：
- `environment`: calm/volatile/extreme（基于沪深300近20日波动率）
- `max_position_pct`: calm=0.3, volatile=0.2, extreme=0.1
- `max_daily_loss_pct`: calm=0.05, volatile=0.03, extreme=0.02
- `max_drawdown_pct`: 0.15
- `risk_level`: low/medium/high

波动率计算：读取近20日沪深300日收益率标准差 σ
- σ < 0.01 → calm
- 0.01 ≤ σ < 0.02 → volatile
- σ ≥ 0.02 → extreme

### Step 2: Portfolio 权益快照持久化（P1）

**文件**:
- `stockquant/persistence/models.py` — 添加 `EquitySnapshot` ORM 模型
- `stockquant/api/routers/portfolio.py` — 添加快照端点 + 修改 equity-curve 优先读快照

EquitySnapshot 字段: id, date, equity, cash, market_value, positions_count, created_at

端点:
- `POST /portfolio/snapshot` — 手动触发快照
- `GET /portfolio/equity-curve` — 优先级: EquitySnapshot → BacktestResult → 实时推算

### Step 3: 修复 QMT Broker 拼写错误（P1）

**文件**: `stockquant/execution/brokers/qmt_broker.py`

`STOCK_SENSE` → `STOCK_SELL`

### Step 4: 本地规则引擎（P2，规则引擎+LLM混合方案）

**文件**:
- `stockquant/ai/local_rule_engine.py` — 新建
- `stockquant/agent/llm_adapter.py` — 添加本地推理路径
- `stockquant/ai/decision_agent.py` — 修改 tick 级分支

规则引擎 `LocalRuleEngine` 类：
- `analyze_signal(indicators)` — 基于 MA/MACD/RSI/BOLL 的快速信号判断
- `generate_decision(market_data)` — 纯数学计算，延迟 < 50ms
- 无需 LLM 调用，无需 GPU

在 `LLMAdapter` 中添加:
- `_call_local_rule_engine(messages)` 方法
- 当 model 参数为 `local_rule_engine` 时走规则引擎路径

### Step 5: NLP 情感分析增强（P2）

**文件**:
- `stockquant/ai/sentiment.py` — 新建
- `stockquant/ai/monitor_agent.py` — 修改 `_analyze_social_sentiment()`

`SentimentAnalyzer` 类，三级降级：
1. 规则引擎增强版（当前关键词 + 金融词典扩展 + 否定词处理）
2. 无外部依赖，纯 Python 实现
3. 预留 HuggingFace 接口（可选安装 transformers 后启用）

### Step 6: 闭环系统配置项（P2）

**文件**:
- `stockquant/config.py` — 添加 AI 管线配置组
- `stockquant/api/routers/settings.py` — 添加配置 schema
- `web/src/pages/Settings.tsx` — 添加 AI 管线配置组

新增配置组 `ai_pipeline`:
- `ai_pipeline.collect_interval_sec`: 采集频率（默认 300）
- `ai_pipeline.denoise_source_credit_threshold`: 来源信用阈值（默认 0.5）
- `ai_pipeline.denoise_timeliness_hours`: 时效降权小时数（默认 24）
- `ai_pipeline.summarize_period`: 总结周期 daily/weekly/monthly（默认 daily）
- `ai_pipeline.elevate_min_articles`: 升华触发最少文章数（默认 3）
- `ai_pipeline.hallucination_mode`: 反幻觉模式 strict/standard/relaxed/emergency（默认 standard）
- `ai_pipeline.memory_l2_retention_days`: L2 保留天数（默认 30）
- `ai_pipeline.memory_l3_confidence_threshold`: L3 置信度阈值（默认 0.15）

### Step 7: 补全环境变量映射（P2）

**文件**: `stockquant/config.py`

在 `_apply_env_overrides` 的 `env_mappings` 中添加:

```python
# AI 管线配置
"AI_PIPELINE_COLLECT_INTERVAL_SEC": ("ai_pipeline", "collect_interval_sec"),
"AI_PIPELINE_DENOISE_SOURCE_CREDIT_THRESHOLD": ("ai_pipeline", "denoise_source_credit_threshold"),
"AI_PIPELINE_DENOISE_TIMELINESS_HOURS": ("ai_pipeline", "denoise_timeliness_hours"),
"AI_PIPELINE_SUMMARIZE_PERIOD": ("ai_pipeline", "summarize_period"),
"AI_PIPELINE_ELEVATE_MIN_ARTICLES": ("ai_pipeline", "elevate_min_articles"),
"AI_PIPELINE_HALLUCINATION_MODE": ("ai_pipeline", "hallucination_mode"),
"AI_PIPELINE_MEMORY_L2_RETENTION_DAYS": ("ai_pipeline", "memory_l2_retention_days"),
"AI_PIPELINE_MEMORY_L3_CONFIDENCE_THRESHOLD": ("ai_pipeline", "memory_l3_confidence_threshold"),
# 本地模型
"LOCAL_RULE_ENGINE_ENABLED": ("ai_pipeline", "local_rule_engine_enabled"),
# 情感分析
"SENTIMENT_METHOD": ("ai_pipeline", "sentiment_method"),
```

同时在 `DEFAULT_CONFIG` 中添加 `ai_pipeline` 默认值。

**文件**: `docker-compose.yml` — 在 backend environment 中添加对应环境变量

### Step 8: GitHub Actions CI（P2）

**文件**: `.github/workflows/test.yml`

CI 配置:
- Python 3.10 + Node 18
- 安装依赖 + pytest NFR 测试
- 前端 tsc --noEmit 类型检查

---

## 验证步骤

1. 后端: `python -c "import stockquant.api.main; print('OK')"`
2. 前端: `npx tsc --noEmit`
3. 端点验证: `curl http://localhost:8000/api/monitor/risk-control`
