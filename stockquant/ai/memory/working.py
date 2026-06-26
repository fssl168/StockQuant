# -*- coding: utf-8 -*-
"""F020 L1 工作记忆 — FinMem Working Memory 三组件（B4 重写）

借鉴 FinMem 论文 §3.2 的 Working Memory 设计，包含三个组件：

1. **Summarization（摘要）**：定期对最近 N 条原始事件做 LLM 摘要，
   生成会话级/日级摘要，缓存供后续检索。

2. **Observation（观察）**：从原始事件抽取结构化观察，
   包括市场异动、资金流向、技术指标突破三类信号。

3. **Reflection（反思）**：基于摘要 + 观察生成阶段性反思，
   如"市场情绪转空"、"板块轮动加速"等高层判断，写入 L3-Deep。

设计原则：
- 保留现有 deque 接口（append/get_recent/query/get_sentiment_baseline/clear）
- 三组件为可选功能：未传 llm_adapter 时降级为基础工作记忆
- LLM 调用复用 stockquant.ai.service.AIService，不引入新依赖
- RecallScorer 集成（tier=working）用于排序检索结果
"""
from __future__ import annotations

import json
import logging
import threading
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stockquant.ai.memory.working")


# ─── Prompt 模板 ─────────────────────────────────────────────────────


_SUMMARIZE_PROMPT = """你是一位资深的 A 股市场分析师。请对以下最近的市场事件做摘要。

要求：
1. 用 3-5 句话概括核心信息
2. 突出影响价格走势的关键因素
3. 区分事实（数据/公告）与市场情绪
4. 严格基于给定事件，不要编造未提及的信息

事件列表（按时间倒序）：
{events}

输出格式：纯文本摘要，不超过 200 字。
"""

_OBSERVE_PROMPT = """你是一位量化研究员。请从以下市场事件中抽取结构化观察信号。

事件列表：
{events}

请抽取以下三类信号：
1. **market_anomaly（市场异动）**：突然放量、涨跌停、异动板块
2. **capital_flow（资金流向）**：北向资金、主力资金、融资融券变动
3. **technical_breakout（技术突破）**：突破关键均线、量价配合、形态完成

输出 JSON 数组，每个元素格式：
{{
  "type": "market_anomaly|capital_flow|technical_breakout",
  "symbol": "标的代码或板块名",
  "direction": "bullish|bearish|neutral",
  "strength": 0.0-1.0,
  "description": "一句话描述",
  "evidence": "事件 id 或内容片段"
}}

如无信号返回 []。
"""

_REFLECT_PROMPT = """你是一位资深策略分析师。请基于以下摘要与观察生成阶段性反思。

摘要：
{summary}

观察：
{observations}

要求：
1. 提炼出 1-2 条高层判断（如"市场情绪转空"、"板块轮动加速"）
2. 给出判断的依据（来自摘要或观察）
3. 标注判断的置信度（low/medium/high）
4. 不要给出具体买卖建议（合规要求）

输出格式：
判断：<高层判断>
依据：<依据描述>
置信度：<low|medium|high>
"""


# ─── WorkingMemory 主类 ───────────────────────────────────────────────


