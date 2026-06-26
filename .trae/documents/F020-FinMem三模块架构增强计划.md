# F020 采集端信息处理增强计划 — FinMem 三模块架构（合并版）

> **核心约束**：采用 FinMem 论文三大模块架构（Profiling / Memory 分层 / Decision-making）作为核心框架，同时合并旧版"采集→降噪→总结→升华"四阶段管线的完整能力增强，不引入新依赖（基于现有 litellm + pgvector + sentence-transformers + asyncio + FastAPI + SQLAlchemy 技术栈）。
>
> **本计划由两份文档合并**：
> - 旧版「F020 采集端信息处理增强计划」（管线细节、工程化、删除 DEPRECATED）
> - 新版「F020-FinMem 三模块架构增强计划」（FinMem 三大模块、多因子召回、Profiling、F020→F025 桥接）

---

## 1. 摘要

借鉴 GitHub 同类型机构级项目（TradingAgents 80k★、FinMem、FINGROUND、FinRobot），将 F020（AI 信息处理）从单一信息流水线升级为 **FinMem 三模块决策认知架构**：

1. **Profiling 模块（新建）**：用户风险偏好画像（保守/中性/激进）+ 基于市场环境与持仓的动态转换机制
2. **Memory 模块（重构分层 + 管线完整化）**：
   - **三层分层**：Shallow 浅层（市场新闻，复用 L2）/ Intermediate 中层（公司季报，L3-Intermediate）/ Deep 深层（公司年报，L3-Deep）
   - **多因子召回**：相关性 + 新鲜度（分层半衰期）+ 重要性（多维加权）
   - **Working Memory 三组件**：Summarization / Observation / Reflection
   - **管线完整化**：合并旧版 DEPRECATED 的完整能力（LLM 总结、L3 集成、推理链验证）到新版四阶段
   - **工程化**：压缩器接入 LLM、L3 embedding fallback、噪音模式库
3. **Decision-making 模块（增强）**：F020 洞察 → F025 决策的桥接 + Profiling 注入
4. **采集端补齐**：新增 ResearchCollector / FinancialCollector / ExchangeCollector，修复 AlphaFeed stub
5. **反幻觉增强**：FINGROUND 六类原子声明分类验证 + 多模型交叉验证 + FAKE_SOURCES 黑名单
6. **工程化**：asyncio 自动调度器、data_sources.yaml 配置化、审计日志、数据源变更检测、删除 DEPRECATED 文件

**关键产出**：Profiling 模块全新、Memory 三层 + 多因子召回、Working Memory 三组件、四阶段管线 5/6/5 步完整化、F020→F025 洞察桥接、3 新采集器、反幻觉六类验证 + 多模型交叉、工程化闭环。

---

## 2. 现状分析（基于 Phase 1 探索）

### 2.1 当前架构（与 FinMem 对照）

