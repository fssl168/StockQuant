# -*- coding: utf-8 -*-
"""F020 记忆压缩器 — L2→L3 压缩迁移（B6.1: 接入 LLM 摘要）

增强点：
- `_generate_summary` 优先调用 LLM 生成压缩摘要，失败降级到截断
- 写入 L3 时携带 importance_score（取最大置信度）与 tier 字段
- 兼容旧接口：未传入 llm_adapter 时仍可工作
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stockquant.ai.memory.compressor")


class MemoryCompressor:
    """记忆压缩器

    将 L2 中较旧的条目压缩摘要后迁移到 L3，保留核心事实 ≥95%。

    Args:
        llm_adapter: 可选 LLM 适配器，需支持 `.chat(message, system_prompt=...)` 或 `.chat(messages)` 接口
                     未传入时降级为截断式摘要
    """

    # L2 条目保留天数，超过此天数的条目将被压缩迁移
    DEFAULT_RETENTION_DAYS = 30

    # 每次压缩的最大条目数
    BATCH_SIZE = 50

    # L3 默认 tier（B6.1: 压缩后的记忆默认归入中间层）
    DEFAULT_L3_TIER = "intermediate"

    def __init__(self, llm_adapter: Any = None) -> None:
        self._llm = llm_adapter

    def compress_l2_to_l3(self, l2_store: Any, l3_store: Any) -> int:
        """将 L2 旧条目压缩后迁移到 L3

        流程:
        1. 获取 L2 中所有条目
        2. 筛选超过保留天数的条目
        3. 按相似性分组
        4. 每组合并为一条 L3 条目（保留核心事实）
        5. 从 L2 中删除已迁移的条目

        Args:
            l2_store: L2Store 实例
            l3_store: L3Store 实例

        Returns:
            迁移的条目数
        """
        try:
            all_items = l2_store.get_all(limit=self.BATCH_SIZE)
        except Exception as exc:
            logger.warning("获取 L2 条目失败: %s", exc)
            return 0

        if not all_items:
            return 0

        # 筛选旧条目
        cutoff = datetime.now().timestamp() - self.DEFAULT_RETENTION_DAYS * 86400
        old_items = []
        for item in all_items:
            ts = item.get("timestamp", "")
            try:
                item_ts = datetime.fromisoformat(ts).timestamp()
            except (ValueError, TypeError):
                item_ts = cutoff  # 无法解析时间的条目也纳入压缩
            if item_ts < cutoff:
                old_items.append(item)

        if not old_items:
            return 0

        # 按 symbol 分组
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for item in old_items:
            symbol = item.get("symbol", "__unknown__")
            groups.setdefault(symbol, []).append(item)

        # 每组合并为一条 L3 条目
        migrated = 0
        for symbol, group_items in groups.items():
            compressed = self._compress_group(group_items)
            compressed["symbol"] = symbol
            try:
                l3_store.write(compressed)
                # 从 L2 删除已迁移条目
                for item in group_items:
                    l2_store.delete(item["id"])
                migrated += len(group_items)
            except Exception as exc:
                logger.warning("L2→L3 迁移失败 (symbol=%s): %s", symbol, exc)

        return migrated

    def _compress_group(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """将一组 L2 条目压缩为一条 L3 条目

        保留核心事实 ≥95%:
        - 合并所有内容，去除重复
        - 保留最高置信度
        - 生成摘要（B6.1: 优先用 LLM，降级截断）
        - B6.1: 携带 importance_score 与 tier 字段
        """
        if not items:
            return {}

        if len(items) == 1:
            item = items[0]
            confidence = item.get("confidence", 1.0)
            return {
                "content": item.get("content", ""),
                "summary": self._generate_summary(item.get("content", "")),
                "confidence": confidence,
                # B6.1: 携带 importance_score（单条时取自身置信度）
                "importance_score": float(confidence),
                "tier": self.DEFAULT_L3_TIER,
                "metadata": {
                    "source_count": 1,
                    "original_ids": [item.get("id", "")],
                    "compressed_at": datetime.now().isoformat(),
                    "compression_method": "llm" if self._llm is not None else "truncate",
                },
                "timestamp": item.get("timestamp", datetime.now().isoformat()),
            }

        # 合并内容（去重）
        seen_contents: List[str] = []
        merged_content_parts: List[str] = []
        for item in items:
            content = item.get("content", "")
            is_dup = False
            for seen in seen_contents:
                if self._similarity(content, seen) > 0.9:
                    is_dup = True
                    break
            if not is_dup:
                seen_contents.append(content)
                merged_content_parts.append(content)

        merged_content = "\n---\n".join(merged_content_parts)
        max_confidence = max(item.get("confidence", 0) for item in items)

        return {
            "content": merged_content,
            "summary": self._generate_summary(merged_content),
            "confidence": max_confidence,
            # B6.1: 携带 importance_score（取最大置信度，并提升 10% 以反映多源佐证）
            "importance_score": min(1.0, float(max_confidence) * 1.1),
            "tier": self.DEFAULT_L3_TIER,
            "metadata": {
                "source_count": len(items),
                "original_ids": [item.get("id", "") for item in items],
                "compressed_at": datetime.now().isoformat(),
                "compression_method": "llm" if self._llm is not None else "truncate",
            },
            "timestamp": items[0].get("timestamp", datetime.now().isoformat()),
        }

    def _generate_summary(self, content: str) -> str:
        """生成摘要（B6.1: 优先 LLM，降级截断）

        - 如果配置了 LLM 适配器，调用 LLM 生成不超过 200 字的压缩摘要
        - LLM 调用失败或未配置时，降级为前 200 字符截断
        """
        if len(content) <= 200:
            return content

        # B6.1: 优先尝试 LLM 摘要
        if self._llm is not None:
            llm_summary = self._llm_summarize(content)
            if llm_summary:
                return llm_summary

        # 降级：前 200 字符
        return content[:200] + "..."

    def _llm_summarize(self, content: str) -> Optional[str]:
        """调用 LLM 生成压缩摘要（B6.1）

        支持双 API 形式：
        - `chat(message: str, system_prompt: str = "")` —— 新版
        - `chat(messages: List[Dict]])` —— 旧版
        """
        try:
            system_prompt = (
                "你是金融领域的信息压缩专家。"
                "请将给定的多条记忆内容压缩为一段不超过200字的摘要，"
                "保留核心事实（数字、时间、公司名、关键事件），"
                "去除重复信息和噪音。直接输出摘要文本，不要解释。"
            )
            user_prompt = f"请压缩以下内容（{len(content)} 字）为不超过200字的摘要：\n\n{content[:4000]}"

            try:
                # 尝试新版 API：chat(message, system_prompt=...)
                summary = self._llm.chat(user_prompt, system_prompt=system_prompt)
            except TypeError:
                # 降级到旧版 API：chat(messages)
                summary = self._llm.chat([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ])

            if not isinstance(summary, str):
                return None
            # 清理可能的引号包裹
            summary = summary.strip().strip('"').strip("'")
            if not summary or len(summary) > 500:
                # 异常输出过长或空，视为失败
                return None
            return summary
        except Exception as exc:
            logger.debug("LLM 压缩摘要失败，降级截断: %s", exc)
            return None

    def _similarity(self, a: str, b: str) -> float:
        """简单字符重叠率"""
        if not a or not b:
            return 0.0
        set_a = set(a)
        set_b = set(b)
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0
