# -*- coding: utf-8 -*-
"""F020 FinMem 多因子召回评分器（B2 核心模块）

借鉴 FinMem 论文 §3.3 的多因子召回机制，构建**相关性 + 新鲜度 + 重要性**
三因子融合评分子系统，覆盖 L1/L2/L3 三层记忆。

数学模型：
    final_score = α · relevance + β · recency + γ · importance
    其中 α + β + γ = 1.0

设计原则：
1. 纯计算模块 — 不依赖具体存储后端，由各层 Store 在召回时调用
2. 分层半衰期 — 不同 tier 使用不同时间衰减率
3. 多维重要性 — 不同 tier 使用不同 importance 计算公式
4. 可观测性 — 每次评分返回 score_breakdown 便于调试
5. 自适应权重 — 根据查询场景动态调整三因子权重
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger("stockquant.ai.memory.recall_scorer")


# ─── 分层定义 ────────────────────────────────────────────────────────


# FinMem 论文 §3.3 表 2：分层半衰期（天）
TIER_HALF_LIFE_DAYS: Dict[str, int] = {
    "working": 1,      # L1 工作记忆：1 天（极短时效）
    "shallow": 3,       # 浅层-市场新闻：3 天（短时效，3 天后相关性减半）
    "intermediate": 90, # 中层-季报：90 天（季度周期，覆盖财报披露间隔）
    "deep": 365,       # 深层-年报：365 天（长期有效，年报每年才更新）
}


# 数据源权重表（FinMem 论文 §3.3 表 3）
SOURCE_WEIGHTS: Dict[str, float] = {
    "exchange_announcement": 1.0,    # 交易所公告
    "company_report":         0.95,  # 公司财报
    "research_report":        0.85,  # 券商研报
    "official_news":          0.80,  # 官方新闻
    "mainstream_media":       0.70,  # 主流媒体
    "social_media":           0.50,  # 社交媒体
    "unknown":                0.30,  # 未知来源
}


def get_source_weight(source: Optional[str]) -> float:
    """获取数据源权重，未识别的来源返回 unknown 权重"""
    if not source:
        return SOURCE_WEIGHTS["unknown"]
    return SOURCE_WEIGHTS.get(source, SOURCE_WEIGHTS["unknown"])


# ─── 权重配置 ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RecallWeights:
    """三因子权重配置

    默认值来自 FinMem 论文 §3.3（α=0.5, β=0.3, γ=0.2）。
    权重和必须等于 1.0，否则引发 ValueError。
    """
    relevance: float = 0.5
    recency: float = 0.3
    importance: float = 0.2

    def __post_init__(self) -> None:
        total = self.relevance + self.recency + self.importance
        if not math.isclose(total, 1.0, abs_tol=1e-6):
            raise ValueError(
                f"RecallWeights 权重和必须等于 1.0，当前值为 {total}"
                f"（relevance={self.relevance}, recency={self.recency}, importance={self.importance}）"
            )
        for name, value in [
            ("relevance", self.relevance),
            ("recency", self.recency),
            ("importance", self.importance),
        ]:
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"RecallWeights.{name} 必须在 [0, 1] 范围内，当前值: {value}")


# 查询场景预设权重（自适应权重用）
SCENE_WEIGHTS: Dict[str, RecallWeights] = {
    "default":       RecallWeights(relevance=0.5, recency=0.3, importance=0.2),
    "realtime":      RecallWeights(relevance=0.7, recency=0.2, importance=0.1),  # 实时交易侧重相关性
    "review":        RecallWeights(relevance=0.3, recency=0.2, importance=0.5),  # 复盘分析侧重重要性
    "historical":    RecallWeights(relevance=0.2, recency=0.6, importance=0.2),  # 历史回溯侧重新鲜度
}


# ─── 因子计算函数 ────────────────────────────────────────────────────


def relevance_score(
    item: Dict[str, Any],
    query_text: str,
    query_embedding: Optional[Sequence[float]] = None,
    tier: str = "shallow",
    semantic_score: Optional[float] = None,
) -> float:
    """计算相关性因子 [0, 1]

    Args:
        item: 记忆条目（必须包含 content 字段）
        query_text: 查询文本
        query_embedding: 查询向量（可选，用于向量相似度计算）
        tier: 记忆层级
        semantic_score: 预计算的语义相似度（如 pgvector cosine_distance 已归一化）
            如果提供，则跳过内部计算直接使用

    Returns:
        归一化的相关性评分 [0, 1]
    """
    # 如果调用方已预计算语义相似度（如 pgvector 余弦距离），直接归一化使用
    if semantic_score is not None:
        # cosine_distance ∈ [0, 2]，转换为相似度 ∈ [0, 1]
        return max(0.0, min(1.0, 1.0 - semantic_score))

    # L1 working / L2 shallow：使用关键词重叠率
    content = (item.get("content") or "").lower()
    query_lower = (query_text or "").lower()
    if not content or not query_lower:
        return 0.0

    # 关键词重叠率（Jaccard 近似）
    content_tokens = set(content.split())
    query_tokens = set(query_lower.split())
    if not query_tokens:
        return 0.0
    overlap = len(content_tokens & query_tokens) / len(query_tokens)

    # 加入来源权重调制
    source = item.get("source") or item.get("source_type")
    source_w = get_source_weight(source)

    # 关键词重叠 0.7 + 来源权重 0.3
    return max(0.0, min(1.0, 0.7 * overlap + 0.3 * source_w))


def recency_score(
    timestamp_iso: Optional[str],
    tier: str,
    last_accessed_at: Optional[str] = None,
    now: Optional[datetime] = None,
) -> float:
    """计算新鲜度因子 — 分层指数衰减

    recency = 0.5 ^ (age_days / half_life_days)

    分层半衰期（FinMem 论文 §3.3 表 2）：
        - working:      1 天   （L1 工作记忆极短时效）
        - shallow:      3 天   （市场新闻短时效）
        - intermediate: 90 天 （季报季度周期）
        - deep:         365 天 （年报长期有效）

    特殊处理：
        - 如果 last_accessed_at 存在，取 max(timestamp, last_accessed_at) 作为基准
          （访问会"刷新"记忆，借鉴人类记忆的提取强化效应）
        - 时间戳缺失返回 0.0
    """
    if not timestamp_iso:
        return 0.0

    now = now or datetime.now()
    try:
        ts = datetime.fromisoformat(timestamp_iso)
    except (ValueError, TypeError):
        return 0.0

    # 取 max(timestamp, last_accessed_at) 作为基准时间
    base_ts = ts
    if last_accessed_at:
        try:
            accessed = datetime.fromisoformat(last_accessed_at)
            if accessed > base_ts:
                base_ts = accessed
        except (ValueError, TypeError):
            pass

    age_days = (now - base_ts).total_seconds() / 86400.0
    if age_days < 0:
        # 时间戳在未来（数据错误），按当前时间处理
        age_days = 0.0

    half_life = TIER_HALF_LIFE_DAYS.get(tier, 30)
    return 0.5 ** (age_days / half_life)


def importance_score(item: Dict[str, Any], tier: str) -> float:
    """计算重要性因子 — 分层多维加权

    分层计算公式（FinMem 论文 §3.3）：

    - shallow (新闻):
        importance = 0.4·source_weight + 0.3·|sentiment| + 0.3·scope
        scope: 全市场=1.0, 行业=0.7, 个股=0.4

    - intermediate (季报):
        importance = 0.5·event_weight + 0.5·|metric_change_pct|
        event_weight: 业绩预增=1.0, 业绩预减=0.9, 分红=0.7, 高管变动=0.6, 其他=0.3

    - deep (年报):
        importance = 0.6·key_event_count_normalized + 0.4·is_core_holding
        key_event_count 归一化: min(event_count / 10, 1.0)

    - working (L1):
        importance = item.importance_score 字段（如果存在），否则 0.5

    Returns:
        归一化重要性 [0, 1]
    """
    if tier == "shallow":
        source_w = get_source_weight(item.get("source") or item.get("source_type"))
        sentiment = float(item.get("sentiment_score", 0.0) or 0.0)
        sentiment_abs = min(abs(sentiment), 1.0)

        scope = item.get("scope", "individual")
        scope_score = {"market": 1.0, "industry": 0.7, "individual": 0.4}.get(scope, 0.4)

        return max(0.0, min(1.0, 0.4 * source_w + 0.3 * sentiment_abs + 0.3 * scope_score))

    if tier == "intermediate":
        # 事件类型权重
        event_type = item.get("event_type", "other")
        event_weights = {
            "profit_warning_up": 1.0,    # 业绩预增
            "profit_warning_down": 0.9,  # 业绩预减
            "dividend":          0.7,    # 分红
            "management_change": 0.6,    # 高管变动
            "other":             0.3,
        }
        event_w = event_weights.get(event_type, 0.3)

        # 财务指标变动幅度
        metric_change = float(item.get("metric_change_pct", 0.0) or 0.0)
        metric_abs = min(abs(metric_change), 1.0)

        return max(0.0, min(1.0, 0.5 * event_w + 0.5 * metric_abs))

    if tier == "deep":
        # 年度关键事件数
        event_count = int(item.get("key_event_count", 0) or 0)
        event_normalized = min(event_count / 10.0, 1.0)

        # 是否核心标的
        is_core = 1.0 if item.get("is_core_holding") else 0.0

        return max(0.0, min(1.0, 0.6 * event_normalized + 0.4 * is_core))

    if tier == "working":
        # L1 工作记忆：使用条目自带的 importance_score，否则默认 0.5
        return float(item.get("importance_score", 0.5) or 0.5)

    # 未知 tier：使用条目已有的 importance_score 字段（向后兼容）
    return float(item.get("importance_score", 0.5) or 0.5)


# ─── 评分结果数据类 ──────────────────────────────────────────────────


@dataclass
class ScoreBreakdown:
    """单条记忆的评分明细 — 用于可观测性"""
    item_id: str
    final_score: float
    relevance: float
    recency: float
    importance: float
    weights_used: Dict[str, float]
    tier: str
    age_days: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "final_score": self.final_score,
            "score_breakdown": {
                "relevance": self.relevance,
                "recency": self.recency,
                "importance": self.importance,
                "weights_used": self.weights_used,
            },
            "tier": self.tier,
            "age_days": self.age_days,
        }


# ─── RecallScorer 主类 ──────────────────────────────────────────────


class RecallScorer:
    """FinMem 多因子召回评分器

    用法：
        scorer = RecallScorer()  # 默认权重 α=0.5/β=0.3/γ=0.2
        scored = scorer.rank(items, query="茅台财报", tier="shallow", top_k=10)
        for item, breakdown in scored:
            print(f"{breakdown.item_id}: {breakdown.final_score:.3f}")
            print(f"  详情: {breakdown.to_dict()}")

    跨层用法（MemoryManager）：
        # 各层独立评分后，跨层用 final_score 统一排序
        l1_results = scorer.rank(l1_items, query, tier="working", top_k=5)
        l2_results = scorer.rank(l2_items, query, tier="shallow", top_k=5)
        l3_results = scorer.rank(l3_items, query, tier="intermediate", top_k=5)
        all_results = l1_results + l2_results + l3_results
        all_results.sort(key=lambda x: x[1].final_score, reverse=True)
    """

    def __init__(
        self,
        weights: Optional[RecallWeights] = None,
        scene: str = "default",
    ) -> None:
        """
        Args:
            weights: 三因子权重；为 None 时使用 scene 对应的预设权重
            scene: 查询场景（default/realtime/review/historical）
        """
        if weights is not None:
            self._weights = weights
        else:
            self._weights = SCENE_WEIGHTS.get(scene, SCENE_WEIGHTS["default"])
        self._scene = scene

    @property
    def weights(self) -> RecallWeights:
        return self._weights

    def score(
        self,
        item: Dict[str, Any],
        query_text: str = "",
        query_embedding: Optional[Sequence[float]] = None,
        tier: str = "shallow",
        semantic_score: Optional[float] = None,
        now: Optional[datetime] = None,
    ) -> ScoreBreakdown:
        """对单条记忆评分，返回明细"""
        rel = relevance_score(
            item, query_text, query_embedding, tier, semantic_score
        )

        timestamp_iso = item.get("timestamp")
        last_accessed = item.get("last_accessed_at")
        rec = recency_score(timestamp_iso, tier, last_accessed, now)

        imp = importance_score(item, tier)

        final = (
            self._weights.relevance * rel
            + self._weights.recency * rec
            + self._weights.importance * imp
        )

        # 计算 age_days（仅用于可观测性）
        age_days = 0.0
        if timestamp_iso:
            try:
                ts = datetime.fromisoformat(timestamp_iso)
                age_days = ((now or datetime.now()) - ts).total_seconds() / 86400.0
            except (ValueError, TypeError):
                pass

        item_id = str(item.get("id", id(item)))
        return ScoreBreakdown(
            item_id=item_id,
            final_score=final,
            relevance=rel,
            recency=rec,
            importance=imp,
            weights_used={
                "relevance": self._weights.relevance,
                "recency": self._weights.recency,
                "importance": self._weights.importance,
            },
            tier=tier,
            age_days=age_days,
        )

    def rank(
        self,
        items: List[Dict[str, Any]],
        query: str = "",
        tier: str = "shallow",
        top_k: int = 10,
        query_embedding: Optional[Sequence[float]] = None,
        now: Optional[datetime] = None,
    ) -> List[tuple[Dict[str, Any], ScoreBreakdown]]:
        """对一批记忆排序，返回 top_k 条目及其评分明细

        Returns:
            [(item, breakdown), ...] 按 final_score 降序排列
        """
        if not items:
            return []

        scored = []
        for item in items:
            breakdown = self.score(
                item, query, query_embedding, tier, now=now
            )
            scored.append((item, breakdown))

        scored.sort(key=lambda x: x[1].final_score, reverse=True)
        return scored[:top_k]

    def explain(
        self,
        item: Dict[str, Any],
        query: str,
        tier: str,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """解释单条记忆的评分（用于调试/UI 展示）"""
        breakdown = self.score(item, query, tier=tier, now=now)
        return breakdown.to_dict()

    def adaptive_weights(self, query_context: str) -> RecallWeights:
        """根据查询场景动态调整权重

        Args:
            query_context: 场景标识
                - "realtime": 实时交易场景，侧重相关性
                - "review": 复盘分析场景，侧重重要性
                - "historical": 历史回溯场景，侧重新鲜度
                - "default": 默认权重

        Returns:
            对应场景的 RecallWeights
        """
        return SCENE_WEIGHTS.get(query_context, SCENE_WEIGHTS["default"])

    def with_weights(self, weights: RecallWeights) -> "RecallScorer":
        """返回一个新的 RecallScorer，使用指定权重（不变性）"""
        return RecallScorer(weights=weights, scene=self._scene)

    def with_scene(self, scene: str) -> "RecallScorer":
        """返回一个新的 RecallScorer，使用指定场景的预设权重"""
        return RecallScorer(scene=scene)


# ─── 便利函数 ────────────────────────────────────────────────────────


def rank_items(
    items: List[Dict[str, Any]],
    query: str = "",
    tier: str = "shallow",
    top_k: int = 10,
    scene: str = "default",
) -> List[Dict[str, Any]]:
    """便利函数：对一批记忆排序，返回 top_k 条目（不带评分明细）

    Args:
        items: 候选记忆条目列表
        query: 查询文本
        tier: 记忆层级（working/shallow/intermediate/deep）
        top_k: 返回的最大条目数
        scene: 查询场景

    Returns:
        排序后的记忆条目列表（按 final_score 降序）
    """
    scorer = RecallScorer(scene=scene)
    scored = scorer.rank(items, query=query, tier=tier, top_k=top_k)
    # 附带 final_score 字段，便于调用方使用
    result = []
    for item, breakdown in scored:
        enriched = {**item, "_final_score": breakdown.final_score, "_score_breakdown": breakdown.to_dict()}
        result.append(enriched)
    return result