| FinMem 模块 | FinMem 设计 | StockQuant 现状 | 对齐度 |
|------------|-------------|-----------------|-------|
| Profiling | 风险偏好枚举 + 动态转换 | **完全缺失**（[UserModel](file:///d:/projects/StockQuant/stockquant/persistence/models.py#L77-L91) 无 risk_profile 字段） | 0% |
| Memory-Shallow | 市场新闻短时效 | L2 短期记忆 ✓ | 70%（无分层标识） |
| Memory-Intermediate | 公司季报 | L3 单层混存，无 tier 字段 | 20% |
| Memory-Deep | 公司年报 | L3 单层混存，无 period_type 字段 | 20% |
| Memory 多因子召回 | relevance + recency + importance | **仅 relevance 单因子**（[l2_store.py](file:///d:/projects/StockQuant/stockquant/ai/memory/l2_store.py)、[l3_store.py#L331-L364](file:///d:/projects/StockQuant/stockquant/ai/memory/l3_store.py#L331-L364)） | 33% |
| Working Memory 三组件 | Summarization + Observation + Reflection | **仅 deque**（[working.py](file:///d:/projects/StockQuant/stockquant/ai/memory/working.py) 52 行） | 20% |
| Decision-making 洞察桥接 | F020 洞察 → F025 | [pipeline_orchestrator.py#L74-L83](file:///d:/projects/StockQuant/stockquant/ai/pipeline_orchestrator.py#L74-L83) 只写 L3，**不传 F025** | 0% |
| Decision-making Profiling 注入 | risk_profile 影响决策 | [decision_agent.py#L231-L286](file:///d:/projects/StockQuant/stockquant/ai/decision_agent.py#L231-L286) evaluate() 不接收 profile | 0% |

### 2.2 关键缺陷（旧版文档梳理 + 探索补充）

| # | 缺陷 | 影响 | 来源 |
|---|------|------|------|
| 1 | 新版总结**无 LLM 调用** | 摘要仅截断，无智能压缩 | 旧版文档 |
| 2 | 新版降噪**无 L3 集成** | 无法过滤已知噪音模式 | 旧版文档 |
| 3 | 新版升华**无推理链验证** | 无法验证因果逻辑 | 旧版文档 |
| 4 | AlphaFeed SDK 是 **stub**（`return []`） | 主路径形同虚设 | 旧版文档 |
| 5 | **无研报/财报/交易所采集器** | 数据源覆盖不足 | 旧版文档 |
| 6 | 记忆压缩器**无 LLM**（[截断 200 字](file:///d:/projects/StockQuant/stockquant/ai/memory/compressor.py#L141-L149)） | L2→L3 迁移质量差 | 旧版文档 |
| 7 | **FAKE_SOURCES 为空集** | 仿冒源检测失效 | 旧版文档 |
| 8 | **无自动调度器** | 仅 API 触发 | 旧版文档 |
| 9 | **无 data_sources.yaml** | 数据源硬编码 | 旧版文档 |
| 10 | **无审计日志** | 采集操作不可追溯 | 旧版文档 |
| 11 | L3 仅用 OpenAI embedding，**无 fallback** | API 不可用时降级为关键词 | 旧版文档 |
| 12 | Profiling 模块**完全缺失** | FinMem 第一支柱缺失 | 新版探索 |
| 13 | L3 单层，**无 tier/period_type/importance_score/last_accessed_at** | FinMem 三层无法区分 | 新版探索 |
| 14 | 召回**仅 relevance 单因子** | 召回率不足 | 新版探索 |
| 15 | Working Memory**仅 deque** | 缺 Summarization/Observation/Reflection | 新版探索 |
| 16 | F020→F025 **断链** | 洞察无法转化为决策 | 新版探索 |
| 17 | F025 evaluate() **不接收 insights/profile** | Profiling 无法注入决策 | 新版探索 |

### 2.3 新旧管线对比

| 维度 | 旧版（DEPRECATED） | 新版（当前） | 增强目标 |
|------|---------------------|-------------|---------|
| 降噪步骤 | 4 步（含 L3 已证伪） | 3 步 | 合并为 5 步 |
| 总结步骤 | 5 步（含 LLM + 多级摘要） | 3 步（无 LLM） | 合并为 6 步 |
| 升华步骤 | 5 步（含推理链验证） | 简化版 | 合并为 5 步 |

---

## 3. 提议变更

### Phase A：Profiling 模块（新建）

#### A1. 数据模型扩展

**文件**：`stockquant/persistence/models.py`

**变更**：UserModel 增加 risk_profile 字段；新增 UserProfileHistory 表（追踪动态转换历史）。

```python
class UserModel(Base):
    # ... 现有字段
    risk_profile: Mapped[str] = mapped_column(
        String(20), nullable=False, default="neutral"
    )  # conservative | neutral | aggressive
    profile_updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=True
    )

class UserProfileHistory(Base):
    """风险偏好转换历史（用于追踪动态转换）"""
    __tablename__ = "user_profile_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    from_profile: Mapped[str] = mapped_column(String(20), nullable=False)
    to_profile: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)  # market_crash | consecutive_loss | manual | ...
    context_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
```

#### A2. 新建 Profiling 模块目录

**新文件**：`stockquant/ai/profiling/__init__.py`、`risk_profile.py`、`manager.py`、`transition.py`

**`risk_profile.py`** — 枚举 + 偏好参数：

```python
from enum import Enum
from dataclasses import dataclass

class RiskProfile(str, Enum):
    CONSERVATIVE = "conservative"
    NEUTRAL = "neutral"
    AGGRESSIVE = "aggressive"

@dataclass
class ProfileParams:
    """风险偏好对应的决策参数（FinMem Profiling → Decision-making 注入）"""
    max_position_pct: float       # 单标的最大仓位
    stop_loss_pct: float          # 止损线
    take_profit_pct: float        # 止盈线
    max_drawdown_tolerance: float # 最大可承受回撤
    confidence_threshold: float  # 决策置信度阈值

PROFILE_PARAMS = {
    RiskProfile.CONSERVATIVE: ProfileParams(0.05, 0.03, 0.06, 0.08, 0.8),
    RiskProfile.NEUTRAL:      ProfileParams(0.10, 0.05, 0.10, 0.15, 0.6),
    RiskProfile.AGGRESSIVE:   ProfileParams(0.20, 0.08, 0.20, 0.25, 0.4),
}
```

**`transition.py`** — 动态转换规则（FinMem 论文 §3.2）：

```python
class ProfileTransitioner:
    """基于市场环境 + 持仓表现的动态风险偏好转换

    转换触发条件（保守策略，避免频繁切换）：
    - 市场暴跌（market_env=crash）：aggressive→neutral, neutral→conservative
    - 连续 3 次亏损（命中率 < 30%）：降一级
    - 用户手动覆盖
    - 冷却期 7 天（防止抖动）
    """
    COOLDOWN_DAYS = 7

    def should_transition(self, current, market_env, recent_hit_rate, days_since_last) -> bool: ...
    def transition(self, user_id, current, trigger, context) -> RiskProfile: ...
```

**`manager.py`** — 对外统一接口：

```python
class ProfilingManager:
    """Profiling 模块统一接口

    职责：
    1. 读取/更新用户风险偏好
    2. 触发动态转换
    3. 返回当前 ProfileParams 供 Decision-making 使用
    """
    def get_profile(self, user_id: str) -> RiskProfile: ...
    def get_params(self, user_id: str) -> ProfileParams: ...
    def update_profile(self, user_id, new_profile, trigger="manual") -> None: ...
    def evaluate_transition(self, user_id, market_env, recent_hit_rate) -> Optional[RiskProfile]: ...
```

#### A3. DB 迁移

通过 SQLAlchemy `Base.metadata.create_all` 自动创建（项目现有约定，见 [l3_store.py#L107-L113](file:///d:/projects/StockQuant/stockquant/ai/memory/l3_store.py#L107-L113)）。如生产环境使用 Alembic，则补充 Alembic migration 脚本。

---

### Phase B：Memory 模块重构（分层 + 多因子召回 + Working 三组件 + 管线完整化）

#### B1. L3Memory 表分层扩展

**文件**：`stockquant/persistence/models.py#L292-L309`

**变更**：L3Memory 增加 tier / period_type / importance_score / last_accessed_at 字段。

```python
class L3Memory(Base):
    # ... 现有字段
    tier: Mapped[str] = mapped_column(
        String(20), nullable=False, default="intermediate"
    )  # shallow | intermediate | deep
    period_type: Mapped[str] = mapped_column(
        String(20), nullable=True
    )  # quarterly | annual | ad_hoc
    importance_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )  # 0.0-1.0，由 ElevateStage 计算写入
    last_accessed_at: Mapped[str] = mapped_column(
        String(30), nullable=True
    )  # 用于 recency 因子（访问越久越衰减）
```

#### B2. FinMem 多因子召回子系统（核心）

**新文件**：`stockquant/ai/memory/recall_scorer.py`（独立模块，约 300 行）

借鉴 FinMem 论文 §3.3 的多因子召回机制，构建**相关性 + 新鲜度 + 重要性**三因子融合评分子系统，覆盖 L1/L2/L3 三层。

##### B2.1 三因子数学模型

```
final_score = α · relevance + β · recency + γ · importance
其中 α + β + γ = 1.0
默认 α=0.5, β=0.3, γ=0.2（FinMem 论文 §3.3 默认权重，可在 config.yaml 配置）
```

##### B2.2 因子 1：相关性（Relevance）

| 层 | 召回策略 | 相关性计算 |
|----|---------|-----------|
| L1 WorkingMemory | 关键词匹配 | `relevance = (命中关键词数 / 查询词总数) · source_weight` |
| L2 Shallow | TF-IDF + 关键词 | `relevance = 0.6·tfidf_score + 0.4·keyword_overlap`（保留 [l2_store.py](file:///d:/projects/StockQuant/stockquant/ai/memory/l2_store.py) 三级降级链） |
| L3 Intermediate/Deep | pgvector 向量 | `relevance = 1 - cosine_distance`（[l3_store.py#L377-L383](file:///d:/projects/StockQuant/stockquant/ai/memory/l3_store.py#L377-L383) `<=>` 余弦距离归一化） |

**source_weight 来源权重表**：

```python
SOURCE_WEIGHTS = {
    "exchange_announcement": 1.0,   # 交易所公告
    "company_report":         0.95, # 公司财报
    "research_report":        0.85, # 券商研报
    "official_news":          0.80, # 官方新闻
    "mainstream_media":       0.70, # 主流媒体
    "social_media":           0.50, # 社交媒体
    "unknown":                0.30, # 未知来源
}
```

##### B2.3 因子 2：新鲜度（Recency）—— 分层指数衰减

```python
def recency_score(timestamp_iso: str, tier: str, last_accessed_at: str = None) -> float:
    """分层半衰期指数衰减：recency = 0.5 ^ (age_days / half_life_days)

    分层半衰期（FinMem 论文 §3.3 表 2）：
      - shallow      (市场新闻): 3 天   — 短时效，3 天后相关性减半
      - intermediate (季报):     90 天  — 季度周期，覆盖财报披露间隔
      - deep         (年报):     365 天 — 长期有效，年报每年才更新
      - working      (L1):       1 天   — 工作记忆极短时效

    特殊处理：
      - 如果 last_accessed_at 存在，取 max(timestamp, last_accessed_at) 作为基准
        （访问会"刷新"记忆，借鉴人类记忆的提取强化效应）
    """
    HALF_LIFE = {"working": 1, "shallow": 3, "intermediate": 90, "deep": 365}
    half_life = HALF_LIFE.get(tier, 30)
    base_ts = last_accessed_at or timestamp_iso
    age_days = (datetime.now() - datetime.fromisoformat(base_ts)).total_seconds() / 86400
    return 0.5 ** (age_days / half_life)
```

##### B2.4 因子 3：重要性（Importance）—— 多维加权

```python
def importance_score(item: dict, tier: str) -> float:
    """分层重要性评分，归一化到 [0, 1]

    - shallow (新闻): f(来源权重, 情绪强度, 影响范围)
        = 0.4·source_weight + 0.3·|sentiment_score| + 0.3·scope_score
        scope_score: 全市场=1.0, 行业=0.7, 个股=0.4

    - intermediate (季报): f(事项类型, 财务指标变动幅度)
        = 0.5·event_weight + 0.5·|metric_change_pct|
        event_weight: 业绩预增=1.0, 业绩预减=0.9, 分红=0.7, 高管变动=0.6, 其他=0.3

    - deep (年报): f(年度关键事件数, 是否核心标的)
        = 0.6·key_event_count_normalized + 0.4·is_core_holding
        key_event_count 归一化: min(event_count / 10, 1.0)
    """
    ...
```

##### B2.5 RecallScorer 完整接口

```python
@dataclass
class RecallWeights:
    relevance: float = 0.5
    recency: float = 0.3
    importance: float = 0.2
    def __post_init__(self):
        assert abs(self.relevance + self.recency + self.importance - 1.0) < 1e-6

class RecallScorer:
    """FinMem 多因子召回评分器

    用法：
        scorer = RecallScorer(weights=RecallWeights())
        scored_items = [(item, scorer.score(item, query_embedding, query_text, tier="shallow"))
                        for item in candidate_items]
        scored_items.sort(key=lambda x: x[1], reverse=True)
        return [item for item, score in scored_items[:top_k]]
    """
    def __init__(self, weights: RecallWeights = None, config_path: str = None): ...
    def score(self, item, query_embedding, query_text, tier="shallow") -> float: ...
    def rank(self, items, query, tier="shallow", top_k=10) -> List[Dict]: ...
    def explain(self, item, query, tier) -> Dict[str, float]: ...
    def adaptive_weights(self, query_context) -> RecallWeights:
        """根据查询场景动态调整权重
        - 实时交易场景: relevance=0.7, recency=0.2, importance=0.1（侧重相关性）
        - 复盘分析场景: importance=0.5, relevance=0.3, recency=0.2（侧重重要性）
        - 历史回溯场景: recency=0.6, relevance=0.2, importance=0.2（侧重新鲜度）
        """
```

##### B2.6 三层集成点

**L1 WorkingMemory**：`query()` 使用 RecallScorer 排序，tier="working"；`get_recent(n)` 改为先按 recency 排序后截断

**L2Store**：`search()` 在三级降级链召回后用 RecallScorer 重排序，tier="shallow"；写入时记录 source_weight/sentiment_score/scope 用于 importance 计算

**L3Store**：`_search_async()` 在 pgvector 向量召回后用 RecallScorer 重排序；写入时根据 tier 字段选择对应半衰期与 importance 计算；新增 `search_by_tier(tier, query, top_k)` 方法

**MemoryManager**：`search()` 跨层检索时先各层用 RecallScorer 内部排序，再用 RecallScorer 跨层统一排序；跨层时各层 tier 不同（shallow/intermediate/deep），半衰期自动适配

##### B2.7 可观测性

每次召回返回时附带 `score_breakdown`：

```json
{
  "item_id": "l3_xxx",
  "final_score": 0.78,
  "score_breakdown": {
    "relevance": 0.85,
    "recency": 0.62,
    "importance": 0.90,
    "weights_used": {"relevance": 0.5, "recency": 0.3, "importance": 0.2}
  },
  "tier": "intermediate",
  "age_days": 45
}
```

#### B3. L3Store 支持 tier 过滤 + MemorySystem 分层接口

**文件**：`stockquant/ai/memory/l3_store.py`、`stockquant/ai/memory/system.py`

```python
# system.py 新增
def add_intermediate(self, symbol, content, period_type="quarterly", importance=0.5) -> str: ...
def add_deep(self, symbol, content, period_type="annual", importance=0.7) -> str: ...
def search_by_layer(self, query, layer: str, top_k=10) -> List[Dict]: ...  # shallow|intermediate|deep|all
```

#### B4. Working Memory 三组件

**文件**：`stockquant/ai/memory/working.py`（重写）

```python
class WorkingMemory:
    """FinMem Working Memory 三组件

    1. Summarization：定期对最近 N 条原始事件做 LLM 摘要
    2. Observation：从原始事件抽取结构化观察（市场异动/资金流向/技术指标突破）
    3. Reflection：基于摘要+观察生成阶段性反思（"市场情绪转空"等高层判断）
    """
    def __init__(self, max_size=200, llm_adapter=None): ...

    # 原始事件队列（保留现有 deque）
    def append(self, entry): ...
    def get_recent(self, n=20): ...

    # 三组件接口
    def summarize(self) -> str: ...         # 触发 LLM 摘要，缓存结果
    def observe(self) -> List[Dict]: ...    # 抽取结构化观察
    def reflect(self) -> str: ...           # 生成反思，写入 L3-Deep

    # 检索（含三组件输出 + RecallScorer 排序）
    def query(self, symbol=None, since=None) -> List[Dict]: ...
    def get_sentiment_baseline(self, symbol, window_days=30) -> float: ...
```

**LLM 调用**：复用 `stockquant/ai/service.py` litellm 封装，不引入新依赖。

#### B5. 管线四阶段完整化（合并旧版 DEPRECATED 能力）

##### B5.1 降噪环节增强（`pipeline/denoise.py`）

**现状**：3 步（temporal_filter / deduplicate / source_rank）
**增强**：合并旧版 `Denoiser` 的 L3 集成，扩展为 5 步

```
DenoiseStage.execute(articles):
  Step 1: temporal_filter（24h 默认，保留）           ← 已有
  Step 2: deduplicate（Jaccard ≥60%，保留）            ← 已有
  Step 3: source_rank（信源排序，保留）                ← 已有
  Step 4: l3_noise_filter（新增）                      ← 借鉴 FinMem
    - 查询 L3 记忆中"已知噪音模式"（标题党/营销号模板）
    - 过滤匹配噪音模式的文章
  Step 5: l3_disproved_filter（新增）                   ← 合并旧版
    - 查询 L3 中"已证伪事实"
    - 降权或过滤包含已证伪声明的文章
```

**参考**：旧版 `pipeline/denoiser.py` 的 L3 查询逻辑 + FinMem 分层记忆召回

##### B5.2 总结环节增强（`pipeline/summarize.py`）

**现状**：3 步（memory retrieval / build_summary / post_verify），**无 LLM**
**增强**：合并旧版 `Summarizer` 的 LLM 调用，扩展为 6 步

```
SummarizeStage.execute(filtered_articles):
  Step 1: memory_retrieval（L1/L2/L3 检索，保留）       ← 已有
  Step 2: prompt_constraint_inject（新增）               ← 合并旧版
    - 注入反幻觉 Prompt 约束（禁用"建议买入"等）
  Step 3: llm_summarize（新增）                          ← 合并旧版，借鉴 FinRobot CoT
    - 调用 AIService.chat() 生成摘要
    - Financial Chain-of-Thought：数据收集→筛选→趋势→异常→因果→结论
  Step 4: multi_level_summary（新增）                   ← 合并旧版
    - 按时效生成：会话级/日级/周级/月级摘要
  Step 5: five_step_verify（新增）                       ← 合并旧版
    - fact_check → source_check → consistency → cross_validation → confidence
  Step 6: memory_writeback（新增）                        ← 合并旧版
    - 写入 L2 短期记忆 + L3 长期记忆（带 tier 标识）
```

**参考**：旧版 `pipeline/summarizer.py` + FinRobot Financial CoT + 现有 `hallucination/corrector.py`

##### B5.3 升华环节增强（`pipeline/elevate.py`）

**现状**：多源融合（4 级置信度）
**增强**：合并旧版 `Elevator` 的推理链验证，扩展为 5 步

```
ElevateStage.execute(summary):
  Step 1: l3_retrieval（新增）                           ← 合并旧版
    - 从 L3 检索历史相似情境（用 RecallScorer 多因子召回）
  Step 2: multi_source_fusion（保留）                    ← 已有
    - source_count 0-4 级置信度
  Step 3: reasoning_chain_verify（新增）                  ← 合并旧版，借鉴 FINGROUND
    - 验证因果逻辑链完整性
    - 原子声明分解 + 类型路由（数值/时序/实体/比较/监管/计算）
  Step 4: cross_validation（新增）                       ← 合并旧版
    - 多源交叉验证关键声明
  Step 5: l3_writeback（新增）                           ← 合并旧版
    - 写入 L3 长期记忆 + 反思（带 importance_score）
    - 触发 WorkingMemory.reflect() 写入 L3-Deep
```

**参考**：旧版 `pipeline/elevator.py` + FINGROUND 原子声明分类

##### B5.4 删除旧版管线（DEPRECATED）

- 删除 `stockquant/ai/pipeline/denoiser.py`
- 删除 `stockquant/ai/pipeline/summarizer.py`
- 删除 `stockquant/ai/pipeline/elevator.py`
- 删除 `stockquant/ai/pipeline/orchestrator.py`（旧版 PipelineOrchestrator）

**注意**：删除前需确认无外部调用，先全局搜索 `from .pipeline.denoiser import` 等引用。

#### B6. 记忆系统增强（旧版文档 §3）

##### B6.1 压缩器接入 LLM（`memory/compressor.py`）

**现状**：[compressor.py#L141-L149](file:///d:/projects/StockQuant/stockquant/ai/memory/compressor.py#L141-L149) `_generate_summary` 仅截断 200 字
**增强**：调用 `AIService.chat()` 生成压缩摘要，写入 L3 时携带 importance_score 与 tier 字段

```python
async def _generate_summary(self, items: List[MemoryItem]) -> str:
    # 借鉴 FinMem 洞察压缩
    prompt = f"请将以下{len(items)}条记忆压缩为一段不超过200字的摘要..."
    response = await self._ai_service.chat(
        messages=[{"role": "user", "content": prompt}],
        model_preference="fast"  # 用快速模型降低成本
    )
    return response.content
```

##### B6.2 L3 支持 embedding fallback（`memory/l3_store.py`）

**现状**：L3 仅用 OpenAI `text-embedding-3-small`
**增强**：本地 embedding fallback（借鉴 FinMem 分层）

```python
async def _get_embedding(self, text: str) -> List[float]:
    try:
        return await self._openai_embedding(text)
    except Exception:
        # fallback to local sentence-transformers (all-MiniLM-L6-v2，已有)
        return self._local_embedding(text)
```

##### B6.3 噪音模式库（`memory/l3_store.py`）

```python
async def get_noise_patterns(self) -> List[str]:
    """查询已知噪音模式（标题党/营销号模板）"""

async def get_disproved_facts(self, symbol: str) -> List[str]:
    """查询已证伪事实"""
```

---

### Phase C：采集端补齐（旧版文档 §2）

#### C1. 新增 ResearchCollector

**新文件**：`stockquant/ai/collectors/research_collector.py`

**数据源**：东方财富研报（`akshare.stock_research_report_em`）、巨潮资讯研报
**写入层**：L3-Intermediate（period_type=quarterly）
**借鉴**：TradingAgents 基本面分析师 + FinRobot 数据采集层

```python
class ResearchCollector(BaseCollector):
    """券商研报采集器"""
    async def collect(self, symbols: List[str]) -> List[RawInfoItem]:
        # 1. AkShare 获取研报列表
        # 2. 解析研报标题/摘要/评级/目标价
        # 3. 封装为 RawInfoItem（type='research'）
```

#### C2. 新增 FinancialCollector

**新文件**：`stockquant/ai/collectors/financial_collector.py`

**数据源**：AkShare 财务数据（`akshare.stock_financial_report_sina`）、东方财富财务指标
**写入层**：L3-Deep（period_type=annual）

```python
class FinancialCollector(BaseCollector):
    """财务报表采集器"""
    async def collect(self, symbols: List[str]) -> List[RawInfoItem]:
        # 1. 获取最新季报关键指标（PE/PB/ROE/营收/净利润）
        # 2. 封装为 RawInfoItem（type='financial'）
        # 3. 结构化字段供反幻觉事实初筛使用
```

#### C3. 新增 ExchangeCollector

**新文件**：`stockquant/ai/collectors/exchange_collector.py`

**数据源**：上交所披露（`akshare.stock_sse_summary`）、深交所披露（`akshare.stock_szse_summary`）

#### C4. 修复 AlphaFeed SDK

**现状**：[news_collector.py](file:///d:/projects/StockQuant/stockquant/ai/collectors/news_collector.py) `_collect_alphafeed` 仅 `return []`
**修复**：
- 若 AlphaFeed SDK 可用：正确调用并解析
- 若不可用：降级到 AkShare（已有），但记录降级原因到审计日志

#### C5. 注册新采集器

**文件**：[orchestrator.py#L40-L44](file:///d:/projects/StockQuant/stockquant/ai/orchestrator.py#L40-L44)

```python
self._collectors: List[BaseCollector] = [
    NewsCollector(),
    AnnouncementCollector(),
    SocialCollector(),
    ResearchCollector(),      # 新增
    FinancialCollector(),     # 新增
    ExchangeCollector(),      # 新增
]
```

#### C6. FAKE_SOURCES 黑名单 + 变更检测

**文件**：`stockquant/ai/collectors/verifier.py`

```python
FAKE_SOURCES = {
    "fake-eastmoney", "fake-sina", "stock-tip-xxx",
    # 初始黑名单 + 运行时动态扩展
}

async def detect_source_change(self, source: str) -> bool:
    """检测数据源页面结构是否变更"""
    # 对比上次采集的响应结构，变更则触发告警
```

---

### Phase D：Decision-making 模块（F020→F025 桥接 + Profiling 注入）

#### D1. F020 洞察桥接 F025

**新文件**：`stockquant/ai/insights_bridge.py`

```python
class InsightsBridge:
    """F020 → F025 洞察桥接

    将 F020 的 elevated insights 转换为 F025 可消费的上下文：
    1. 按 symbol 聚类 insights
    2. 从 Memory 检索该 symbol 的三层历史记忆（用 RecallScorer 多因子召回）
    3. 调用 WorkingMemory.reflect() 生成阶段反思
    4. 组装为 DecisionContext 传给 F025
    """
    def build_context(self, symbol, insights, memory_system) -> DecisionContext: ...
```

**文件**：[pipeline_orchestrator.py#L74-L91](file:///d:/projects/StockQuant/stockquant/ai/pipeline_orchestrator.py#L74-L91)
**变更**：run() 末尾返回 insights 时，调用 InsightsBridge 构建上下文

#### D2. F025 evaluate() 接收 Profiling + Insights

**文件**：[decision_agent.py#L231-L286](file:///d:/projects/StockQuant/stockquant/ai/decision_agent.py#L231-L286)

**变更**：evaluate() 入参扩展：

```python
def evaluate(
    self,
    signal: Dict[str, Any],
    current_positions: Optional[Dict[str, Any]] = None,
    total_cash: float = 1000000.0,
    insights: Optional[List[Dict[str, Any]]] = None,     # 新增：F020 洞察
    user_profile: Optional["RiskProfile"] = None,       # 新增：风险偏好
    decision_context: Optional["DecisionContext"] = None,# 新增：完整上下文
) -> DecisionAdvice:
```

**SYSTEM_PROMPT 扩展**（[decision_agent.py#L76-L95](file:///d:/projects/StockQuant/stockquant/ai/decision_agent.py#L76-L95)）：

```
7. **风险偏好约束**：根据 user_profile 调整仓位上限、止损止盈
   - conservative: 仓位上限 5%，止损 3%，止盈 6%
   - neutral: 仓位上限 10%，止损 5%，止盈 10%
   - aggressive: 仓位上限 20%，止损 8%，止盈 20%
8. **洞察整合**：如果传入 insights，结合 F020 的市场洞察做综合判断
```

#### D3. AgentOrchestrator 串联

**文件**：`stockquant/ai/orchestrator.py`

**变更**：在现有 F024→F025 桥接之外，新增 F020→F025 桥接调用：

```python
# 现有：F024（指标）→ F025（决策）
# 新增：F020（信息处理）→ insights → F025
```

---

### Phase E：反幻觉增强（六类原子声明验证 + 多模型交叉验证）

#### E1. FINGROUND 六类原子声明验证

**新文件**：`stockquant/ai/hallucination/claim_verifier.py`
**修改文件**：`stockquant/ai/hallucination/checkpoints.py`

```python
class ClaimType(str, Enum):
    NUMERIC = "numeric"          # 数值型（营收/利润/PE 等）
    TEMPORAL = "temporal"        # 时间型（财报日期/事件日期）
    ENTITY_ATTR = "entity_attr"  # 实体属性（董事长/注册地）
    COMPARATIVE = "comparative"  # 比较型（同比/环比/排名）
    REGULATORY = "regulatory"    # 监管型（政策/法规）
    COMPUTATIONAL = "computational"  # 计算型（增长率/比率）

async def verify_claim(claim, claim_type, memory_system) -> ClaimVerification:
    """原子声明分解 + 类型路由验证：
    - 数值型：查询数据库验证（PE/价格/成交量）
    - 时序型：查询历史数据验证趋势
    - 实体属性：查询公司信息验证
    - 比较型：交叉查询比较
    - 监管型：查询公告验证
    - 计算型：公式重构验证
    """
```

#### E2. 多模型交叉验证

**新文件**：`stockquant/ai/hallucination/cross_validator.py`
**修改文件**：`stockquant/ai/hallucination/pipeline.py`

借鉴 AI.cc 研究（单模型 8.3% → 多模型 3.2% 幻觉率，降低 ~61%）

```python
async def multi_model_verify(claim: str) -> VerifyResult:
    """多模型交叉验证（利用现有 litellm 多 Provider）"""
    results = await asyncio.gather(
        self._verify_with_model(claim, "openai"),
        self._verify_with_model(claim, "anthropic"),
        self._verify_with_model(claim, "qwen"),
    )
    # 多数投票 + 分歧标记
    if len(set(results)) > 1:
        return VerifyResult(conflict=True, needs_human_review=True)
    return results[0]
```

---

### Phase F：工程化增强（旧版文档 §5）

#### F1. asyncio 自动调度器（不引入 APScheduler）

**新文件**：`stockquant/ai/scheduler.py`

```python
class PipelineScheduler:
    """基于 asyncio 的信息处理调度器"""
    async def start(self):
        # 定时采集任务（可配置：实时/分钟级/小时级/日级）
        asyncio.create_task(self._schedule_collect("realtime", interval=60))
        asyncio.create_task(self._schedule_collect("minute", interval=300))
        asyncio.create_task(self._schedule_collect("daily", hour=18))
```

**集成**：FastAPI 启动时启动调度器

#### F2. data_sources.yaml 配置化

**新文件**：`config/data_sources.yaml`

```yaml
collectors:
  news:
    enabled: true
    sources:
      - name: eastmoney
        priority: 1
        trust_score: 0.8
      - name: xueqiu
        priority: 2
        trust_score: 0.6
  research:
    enabled: true
    sources:
      - name: eastmoney_research
        priority: 1
  financial:
    enabled: true
    sources:
      - name: sina_financial
        priority: 1
  exchange:
    enabled: true
    sources:
      - name: sse
        priority: 1
      - name: szse
        priority: 1

scheduling:
  realtime:
    interval_seconds: 60
    collectors: [news, social]
  minute:
    interval_seconds: 300
    collectors: [announcement]
  daily:
    hour: 18
    collectors: [research, financial, exchange]
```

#### F3. 审计日志

**文件**：`stockquant/ai/collectors/base.py`

```python
class BaseCollector:
    async def _audit_log(self, action: str, source: str, result: str, count: int):
        """记录采集操作到审计日志"""
        # 写入数据库 audit_log 表
```

#### F4. 数据源变更检测

**文件**：`stockquant/ai/collectors/verifier.py`（已在 C6 覆盖）

---

## 4. 假设与决策

| # | 假设/决策 | 理由 |
|---|----------|------|
| 1 | 不引入新依赖 | 用户明确要求；litellm + pgvector + sentence-transformers + asyncio + FastAPI 已覆盖所有需求 |
| 2 | L3Memory 表通过 SQLAlchemy 自动建表 | 项目现有约定（[l3_store.py#L107-L113](file:///d:/projects/StockQuant/stockquant/ai/memory/l3_store.py#L107-L113)） |
| 3 | 不破坏现有 L1/L2 接口 | 向后兼容，MemorySystem 旧接口保留，新接口（add_intermediate/add_deep）追加 |
| 4 | Profiling 转换冷却期 7 天 | 防止风险偏好频繁抖动 |
| 5 | 多因子权重 α=0.5/β=0.3/γ=0.2 | FinMem 论文默认值，可在 config.yaml 配置 |
| 6 | WorkingMemory 三组件使用 LLM 调用 | 复用 `stockquant/ai/service.py`，不新建 LLM 客户端 |
| 7 | 删除旧版 DEPRECATED 文件 | 能力已合并到新版管线，避免双套代码维护 |
| 8 | Shallow 层复用 L2，不新建表 | L2 已是短期记忆，符合 FinMem 浅层定义 |
| 9 | 现有 `AIService`（litellm）可正常调用 LLM | 总结/压缩/验证全部复用 |
| 10 | pgvector 足以支撑当前规模向量检索 | 无需 chromadb |
| 11 | asyncio 定时任务可满足调度需求 | 无需 APScheduler |
| 12 | 现有 10+ 数据源通过 AkShare 可访问 | 研报/财报/交易所数据 |
| 13 | 不修改前端 UI | 本次仅增强后端 AI 模块 |

### 不在范围内
- 前端 UI 改动
- 新增外部依赖（chromadb/APScheduler/LangGraph/Kafka/Flink）
- 模型微调/训练
- 实盘交易对接

---

## 5. 文件变更清单

### 新建文件（15 个）

| # | 文件 | 说明 | 所属 Phase |
|---|------|------|-----------|
| 1 | `stockquant/ai/profiling/__init__.py` | Profiling 模块入口 | A2 |
| 2 | `stockquant/ai/profiling/risk_profile.py` | 风险偏好枚举 + 偏好参数 | A2 |
| 3 | `stockquant/ai/profiling/transition.py` | 动态转换规则 | A2 |
| 4 | `stockquant/ai/profiling/manager.py` | Profiling 统一接口 | A2 |
| 5 | `stockquant/ai/memory/recall_scorer.py` | FinMem 多因子召回评分器（~300 行） | B2 |
| 6 | `stockquant/ai/insights_bridge.py` | F020→F025 洞察桥接 | D1 |
| 7 | `stockquant/ai/collectors/research_collector.py` | 券商研报采集器 | C1 |
| 8 | `stockquant/ai/collectors/financial_collector.py` | 财报采集器 | C2 |
| 9 | `stockquant/ai/collectors/exchange_collector.py` | 交易所直连采集器 | C3 |
| 10 | `stockquant/ai/hallucination/claim_verifier.py` | 六类原子声明验证 | E1 |
| 11 | `stockquant/ai/hallucination/cross_validator.py` | 多模型交叉验证 | E2 |
| 12 | `stockquant/ai/scheduler.py` | asyncio 自动调度器 | F1 |
| 13 | `config/data_sources.yaml` | 数据源配置 | F2 |
| 14 | `tests/ai/memory/test_recall_scorer.py` | 多因子召回测试 | B2 |
| 15 | `tests/ai/profiling/test_risk_profile.py` | Profiling 测试 | A2 |

### 修改文件（18 个）

| # | 文件 | 修改内容 | 所属 Phase |
|---|------|---------|-----------|
| 1 | `stockquant/persistence/models.py` | UserModel + L3Memory 字段扩展、新增 UserProfileHistory | A1/B1 |
| 2 | `stockquant/ai/memory/working.py` | Working Memory 三组件重写 + RecallScorer 集成（tier=working） | B4 |
| 3 | `stockquant/ai/memory/l3_store.py` | tier 过滤 + RecallScorer 集成 + embedding fallback + 噪音模式库 | B2/B3/B6 |
| 4 | `stockquant/ai/memory/l2_store.py` | RecallScorer 集成（tier=shallow）+ 写入记录 source_weight/sentiment/scope | B2 |
| 5 | `stockquant/ai/memory/system.py` | 新增 add_intermediate/add_deep/search_by_layer | B3 |
| 6 | `stockquant/ai/memory/manager.py` | 跨层统一 RecallScorer 评分排序 | B2 |
| 7 | `stockquant/ai/memory/compressor.py` | 接入 LLM 摘要 + 写入 L3 携带 importance_score/tier | B6 |
| 8 | `stockquant/ai/pipeline/denoise.py` | +2 步（L3 噪音过滤 + 已证伪过滤） | B5.1 |
| 9 | `stockquant/ai/pipeline/summarize.py` | +3 步（LLM 总结 + 多级摘要 + 五步验证） | B5.2 |
| 10 | `stockquant/ai/pipeline/elevate.py` | +3 步（L3 检索 + 推理链验证 + 交叉验证） | B5.3 |
| 11 | `stockquant/ai/pipeline_orchestrator.py` | F020→F025 桥接 + 集成调度器 + 审计日志 | D1/F1/F3 |
| 12 | `stockquant/ai/decision_agent.py` | evaluate() 入参 + SYSTEM_PROMPT | D2 |
| 13 | `stockquant/ai/orchestrator.py` | 注册 3 个新采集器 + F020→F025 串联 | C5/D3 |
| 14 | `stockquant/ai/collectors/news_collector.py` | 修复 AlphaFeed stub | C4 |
| 15 | `stockquant/ai/collectors/verifier.py` | FAKE_SOURCES 黑名单 + 变更检测 | C6 |
| 16 | `stockquant/ai/collectors/base.py` | 审计日志接口 | F3 |
| 17 | `stockquant/ai/hallucination/checkpoints.py` | 新增原子声明验证检查点 | E1 |
| 18 | `stockquant/ai/hallucination/pipeline.py` | cross_validation 调用多模型 | E2 |

### 删除文件（4 个）

| 文件 | 原因 |
|------|------|
| `stockquant/ai/pipeline/denoiser.py` | DEPRECATED，能力已合并到新版 5 步 |
| `stockquant/ai/pipeline/summarizer.py` | DEPRECATED，能力已合并到新版 6 步 |
| `stockquant/ai/pipeline/elevator.py` | DEPRECATED，能力已合并到新版 5 步 |
| `stockquant/ai/pipeline/orchestrator.py` | DEPRECATED，使用新版编排器 |

---

## 6. 验证步骤

### 6.1 单元测试

```bash
# 新模块测试
pytest tests/ai/profiling/test_risk_profile.py -v
pytest tests/ai/memory/test_recall_scorer.py -v

# 现有测试回归（基线 754 passed / 11 skipped / 0 failed）
pytest tests/ai/ -v
```

### 6.2 集成测试

```python
# 验证 F020→F025 桥接
pipeline = InformationProcessingPipeline(memory=MemorySystem(), profiling=ProfilingManager())
result = pipeline.run(["sh600519"], sources=["news_searcher", "research", "financial"])
assert result["insights"]
assert result["decision_context"]  # 桥接到 F025

# 验证三因子召回
memory = MemorySystem()
memory.add_intermediate("sh600519", "Q3 营收同比+15%", period_type="quarterly", importance=0.8)
memory.add_deep("sh600519", "2024 年报披露分红方案", period_type="annual", importance=0.9)
results = memory.search_by_layer("茅台财报", layer="all", top_k=5)
assert any(r["tier"] == "intermediate" for r in results)
assert any(r["tier"] == "deep" for r in results)

# 验证 Profiling 动态转换
mgr = ProfilingManager()
mgr.update_profile("user1", RiskProfile.AGGRESSIVE)
mgr.evaluate_transition("user1", market_env="crash", recent_hit_rate=0.2)
assert mgr.get_profile("user1") == RiskProfile.NEUTRAL  # 暴跌后降级

# 验证四阶段管线完整化
pipeline = InformationProcessingPipeline(memory=MemorySystem())
result = pipeline.run(["sh600519"])
assert result["summary"]["llm_generated"]  # LLM 总结已生成
assert result["insights"][0]["reasoning_chain_verified"]  # 推理链已验证

# 验证反幻觉多模型交叉
from stockquant.ai.hallucination.cross_validator import multi_model_verify
result = await multi_model_verify("贵州茅台 2024 年营收同比增长 15%")
assert result.conflict is False or result.needs_human_review
```

### 6.3 全量回归

```bash
pytest tests/  # 必须 ≥ 754 passed
cd web && npm test  # vitest 必须 225 passed
```

### 6.4 配置验证

- 加载 `config/data_sources.yaml` 验证配置正确
- 验证调度器按配置触发采集
- 验证审计日志写入数据库

---

## 7. 实施顺序

1. **Phase A1-A3**：Profiling 数据模型 + 模块 + 迁移
2. **Phase B1**：L3Memory 表字段扩展（tier / period_type / importance_score / last_accessed_at）
3. **Phase B2**：FinMem 多因子召回子系统（recall_scorer.py 独立模块，约 300 行，含三因子数学模型 + 分层半衰期 + 多维重要性 + 权重可配置 + 可观测性）
4. **Phase B3**：L3Store tier 过滤 + RecallScorer 集成三层（L1/L2/L3）+ MemorySystem 新增分层接口
5. **Phase B4**：Working Memory 三组件（Summarization / Observation / Reflection）
6. **Phase B5.1-B5.3**：四阶段管线完整化（降噪 5 步 / 总结 6 步 / 升华 5 步）
7. **Phase B5.4**：删除 4 个 DEPRECATED 文件
8. **Phase B6**：MemoryManager 跨层统一评分 + compressor.py LLM 摘要 + L3 embedding fallback + 噪音模式库
9. **Phase C1-C6**：3 个新 Collector + AlphaFeed 修复 + FAKE_SOURCES + 变更检测
10. **Phase D1-D3**：F020→F025 桥接 + Profiling 注入
11. **Phase E1-E2**：六类声明验证 + 多模型交叉验证
12. **Phase F1-F4**：asyncio 调度器 + data_sources.yaml + 审计日志
13. 全量回归测试（pytest ≥ 754 passed、vitest 225 passed）
14. 更新 Product-Spec.md 与 CHANGELOG
