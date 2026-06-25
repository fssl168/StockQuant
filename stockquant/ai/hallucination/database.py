# -*- coding: utf-8 -*-
"""F020 幻觉数据库 — 记录幻觉事件 + 模式分析 + Prompt 优化建议"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from stockquant.persistence.models import (
    Base,
    HallucinationRecord,
    get_engine,
    init_db,
)
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger("stockquant.ai.hallucination.database")


class HallucinationDatabase:
    """幻觉数据库

    功能:
    1. record() — 记录幻觉事件
    2. query() — 查询记录
    3. analyze_patterns() — 分析幻觉模式
    4. optimize_prompt() — 生成 Prompt 优化建议
    """

    def __init__(self, db_url: str | None = None) -> None:
        self._engine = get_engine(db_url)
        init_db(db_url)  # 确保表已创建
        self._Session = sessionmaker(bind=self._engine)

    def record(self, entry: Dict[str, Any]) -> str:
        """记录一个幻觉事件

        Args:
            entry: 幻觉事件字典，包含:
                - agent: 来源 Agent 名称
                - input_summary: 输入摘要
                - hallucination_type: 幻觉类型
                - detection_method: 检测方法
                - original_output: 原始输出
                - corrected_output: 纠正后输出
                - confidence: 置信度
                - user_feedback: 用户反馈

        Returns:
            记录 ID
        """
        record_id = entry.get("id") or f"hall_{uuid.uuid4().hex[:12]}"

        record = HallucinationRecord(
            id=record_id,
            timestamp=entry.get("timestamp", datetime.now()),
            agent=entry.get("agent", ""),
            input_summary=entry.get("input_summary", ""),
            hallucination_type=entry.get("hallucination_type", ""),
            detection_method=entry.get("detection_method", ""),
            original_output=entry.get("original_output", ""),
            corrected_output=entry.get("corrected_output", ""),
            confidence=entry.get("confidence", 0.0),
            user_feedback=entry.get("user_feedback", ""),
        )

        with self._Session() as session:
            session.add(record)
            session.commit()

        logger.info("幻觉记录已保存: %s (agent=%s, type=%s)",
                     record_id, record.agent, record.hallucination_type)
        return record_id

    def query(
        self,
        agent: Optional[str] = None,
        hallucination_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """查询幻觉记录

        Args:
            agent: 按 Agent 名称过滤
            hallucination_type: 按幻觉类型过滤
            limit: 最大返回条数

        Returns:
            记录列表
        """
        with self._Session() as session:
            q = session.query(HallucinationRecord)

            if agent:
                q = q.filter(HallucinationRecord.agent == agent)
            if hallucination_type:
                q = q.filter(HallucinationRecord.hallucination_type == hallucination_type)

            q = q.order_by(HallucinationRecord.timestamp.desc()).limit(limit)
            records = q.all()

            return [self._record_to_dict(r) for r in records]

    def analyze_patterns(self) -> Dict[str, Any]:
        """分析幻觉模式

        返回:
            - type_distribution: 幻觉类型分布
            - high_frequency_triggers: 高频触发词
            - agent_differences: 各 Agent 幻觉差异
            - time_trend: 时间趋势
        """
        with self._Session() as session:
            records = session.query(HallucinationRecord).all()

        if not records:
            return {
                "type_distribution": {},
                "high_frequency_triggers": [],
                "agent_differences": {},
                "time_trend": {},
                "total_count": 0,
            }

        # 1. 类型分布
        type_counter = Counter(r.hallucination_type for r in records)
        type_distribution = dict(type_counter.most_common())

        # 2. 高频触发词（从 input_summary 中提取）
        word_counter: Counter = Counter()
        for r in records:
            if r.input_summary:
                words = r.input_summary.split()
                word_counter.update(words)
        high_frequency_triggers = [
            {"word": w, "count": c}
            for w, c in word_counter.most_common(20)
            if c >= 2 and len(w) >= 2
        ]

        # 3. 各 Agent 幻觉差异
        agent_stats: Dict[str, Dict[str, Any]] = {}
        agent_records: Dict[str, List[HallucinationRecord]] = {}
        for r in records:
            agent_records.setdefault(r.agent, []).append(r)

        for agent_name, agent_recs in agent_records.items():
            types = Counter(r.hallucination_type for r in agent_recs)
            avg_confidence = sum(r.confidence for r in agent_recs) / len(agent_recs)
            agent_stats[agent_name] = {
                "count": len(agent_recs),
                "top_types": dict(types.most_common(5)),
                "avg_confidence": round(avg_confidence, 3),
            }

        # 4. 时间趋势（按天统计）
        day_counter: Counter = Counter()
        for r in records:
            if r.timestamp:
                day_key = r.timestamp.strftime("%Y-%m-%d")
                day_counter[day_key] += 1
        time_trend = dict(sorted(day_counter.items()))

        return {
            "type_distribution": type_distribution,
            "high_frequency_triggers": high_frequency_triggers,
            "agent_differences": agent_stats,
            "time_trend": time_trend,
            "total_count": len(records),
        }

    def optimize_prompt(self) -> Dict[str, Any]:
        """基于模式分析生成 Prompt 优化建议

        Returns:
            - suggestions: 优化建议列表
            - priority_agents: 需要优先优化的 Agent
            - banned_patterns: 需要禁止的模式
        """
        patterns = self.analyze_patterns()

        suggestions: List[Dict[str, str]] = []
        banned_patterns: List[str] = []
        priority_agents: List[str] = []

        # 基于类型分布生成建议
        type_dist = patterns.get("type_distribution", {})
        for h_type, count in type_dist.items():
            if count >= 3:
                suggestion = self._type_to_suggestion(h_type, count)
                if suggestion:
                    suggestions.append(suggestion)

            # 收集需要禁止的模式
            banned = self._type_to_banned_pattern(h_type)
            if banned:
                banned_patterns.append(banned)

        # 基于高频触发词生成建议
        triggers = patterns.get("high_frequency_triggers", [])
        if triggers:
            top_words = ", ".join(t["word"] for t in triggers[:5])
            suggestions.append({
                "type": "trigger_warning",
                "description": f"高频触发词: {top_words}，建议在 prompt 中增加对这些词的约束",
                "priority": "medium",
            })

        # 基于各 Agent 差异确定优先优化对象
        agent_diff = patterns.get("agent_differences", {})
        for agent_name, stats in sorted(
            agent_diff.items(), key=lambda x: x[1].get("count", 0), reverse=True
        ):
            if stats.get("count", 0) >= 3:
                priority_agents.append(agent_name)
                suggestions.append({
                    "type": "agent_optimization",
                    "description": f"Agent '{agent_name}' 幻觉频次 {stats['count']}，"
                                   f"主要类型: {list(stats.get('top_types', {}).keys())}",
                    "priority": "high",
                })

        # 如果没有记录，返回通用建议
        if not suggestions:
            suggestions.append({
                "type": "general",
                "description": "暂无足够幻觉记录，建议持续监控",
                "priority": "low",
            })

        return {
            "suggestions": suggestions,
            "priority_agents": priority_agents,
            "banned_patterns": banned_patterns,
        }

    @staticmethod
    def _record_to_dict(record: HallucinationRecord) -> Dict[str, Any]:
        """ORM 记录转字典"""
        return {
            "id": record.id,
            "timestamp": record.timestamp.isoformat() if record.timestamp else None,
            "agent": record.agent,
            "input_summary": record.input_summary,
            "hallucination_type": record.hallucination_type,
            "detection_method": record.detection_method,
            "original_output": record.original_output,
            "corrected_output": record.corrected_output,
            "confidence": record.confidence,
            "user_feedback": record.user_feedback,
        }

    @staticmethod
    def _type_to_suggestion(hallucination_type: str, count: int) -> Optional[Dict[str, str]]:
        """根据幻觉类型生成优化建议"""
        type_suggestions = {
            "fabricated_data": {
                "type": "data_constraint",
                "description": "检测到虚构数据幻觉，建议在 prompt 中增加: '所有数值必须来自提供的原始数据，不得编造'",
                "priority": "high",
            },
            "unsupported_claim": {
                "type": "evidence_constraint",
                "description": "检测到无支撑断言，建议在 prompt 中增加: '每个结论必须附带来源依据'",
                "priority": "high",
            },
            "temporal_error": {
                "type": "time_constraint",
                "description": "检测到时间错误，建议在 prompt 中增加: '注意时间顺序，不得将未来事件当作已发生事件'",
                "priority": "medium",
            },
            "source_confusion": {
                "type": "source_constraint",
                "description": "检测到来源混淆，建议在 prompt 中增加: '明确标注每条信息的来源，不得将不同来源的信息混为一谈'",
                "priority": "medium",
            },
            "logical_fallacy": {
                "type": "logic_constraint",
                "description": "检测到逻辑谬误，建议在 prompt 中增加: '推理步骤之间必须有明确的因果连接'",
                "priority": "high",
            },
            "omission": {
                "type": "completeness_constraint",
                "description": "检测到信息遗漏，建议在 prompt 中增加: '如果关键信息缺失，明确标注而非忽略'",
                "priority": "medium",
            },
        }
        suggestion = type_suggestions.get(hallucination_type)
        if suggestion:
            suggestion = dict(suggestion)
            suggestion["description"] = f"[频次: {count}] {suggestion['description']}"
        return suggestion

    @staticmethod
    def _type_to_banned_pattern(hallucination_type: str) -> Optional[str]:
        """根据幻觉类型生成禁止模式"""
        banned = {
            "fabricated_data": "禁止编造具体数值和百分比",
            "unsupported_claim": "禁止无来源支撑的断言",
            "temporal_error": "禁止混淆时间线",
            "source_confusion": "禁止混淆信息来源",
            "logical_fallacy": "禁止逻辑跳跃",
            "omission": "禁止忽略关键缺失信息",
        }
        return banned.get(hallucination_type)

    def get_metrics(self, window_hours: int = 24) -> Dict[str, Any]:
        """计算 AI 可靠性指标（NFR009）

        返回:
            - total_checks: 时间窗口内检查总数
            - fact_pass_rate: 事实验证通过率
            - hallucination_rate: 幻觉检出率
            - consecutive_hallucinations: 连续幻觉次数
            - emergency_mode: 是否触发紧急模式（连续 ≥ 3 次幻觉）
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(hours=window_hours)
        records = self.query()

        recent = []
        for r in records:
            ts_str = r.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str) if ts_str else None
            except (ValueError, TypeError):
                ts = None
            if ts and ts >= cutoff:
                recent.append(r)

        total = len(recent)
        if total == 0:
            return {
                "window_hours": window_hours,
                "total_checks": 0,
                "fact_pass_rate": 1.0,
                "hallucination_rate": 0.0,
                "consecutive_hallucinations": 0,
                "emergency_mode": False,
            }

        # 幻觉记录（verified 为 False 或 hallucination_type 非空）
        hallucination_records = [
            r for r in recent
            if r.get("hallucination_type") and r.get("verified", True) is False
        ]
        n_hallucinations = len(hallucination_records)

        # 连续幻觉次数（从最近往前数）
        consecutive = 0
        for r in reversed(recent):
            if r.get("hallucination_type") and r.get("verified", True) is False:
                consecutive += 1
            else:
                break

        return {
            "window_hours": window_hours,
            "total_checks": total,
            "verified_count": total - n_hallucinations,
            "hallucination_count": n_hallucinations,
            "fact_pass_rate": round((total - n_hallucinations) / total, 4),
            "hallucination_rate": round(n_hallucinations / total, 4),
            "consecutive_hallucinations": consecutive,
            "emergency_mode": consecutive >= 3,
        }