class WorkingMemory:
    """FinMem Working Memory 三组件

    L1 工作记忆：内存中存储最近 N 条事件，
    叠加 Summarization/Observation/Reflection 三组件输出。

    三组件输出存储为：
        - self._summary: 最新摘要文本（dict: timestamp → summary）
        - self._observations: 观察列表（List[Dict]）
        - self._reflections: 反思列表（List[Dict]）
    """

    # 摘要触发阈值：累计多少条新事件后触发一次摘要
    SUMMARIZE_BATCH_SIZE = 20
    # 单次摘要回溯的最近事件数
    SUMMARIZE_LOOKBACK = 50

    def __init__(
        self,
        max_size: int = 200,
        llm_adapter: Optional[Any] = None,
    ) -> None:
        """
        Args:
            max_size: 原始事件队列最大容量
            llm_adapter: AIService 实例或 duck-typed 对象（.chat(msg, sys) -> str）
                         为 None 时三组件降级为 stub（不调用 LLM）
        """
        self._max_size = max_size
        self._entries: deque[Dict[str, Any]] = deque(maxlen=max_size)
        self._lock = threading.Lock()

        # B4: 三组件缓存
        self._summary: Optional[str] = None              # 最新摘要文本
        self._summary_at: Optional[str] = None           # 摘要生成时间
        self._observations: List[Dict[str, Any]] = []    # 结构化观察列表
        self._reflections: List[Dict[str, Any]] = []     # 阶段性反思列表

        # 自上次摘要以来的新事件计数
        self._new_since_summary = 0

        # LLM 适配器（AIService 或兼容 .chat 接口的对象）
        self._llm = llm_adapter
        # 兼容 RecallScorer（tier=working）
        try:
            from .recall_scorer import RecallScorer
            self._scorer = RecallScorer(scene="realtime")
        except ImportError:
            self._scorer = None

    # ── 原始事件队列接口（保留现有行为） ──────────────────────────────

    def append(self, entry: Dict[str, Any]) -> None:
        """追加一条原始事件"""
        with self._lock:
            entry.setdefault("timestamp", datetime.now().isoformat())
            # B4: 默认 importance_score（RecallScorer working tier 使用）
            entry.setdefault("importance_score", 0.5)
            self._entries.append(entry)
            self._new_since_summary += 1

    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        """获取最近 N 条事件（按时间倒序，最新的在前）"""
        with self._lock:
            return list(self._entries)[-n:]

    def query(
        self,
        symbol: Optional[str] = None,
        since: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """按 symbol/since 过滤检索

        B4 增强：合并三组件输出（summary/observations/reflections）
        """
        with self._lock:
            results = list(self._entries)
        if symbol:
            results = [e for e in results if e.get("symbol") == symbol]
        if since:
            results = [e for e in results if e.get("timestamp", "") >= since]

        # B4: 合并三组件输出
        if self._summary:
            results.append({
                "type": "summary",
                "component": "summarization",
                "content": self._summary,
                "timestamp": self._summary_at or datetime.now().isoformat(),
                "importance_score": 0.7,
            })
        for obs in self._observations:
            # 保留 observation 原始 type 字段（market_anomaly/capital_flow/technical_breakout）
            # 用 component 字段标识来自 WorkingMemory 三组件
            merged = {**obs}
            merged.setdefault("type", "observation")
            merged["component"] = "observation"
            results.append(merged)
        for refl in self._reflections:
            merged = {**refl}
            merged.setdefault("type", "reflection")
            merged["component"] = "reflection"
            results.append(merged)

        return results

    def get_sentiment_baseline(self, symbol: str, window_days: int = 30) -> float:
        """获取某标的的情绪基线（最近 N 天的平均情绪分）"""
        entries = self.query(symbol=symbol)
        sentiments = [e.get("sentiment", 0) for e in entries if "sentiment" in e]
        if not sentiments:
            return 0.0
        return sum(sentiments) / len(sentiments)

    def clear(self) -> None:
        """清空所有记忆（包括三组件缓存）"""
        with self._lock:
            self._entries.clear()
            self._summary = None
            self._summary_at = None
            self._observations.clear()
            self._reflections.clear()
            self._new_since_summary = 0

    # ── B4: 三组件接口 ────────────────────────────────────────────────

    def summarize(self, force: bool = False) -> str:
        """触发 LLM 摘要（Summarization 组件）

        对最近 SUMMARIZE_LOOKBACK 条原始事件做摘要，结果缓存到 self._summary。
        若自上次摘要以来新事件数 < SUMMARIZE_BATCH_SIZE 且 force=False，返回上次摘要。

        Args:
            force: 是否强制重新摘要（忽略缓存）

        Returns:
            摘要文本（如 LLM 不可用则返回降级文本摘要）
        """
        if (
            not force
            and self._summary
            and self._new_since_summary < self.SUMMARIZE_BATCH_SIZE
        ):
            return self._summary

        events = self.get_recent(n=self.SUMMARIZE_LOOKBACK)
        if not events:
            return self._summary or ""

        # LLM 不可用时降级：拼接前 N 条事件的简短描述
        if self._llm is None:
            summary = self._summarize_fallback(events)
        else:
            try:
                events_text = self._format_events_for_prompt(events)
                prompt = _SUMMARIZE_PROMPT.format(events=events_text)
                summary = self._llm.chat(prompt, system_prompt="你是市场摘要助手。")
                if not summary or not summary.strip():
                    summary = self._summarize_fallback(events)
            except Exception as exc:
                logger.warning("LLM 摘要失败，降级文本拼接: %s", exc)
                summary = self._summarize_fallback(events)

        with self._lock:
            self._summary = summary
            self._summary_at = datetime.now().isoformat()
            self._new_since_summary = 0

        logger.info("WorkingMemory 摘要生成完成（%d 字）", len(summary))
        return summary

    def observe(self, force: bool = False) -> List[Dict[str, Any]]:
        """抽取结构化观察（Observation 组件）

        从最近事件中抽取三类信号：
        - market_anomaly: 市场异动
        - capital_flow: 资金流向
        - technical_breakout: 技术突破

        Args:
            force: 是否强制重新抽取

        Returns:
            观察列表，每个元素含 type/symbol/direction/strength/description/evidence
        """
        if self._observations and not force and self._new_since_summary == 0:
            return list(self._observations)

        events = self.get_recent(n=self.SUMMARIZE_LOOKBACK)
        if not events:
            return list(self._observations)

        observations: List[Dict[str, Any]] = []

        if self._llm is None:
            # 降级：基于规则的简单观察抽取
            observations = self._observe_rule_based(events)
        else:
            try:
                events_text = self._format_events_for_prompt(events)
                prompt = _OBSERVE_PROMPT.format(events=events_text)
                resp = self._llm.chat(prompt, system_prompt="你是量化研究员。")
                observations = self._parse_observations(resp, events)
            except Exception as exc:
                logger.warning("LLM 观察抽取失败，降级规则: %s", exc)
                observations = self._observe_rule_based(events)

        with self._lock:
            self._observations = observations

        logger.info("WorkingMemory 观察抽取完成（%d 条）", len(observations))
        return list(observations)

    def reflect(
        self,
        l3_store: Optional[Any] = None,
        symbol: Optional[str] = None,
    ) -> str:
        """生成阶段性反思（Reflection 组件）

        基于摘要 + 观察生成高层判断，可选写入 L3-Deep。

        Args:
            l3_store: L3Store 实例；非 None 时将反思写入 L3-Deep 层
            symbol: 关联标的代码（写入 L3 时使用）

        Returns:
            反思文本
        """
        summary = self._summary or self.summarize()
        observations = self._observations or self.observe()

        if not summary and not observations:
            return ""

        reflection_text: str
        confidence = "low"

        if self._llm is None:
            # 降级：基于摘要+观察的简单反思
            reflection_text = self._reflect_fallback(summary, observations)
        else:
            try:
                obs_text = json.dumps(observations, ensure_ascii=False, indent=2)
                prompt = _REFLECT_PROMPT.format(summary=summary, observations=obs_text)
                reflection_text = self._llm.chat(prompt, system_prompt="你是策略分析师。")
                if not reflection_text or not reflection_text.strip():
                    reflection_text = self._reflect_fallback(summary, observations)
                # 提取置信度
                confidence = self._extract_confidence(reflection_text)
            except Exception as exc:
                logger.warning("LLM 反思失败，降级文本: %s", exc)
                reflection_text = self._reflect_fallback(summary, observations)

        reflection_entry = {
            "content": reflection_text,
            "summary": reflection_text[:100] + "..." if len(reflection_text) > 100 else reflection_text,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
            "based_on_summary": summary[:200] if summary else "",
            "based_on_observations_count": len(observations),
        }

        with self._lock:
            self._reflections.append(reflection_entry)

        # 写入 L3-Deep（如提供 l3_store）
        if l3_store is not None:
            try:
                l3_store.write({
                    "symbol": symbol or "market",
                    "content": reflection_text,
                    "summary": reflection_entry["summary"],
                    "tier": "deep",
                    "period_type": "reflection",
                    "importance_score": 0.8,
                    "timestamp": datetime.now().isoformat(),
                })
                logger.info("WorkingMemory 反思已写入 L3-Deep")
            except Exception as exc:
                logger.warning("反思写入 L3 失败: %s", exc)

        logger.info("WorkingMemory 反思生成完成（置信度=%s）", confidence)
        return reflection_text

    # ── B4: 三组件降级实现（无 LLM 时） ──────────────────────────────

    def _summarize_fallback(self, events: List[Dict[str, Any]]) -> str:
        """无 LLM 时的降级摘要：拼接事件描述"""
        lines = []
        for ev in events[:10]:  # 最近 10 条
            ts = ev.get("timestamp", "")[:16]
            symbol = ev.get("symbol", "")
            content = ev.get("content", str(ev))[:80]
            lines.append(f"[{ts}] {symbol}: {content}")
        return "近期事件：\n" + "\n".join(lines)

    def _observe_rule_based(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """无 LLM 时的规则抽取观察"""
        observations: List[Dict[str, Any]] = []
        for ev in events:
            content = (ev.get("content") or "").lower()
            symbol = ev.get("symbol", "")
            ev_id = ev.get("id", "")

            # 简单规则：包含关键词时生成观察
            if any(kw in content for kw in ["涨停", "跌停", "异动", "放量"]):
                direction = "bearish" if "跌停" in content else "bullish"
                observations.append({
                    "type": "market_anomaly",
                    "symbol": symbol,
                    "direction": direction,
                    "strength": 0.7,
                    "description": content[:80],
                    "evidence": str(ev_id),
                })
            elif any(kw in content for kw in ["北向", "主力", "融资", "融券"]):
                observations.append({
                    "type": "capital_flow",
                    "symbol": symbol,
                    "direction": "neutral",
                    "strength": 0.5,
                    "description": content[:80],
                    "evidence": str(ev_id),
                })
            elif any(kw in content for kw in ["突破", "均线", "形态", "量价"]):
                observations.append({
                    "type": "technical_breakout",
                    "symbol": symbol,
                    "direction": "neutral",
                    "strength": 0.5,
                    "description": content[:80],
                    "evidence": str(ev_id),
                })
        return observations

    def _reflect_fallback(
        self,
        summary: str,
        observations: List[Dict[str, Any]],
    ) -> str:
        """无 LLM 时的降级反思"""
        if not observations:
            return f"判断：市场平稳\n依据：{summary[:100]}\n置信度：low"
        # 统计方向
        bullish = sum(1 for o in observations if o.get("direction") == "bullish")
        bearish = sum(1 for o in observations if o.get("direction") == "bearish")
        if bullish > bearish:
            direction = "看多"
            confidence = "medium" if bullish - bearish >= 3 else "low"
        elif bearish > bullish:
            direction = "看空"
            confidence = "medium" if bearish - bullish >= 3 else "low"
        else:
            direction = "震荡"
            confidence = "low"
        return (
            f"判断：市场情绪{direction}\n"
            f"依据：基于 {len(observations)} 条观察（{bullish} 多/{bearish} 空）\n"
            f"置信度：{confidence}"
        )

    # ── B4: 辅助方法 ──────────────────────────────────────────────────

    @staticmethod
    def _format_events_for_prompt(events: List[Dict[str, Any]]) -> str:
        """将事件列表格式化为 prompt 文本"""
        lines = []
        for i, ev in enumerate(events, 1):
            ts = ev.get("timestamp", "")[:16]
            symbol = ev.get("symbol", "")
            content = ev.get("content", str(ev))[:200]
            lines.append(f"{i}. [{ts}] {symbol}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _parse_observations(
        response: str,
        events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """解析 LLM 返回的观察 JSON"""
        if not response:
            return []
        try:
            # 尝试提取 JSON 数组
            text = response.strip()
            # 去除可能的 markdown 包裹
            if text.startswith("```"):
                text = text.split("```")[1] if "```" in text[3:] else text[3:]
                if text.startswith("json"):
                    text = text[4:]
            obs = json.loads(text)
            if isinstance(obs, list):
                return obs
        except Exception as exc:
            logger.debug("观察 JSON 解析失败: %s", exc)
        return []

    @staticmethod
    def _extract_confidence(reflection_text: str) -> str:
        """从反思文本中提取置信度"""
        text = reflection_text.lower()
        for level in ("high", "medium", "low"):
            if level in text:
                return level
        return "low"

    # ── B4: 访问器 ────────────────────────────────────────────────────

    @property
    def summary(self) -> Optional[str]:
        """获取当前缓存的摘要（不触发新摘要）"""
        return self._summary

    @property
    def observations(self) -> List[Dict[str, Any]]:
        """获取当前观察列表（副本）"""
        return list(self._observations)

    @property
    def reflections(self) -> List[Dict[str, Any]]:
        """获取反思列表（副本）"""
        return list(self._reflections)

    @property
    def llm_available(self) -> bool:
        """LLM 适配器是否可用"""
        return self._llm is not None
