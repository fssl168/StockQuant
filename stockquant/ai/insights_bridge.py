# -*- coding: utf-8 -*-
"""F020 → F025 洞察桥接（Phase D1）

将 F020 信息处理管线的 elevated insights 转换为 F025 DecisionAgent 可消费的上下文。

FinMem 论文 §3.4 Decision-making 模块要求：
1. 按 symbol 聚类 insights
2. 从 Memory 检索该 symbol 的三层历史记忆（用 RecallScorer 多因子召回）
3. 调用 WorkingMemory.reflect() 生成阶段反思
4. 组装为 DecisionContext 传给 F025 DecisionAgent.evaluate()

设计原则：
- DecisionContext 是纯数据载体（dataclass），便于序列化与审计
- InsightsBridge 无状态，可重入；每次 build_context 都重新检索
- Profiling 不在此处注入（避免循环依赖），由 DecisionAgent 自行读取
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stockquant.ai.insights_bridge")


@dataclass
class DecisionContext:
    """F020 → F025 决策上下文

    聚合 F020 升华洞察 + 三层历史记忆 + WorkingMemory 反思，
    传递给 DecisionAgent.evaluate() 作为决策依据。

    Attributes:
        symbol: 标的代码（如 sh600519）
        insights: 当前批次 F020 升华后的洞察列表
        memory_retrieval: 三层历史记忆检索结果（RecallScorer 多因子召回排序）
        reflection: WorkingMemory 反思文本
        reflection_confidence: 反思置信度（low/medium/high）
        timestamp: 上下文构建时间（ISO 格式）
        metadata: 额外元数据（如来源统计、置信度均值等）
    """
    symbol: str = ""
    insights: List[Dict[str, Any]] = field(default_factory=list)
    memory_retrieval: List[Dict[str, Any]] = field(default_factory=list)
    reflection: str = ""
    reflection_confidence: str = "low"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


class InsightsBridge:
    """F020 → F025 洞察桥接器

    将 F020 信息处理管线的输出（elevated insights）转换为 F025 DecisionAgent
    可消费的 DecisionContext。

    用法::

        bridge = InsightsBridge()
        ctx = bridge.build_context(
            symbol="sh600519",
            insights=pipeline_result["insights"],
            memory_system=memory,
        )
        advice = decision_agent.evaluate(
            signal={"symbol": "sh600519", "direction": "BUY", "qty": 100},
            insights=ctx.insights,
            decision_context=ctx,
        )
    """

    def __init__(self, top_k_per_layer: int = 5) -> None:
        """
        Args:
            top_k_per_layer: 每层记忆检索返回的最大条目数（默认 5）
        """
        self._top_k = max(1, top_k_per_layer)

    def build_context(
        self,
        symbol: str,
        insights: List[Dict[str, Any]],
        memory_system: Optional[Any] = None,
    ) -> DecisionContext:
        """构建 F025 决策上下文

        Args:
            symbol: 标的代码
            insights: F020 升华后的洞察列表
            memory_system: MemorySystem 实例（可选，缺失时跳过记忆检索）

        Returns:
            DecisionContext 包含洞察 + 历史记忆 + 反思
        """
        # Step 1: 按 symbol 聚类 insights
        clustered = self._cluster_by_symbol(insights, symbol)

        # Step 2: 三层历史记忆检索（RecallScorer 多因子召回）
        memory_items: List[Dict[str, Any]] = []
        if memory_system is not None:
            memory_items = self._retrieve_memory(memory_system, symbol)

        # Step 3: WorkingMemory 反思
        reflection_text = ""
        reflection_confidence = "low"
        if memory_system is not None:
            try:
                reflection_text, reflection_confidence = self._reflect(
                    memory_system, symbol, clustered
                )
            except Exception as exc:
                logger.warning("WorkingMemory 反思失败: %s", exc)

        # Step 4: 组装上下文
        ctx = DecisionContext(
            symbol=symbol,
            insights=clustered,
            memory_retrieval=memory_items,
            reflection=reflection_text,
            reflection_confidence=reflection_confidence,
            metadata={
                "insight_count": len(clustered),
                "memory_count": len(memory_items),
                "source_symbols": list({i.get("symbol", symbol) for i in insights if isinstance(i, dict)}),
            },
        )
        logger.info(
            "InsightsBridge 构建上下文: symbol=%s, insights=%d, memory=%d, reflection=%s",
            symbol, len(clustered), len(memory_items), "yes" if reflection_text else "no",
        )
        return ctx

    # ── 内部实现 ──────────────────────────────────────────────

    @staticmethod
    def _cluster_by_symbol(
        insights: List[Dict[str, Any]],
        target_symbol: str,
    ) -> List[Dict[str, Any]]:
        """按 symbol 聚类 insights

        保留与 target_symbol 相关的洞察；无 symbol 字段的洞察也保留
        （视为市场级洞察）。
        """
        if not insights:
            return []
        clustered: List[Dict[str, Any]] = []
        for item in insights:
            if not isinstance(item, dict):
                continue
            item_symbol = item.get("symbol", "")
            # 无 symbol 字段（市场级）或匹配目标 symbol
            if not item_symbol or item_symbol == target_symbol:
                clustered.append(item)
        return clustered

    def _retrieve_memory(
        self,
        memory_system: Any,
        symbol: str,
    ) -> List[Dict[str, Any]]:
        """三层历史记忆检索

        优先调用 MemorySystem.search_by_layer(layer="all")（B3 多因子召回）；
        若方法不存在则降级到 search_long_term + search_short_term。
        """
        results: List[Dict[str, Any]] = []
        try:
            if hasattr(memory_system, "search_by_layer"):
                # B3: 跨层检索 + RecallScorer 排序
                items = memory_system.search_by_layer(
                    query=symbol,
                    layer="all",
                    top_k=self._top_k,
                )
                # 过滤 symbol 匹配（search_by_layer 返回所有 symbol，需要过滤）
                for item in items:
                    if isinstance(item, dict):
                        item_symbol = item.get("symbol", "")
                        if not item_symbol or item_symbol == symbol:
                            results.append(item)
                return results[: self._top_k * 2]
        except Exception as exc:
            logger.debug("search_by_layer 失败，降级到传统检索: %s", exc)

        # 降级：L3 + L2 分别检索
        try:
            if hasattr(memory_system, "search_long_term"):
                l3_items = memory_system.search_long_term(
                    symbol=symbol, limit=self._top_k
                )
                results.extend(l3_items)
        except Exception as exc:
            logger.debug("search_long_term 失败: %s", exc)

        try:
            if hasattr(memory_system, "search_short_term"):
                l2_items = memory_system.search_short_term(
                    symbol=symbol, limit=self._top_k
                )
                results.extend(l2_items)
        except Exception as exc:
            logger.debug("search_short_term 失败: %s", exc)

        return results[: self._top_k * 2]

    def _reflect(
        self,
        memory_system: Any,
        symbol: str,
        insights: List[Dict[str, Any]],
    ) -> tuple[str, str]:
        """调用 WorkingMemory.reflect() 生成阶段反思

        Args:
            memory_system: MemorySystem 实例
            symbol: 标的代码
            insights: 当前批次洞察（注入到 WorkingMemory 触发反思）

        Returns:
            (反思文本, 置信度) 元组；失败时返回 ("", "low")
        """
        l1 = getattr(memory_system, "l1", None)
        if l1 is None:
            return "", "low"

        # 将当前批次 insights 注入 WorkingMemory（如支持 append）
        try:
            for insight in insights[:5]:  # 限制注入数量，避免污染
                if isinstance(insight, dict):
                    content = insight.get("content") or insight.get("insight") or str(insight)
                    l1.append({
                        "content": content,
                        "symbol": symbol,
                        "type": "f020_insight",
                        "timestamp": datetime.now().isoformat(),
                    })
        except Exception as exc:
            logger.debug("WorkingMemory 注入失败: %s", exc)

        # 获取 L3Store 实例（用于 reflect 写入 L3-Deep）
        l3_store = getattr(memory_system, "l3", None)

        # 调用 reflect()
        try:
            reflection_text = l1.reflect(l3_store=l3_store, symbol=symbol)
            if not reflection_text or not reflection_text.strip():
                return "", "low"
            # 提取置信度（reflect 内部已写入 _reflections）
            confidence = "low"
            reflections = []
            if hasattr(l1, "reflections"):
                reflections = list(l1.reflections)
            if reflections:
                last = reflections[-1] if isinstance(reflections[-1], dict) else {}
                confidence = last.get("confidence", "low")
            return reflection_text.strip(), confidence
        except Exception as exc:
            logger.warning("WorkingMemory.reflect 调用失败: %s", exc)
            return "", "low"
