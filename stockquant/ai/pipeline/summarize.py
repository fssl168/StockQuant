# -*- coding: utf-8 -*-
"""F020 信息总结阶段 — 6 步完整化（B5.2）

合并旧版 DEPRECATED `summarizer.py` 的 LLM 调用 + 多级摘要 + 五步验证能力：

Step 1: memory_retrieval        — L1/L2/L3 三源检索（保留）
Step 2: prompt_constraint_inject — 注入反幻觉 Prompt 约束（新增）
Step 3: llm_summarize           — Financial CoT 总结（新增，降级到规则）
Step 4: multi_level_summary     — 会话/日/周/月级摘要（新增）
Step 5: five_step_verify        — 事实验证链（fact/source/consistency/cross/confidence）
Step 6: memory_writeback        — 写入 L2 短期 + L3 长期（带 tier 标识）

设计原则：
- 完全向后兼容：`SummarizeStage().execute(articles)` 接口不变
- 渐进增强：传入 memory + llm_adapter 才启用 LLM 调用；否则降级
- 不引入新依赖（AIService 已封装 litellm）
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .collection import RawArticle

logger = logging.getLogger("stockquant.ai.pipeline.summarize")


# ─── 反幻觉 Prompt 约束（合并自旧版 summarizer.py） ───────────────────
PROMPT_CONSTRAINTS: List[str] = [
    "仅基于提供的信息进行总结，不得编造数据",
    "如果信息不足，明确标注'信息不足'而非推测",
    "所有数值必须来自原始信息，不得四舍五入或估算",
    "不得包含任何投资建议，如需提及请附免责声明",
]

# ─── Financial Chain-of-Thought 系统提示（借鉴 FinRobot） ─────────────
_FINANCIAL_COT_SYSTEM_PROMPT = """你是一名严谨的金融信息分析师。请按照以下 Financial Chain-of-Thought 流程分析：

1. 数据收集：列出所有提供的原始信息条目
2. 信息筛选：识别与该标的最相关的事实
3. 趋势判断：从历史事实和数据点判断价格/事件趋势
4. 异常检测：标注与历史不一致的异常点
5. 因果分析：解释事件与价格/财务变动的因果关系
6. 结论：给出基于证据的简明总结（不超过 300 字）

严格遵守的约束：
{constraints}

请输出 JSON：
{{
  "summary": "简明总结文本",
  "facts": ["关键事实1", "关键事实2"],
  "trend": "上涨|下跌|震荡|不确定",
  "confidence": 0.0-1.0,
  "anomalies": ["异常点1"],
  "reasoning_chain": ["步骤1", "步骤2", ...]
}}
"""


class SummarizeStage:
    """信息总结阶段 — 6 步完整化

    Step 1: memory_retrieval        L1/L2/L3 三源检索
    Step 2: prompt_constraint_inject 注入反幻觉约束
    Step 3: llm_summarize           Financial CoT 总结（降级到规则）
    Step 4: multi_level_summary     会话/日/周/月级摘要
    Step 5: five_step_verify        事实验证链
    Step 6: memory_writeback        写回 L2 + L3

    用法（向后兼容）：
        stage = SummarizeStage()
        result = stage.execute(articles)

    用法（启用 LLM + Memory）：
        stage = SummarizeStage(memory=mem, llm_adapter=ai_service)
        result = stage.execute(articles)
    """

    def __init__(
        self,
        memory: Any = None,
        llm_adapter: Any = None,
    ) -> None:
        """
        Args:
            memory: MemorySystem 实例（用于检索 + 回写）
            llm_adapter: AIService 或具备 chat(prompt, system_prompt) 方法的对象
        """
        self._memory = memory
        self._llm = llm_adapter

    def execute(self, articles: List[RawArticle]) -> Dict[str, Any]:
        """执行 6 步总结"""
        if not articles:
            return {
                "summary": "无有效信息",
                "facts": [],
                "confidence": 0.0,
                "level": "session",
                "article_count": 0,
            }

        # Step 1: 三源检索
        facts = self._memory_retrieval(articles)
        logger.debug("Step 1 memory_retrieval: %d facts", len(facts))

        # Step 2: Prompt 约束注入
        constraints = self._prompt_constraint_inject()
        logger.debug("Step 2 prompt_constraint_inject: %d constraints", len(constraints))

        # Step 3: LLM 总结（降级到规则）
        llm_result = self._llm_summarize(articles, facts, constraints)
        summary_text = llm_result.get("summary", "")
        logger.debug("Step 3 llm_summarize: %d chars", len(summary_text))

        # Step 4: 多级摘要
        level = self._determine_summary_level(articles)
        multi_level = self._build_multi_level_summary(summary_text, articles, level)
        logger.debug("Step 4 multi_level_summary: level=%s", level)

        # Step 5: 五步验证
        verified = self._five_step_verify(articles, facts, llm_result)
        logger.debug("Step 5 five_step_verify: passed=%s", verified.get("passed"))

        # Step 6: 记忆回写
        self._memory_writeback(articles, summary_text, llm_result, level)
        logger.debug("Step 6 memory_writeback: done")

        return {
            "summary": summary_text,
            "facts": facts[:20],
            "verified": verified.get("passed", False),
            "verification": verified,
            "confidence": llm_result.get("confidence", self._calculate_confidence(articles, facts)),
            "level": level,
            "multi_level": multi_level,
            "article_count": len(articles),
            "trend": llm_result.get("trend", "unknown"),
            "anomalies": llm_result.get("anomalies", []),
            "reasoning_chain": llm_result.get("reasoning_chain", []),
        }

    # ─── Step 1: 三源检索 ───────────────────────────────────────────────
    def _memory_retrieval(self, articles: List[RawArticle]) -> List[Dict[str, Any]]:
        """Step 1 — L1/L2/L3 三源检索相关事实"""
        facts: List[Dict[str, Any]] = []
        if self._memory is None:
            return facts

        # 提取 articles 中涉及的 symbols
        symbols = self._extract_symbols(articles)

        # L1: 工作记忆
        try:
            for sym in symbols[:3]:
                l1_facts = self._memory.search_working(symbol=sym)
                facts.extend([{"source": "L1", "data": f} for f in (l1_facts or [])[:5]])
        except Exception as exc:
            logger.warning("L1 检索失败: %s", exc)

        # L2: 短期记忆
        try:
            for sym in symbols[:3]:
                l2_facts = self._memory.search_short_term(symbol=sym, limit=5)
                facts.extend([{"source": "L2", "data": f} for f in (l2_facts or [])[:5]])
        except Exception as exc:
            logger.warning("L2 检索失败: %s", exc)

        # L3: 长期记忆
        try:
            for sym in symbols[:3]:
                l3_facts = self._memory.search_long_term(symbol=sym, limit=5)
                facts.extend([{"source": "L3", "data": f} for f in (l3_facts or [])[:5]])
        except Exception as exc:
            logger.warning("L3 检索失败: %s", exc)

        return facts

    @staticmethod
    def _extract_symbols(articles: List[RawArticle]) -> List[str]:
        """从 articles 中提取涉及的 symbols"""
        symbols: List[str] = []
        for a in articles:
            if not a.raw:
                continue
            raw_syms = a.raw.get("symbols")
            if isinstance(raw_syms, list):
                symbols.extend(str(s) for s in raw_syms if s)
            elif a.raw.get("symbol"):
                symbols.append(str(a.raw["symbol"]))
        # 去重保序
        return list(dict.fromkeys(symbols))

    # ─── Step 2: Prompt 约束注入 ────────────────────────────────────────
    def _prompt_constraint_inject(self) -> List[str]:
        """Step 2 — 返回反幻觉约束列表（合并自旧版 PROMPT_CONSTRAINTS）"""
        return list(PROMPT_CONSTRAINTS)

    # ─── Step 3: LLM 总结（降级到规则） ─────────────────────────────────
    def _llm_summarize(
        self,
        articles: List[RawArticle],
        facts: List[Dict[str, Any]],
        constraints: List[str],
    ) -> Dict[str, Any]:
        """Step 3 — 调用 LLM 生成 Financial CoT 总结，失败时降级到规则"""
        if self._llm is None:
            return self._rule_based_summarize(articles, facts)

        try:
            return self._call_llm(articles, facts, constraints)
        except Exception as exc:
            logger.warning("LLM 总结失败，降级到规则总结: %s", exc)
            return self._rule_based_summarize(articles, facts)

    def _call_llm(
        self,
        articles: List[RawArticle],
        facts: List[Dict[str, Any]],
        constraints: List[str],
    ) -> Dict[str, Any]:
        """调用 LLM 生成总结"""
        constraints_text = "\n".join(f"- {c}" for c in constraints)
        system_prompt = _FINANCIAL_COT_SYSTEM_PROMPT.format(constraints=constraints_text)

        items_text = "\n".join(
            f"[{a.source}] {a.title}: {(a.content or '')[:200]}"
            for a in articles[:15]
        )
        facts_text = "\n".join(
            f"[{f.get('source', '?')}] {json.dumps(f.get('data', {}), ensure_ascii=False, default=str)[:100]}"
            for f in facts[:10]
        )

        user_prompt = (
            f"原始信息（共 {len(articles)} 条）：\n{items_text}\n\n"
            f"历史事实（共 {len(facts)} 条）：\n{facts_text}\n\n"
            f"请按照 Financial Chain-of-Thought 流程分析并输出 JSON。"
        )

        # AIService.chat(message, system_prompt="") 接口
        try:
            content = self._llm.chat(user_prompt, system_prompt=system_prompt)
        except TypeError:
            # 兼容旧式 chat(messages, ...) 接口
            content = self._llm.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ])

        if not isinstance(content, str) or not content:
            return self._rule_based_summarize(articles, facts)

        # 解析 JSON 响应
        return self._parse_llm_response(content, articles, facts)

    def _parse_llm_response(
        self,
        content: str,
        articles: List[RawArticle],
        facts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """解析 LLM 的 JSON 响应，失败时降级到规则"""
        # 尝试提取 JSON 块
        json_match = re.search(r'\{[\s\S]*\}', content)
        if not json_match:
            # 无 JSON，直接用文本作为 summary
            return {
                "summary": content.strip()[:500],
                "facts": [],
                "trend": "unknown",
                "confidence": 0.5,
                "anomalies": [],
                "reasoning_chain": [],
            }

        try:
            result = json.loads(json_match.group(0))
            # 字段补全
            result.setdefault("summary", content.strip()[:500])
            result.setdefault("facts", [])
            result.setdefault("trend", "unknown")
            result.setdefault("confidence", 0.5)
            result.setdefault("anomalies", [])
            result.setdefault("reasoning_chain", [])
            return result
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("LLM 响应 JSON 解析失败: %s", exc)
            return {
                "summary": content.strip()[:500],
                "facts": [],
                "trend": "unknown",
                "confidence": 0.4,
                "anomalies": [],
                "reasoning_chain": [],
            }

    def _rule_based_summarize(
        self,
        articles: List[RawArticle],
        facts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """规则总结（LLM 不可用时的降级方案）"""
        sources = set(a.source for a in articles)
        parts = [f"共采集 {len(articles)} 条信息，来源：{', '.join(sorted(sources))}"]

        # 按来源分组
        by_source: Dict[str, List[RawArticle]] = {}
        for a in articles:
            by_source.setdefault(a.source, []).append(a)

        for source, group in sorted(by_source.items()):
            parts.append(f"\n[{source}] {len(group)} 条：")
            for a in group[:3]:
                parts.append(f"  - {a.title}")

        # 提取关键数据点
        all_text = " ".join((a.content or "") for a in articles)
        if all_text:
            numbers = re.findall(r'\d+(?:\.\d+)?%', all_text)
            if numbers:
                parts.append(f"\n关键数据点：{', '.join(sorted(set(numbers))[:10])}")

        if facts:
            parts.append(f"\n历史参考: {len(facts)} 条相关事实")

        summary = "\n".join(parts[:50])

        # 简单趋势判断
        trend = self._infer_trend(all_text)

        return {
            "summary": summary,
            "facts": [],
            "trend": trend,
            "confidence": self._calculate_confidence(articles, facts),
            "anomalies": [],
            "reasoning_chain": ["rule_based_summary"],
        }

    @staticmethod
    def _infer_trend(text: str) -> str:
        """简单趋势判断"""
        if not text:
            return "unknown"
        positive = sum(1 for w in ("利好", "上涨", "增长", "盈利", "增持") if w in text)
        negative = sum(1 for w in ("利空", "下跌", "亏损", "减持", "风险") if w in text)
        if positive > negative:
            return "上涨"
        if negative > positive:
            return "下跌"
        if positive > 0:
            return "震荡"
        return "不确定"

    # ─── Step 4: 多级摘要 ───────────────────────────────────────────────
    def _determine_summary_level(self, articles: List[RawArticle]) -> str:
        """确定摘要级别 — session/daily/weekly/monthly"""
        timestamps = [a.published_at for a in articles if a.published_at]
        if not timestamps:
            return "session"
        span = max(timestamps) - min(timestamps)
        if span <= timedelta(hours=4):
            return "session"
        if span <= timedelta(days=1):
            return "daily"
        if span <= timedelta(days=7):
            return "weekly"
        return "monthly"

    def _build_multi_level_summary(
        self,
        summary_text: str,
        articles: List[RawArticle],
        current_level: str,
    ) -> Dict[str, str]:
        """构建多级摘要 — session/daily/weekly/monthly"""
        levels = ["session", "daily", "weekly", "monthly"]
        level_idx = levels.index(current_level) if current_level in levels else 0

        result: Dict[str, str] = {current_level: summary_text}

        # 更高级别使用压缩版本
        for i in range(level_idx + 1, len(levels)):
            higher_level = levels[i]
            core_items = articles[:3]
            compressed = "; ".join(f"{a.source}:{a.title[:20]}" for a in core_items)
            result[higher_level] = f"[{higher_level}摘要] {compressed}"

        return result

    # ─── Step 5: 五步验证 ───────────────────────────────────────────────
    def _five_step_verify(
        self,
        articles: List[RawArticle],
        facts: List[Dict[str, Any]],
        llm_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Step 5 — 五步验证链：fact_check → source_check → consistency → cross_validation → confidence"""
        # 1. fact_check — 事实校验
        fact_check = self._verify_facts(articles, facts)

        # 2. source_check — 来源校验
        source_check = self._verify_sources(articles)

        # 3. consistency — 一致性校验
        consistency = self._verify_consistency(articles, llm_result)

        # 4. cross_validation — 交叉验证
        cross_validation = self._cross_validate(articles, facts)

        # 5. confidence — 综合置信度
        confidence = self._aggregate_confidence(
            fact_check, source_check, consistency, cross_validation, llm_result
        )

        passed = all([
            fact_check["passed"],
            source_check["passed"],
            consistency["passed"],
        ]) and confidence >= 0.4

        return {
            "passed": passed,
            "confidence": confidence,
            "steps": {
                "fact_check": fact_check,
                "source_check": source_check,
                "consistency": consistency,
                "cross_validation": cross_validation,
            },
        }

    def _verify_facts(
        self,
        articles: List[RawArticle],
        facts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """事实校验 — 检查数值是否在原始信息中出现"""
        if not articles:
            return {"passed": False, "issues": ["无原始文章"]}

        issues: List[str] = []
        all_text = " ".join((a.content or "") + " " + (a.title or "") for a in articles)

        # 提取所有百分比数字
        numbers_in_articles = set(re.findall(r'\d+(?:\.\d+)?%', all_text))

        # 从 LLM 结果或 facts 中提取数字
        for fact in facts[:10]:
            fact_data = fact.get("data", {})
            if isinstance(fact_data, dict):
                fact_str = json.dumps(fact_data, ensure_ascii=False, default=str)
            else:
                fact_str = str(fact_data)
            fact_numbers = re.findall(r'\d+(?:\.\d+)?%', fact_str)
            for num in fact_numbers:
                if num not in numbers_in_articles and fact.get("source") != "L3":
                    # L3 是历史事实，可以不在当前文章中
                    issues.append(f"数值 {num} 未在原始信息中出现")

        passed = len(issues) < 3  # 允许少量不一致
        return {"passed": passed, "issues": issues[:5]}

    def _verify_sources(self, articles: List[RawArticle]) -> Dict[str, Any]:
        """来源校验 — 检查所有文章是否都有可信来源"""
        if not articles:
            return {"passed": False, "issues": ["无文章"]}

        issues: List[str] = []
        credible_sources = {"cninfo", "cls", "eastmoney", "news_searcher", "xueqiu", "sina"}
        for a in articles:
            if not a.source:
                issues.append(f"文章无来源: {a.title[:30]}")
            elif a.source not in credible_sources:
                issues.append(f"未知来源 {a.source}: {a.title[:30]}")
            if not a.url and not a.source:
                issues.append(f"文章无 URL 且无来源: {a.title[:30]}")

        passed = len(issues) < len(articles) * 0.5  # 至少一半可信
        return {"passed": passed, "issues": issues[:5]}

    def _verify_consistency(
        self,
        articles: List[RawArticle],
        llm_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """一致性校验 — 检查文章间是否互相矛盾"""
        if not articles:
            return {"passed": False, "issues": ["无文章"]}

        issues: List[str] = []
        positive_words = {"利好", "上涨", "增长", "盈利", "增持"}
        negative_words = {"利空", "下跌", "亏损", "减持", "风险"}

        positive_count = 0
        negative_count = 0
        for a in articles:
            text = (a.title or "") + " " + (a.content or "")
            if any(w in text for w in positive_words):
                positive_count += 1
            if any(w in text for w in negative_words):
                negative_count += 1

        # 同时大量正面和负面，可能存在矛盾
        if positive_count > 2 and negative_count > 2:
            issues.append(
                f"同时存在 {positive_count} 条正面 + {negative_count} 条负面信息，可能矛盾"
            )

        # 与 LLM 趋势判断一致性
        llm_trend = llm_result.get("trend", "unknown")
        if llm_trend == "上涨" and negative_count > positive_count:
            issues.append("LLM 判断上涨但负面信息更多")
        if llm_trend == "下跌" and positive_count > negative_count:
            issues.append("LLM 判断下跌但正面信息更多")

        passed = len(issues) == 0
        return {"passed": passed, "issues": issues}

    def _cross_validate(
        self,
        articles: List[RawArticle],
        facts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """交叉验证 — 检查是否有多源支撑"""
        if not articles:
            return {"passed": False, "issues": ["无文章"], "support_count": 0}

        # 按来源分组
        source_set = set(a.source for a in articles if a.source)
        support_count = len(source_set)

        issues: List[str] = []
        if support_count < 2:
            issues.append(f"仅 {support_count} 个来源，交叉验证不足")

        # L3 历史事实支撑
        l3_count = sum(1 for f in facts if f.get("source") == "L3")
        if l3_count == 0 and len(articles) > 2:
            issues.append("无 L3 历史事实支撑")

        passed = support_count >= 2
        return {
            "passed": passed,
            "issues": issues,
            "support_count": support_count,
            "l3_support": l3_count,
        }

    def _aggregate_confidence(
        self,
        fact_check: Dict[str, Any],
        source_check: Dict[str, Any],
        consistency: Dict[str, Any],
        cross_validation: Dict[str, Any],
        llm_result: Dict[str, Any],
    ) -> float:
        """综合置信度 — 加权四步验证结果"""
        # 各步权重
        score = 0.0
        score += 0.25 * (1.0 if fact_check.get("passed") else 0.3)
        score += 0.20 * (1.0 if source_check.get("passed") else 0.3)
        score += 0.25 * (1.0 if consistency.get("passed") else 0.4)
        # 交叉验证按来源数加权
        support = cross_validation.get("support_count", 0)
        score += 0.30 * min(support / 3.0, 1.0)
        # LLM 置信度作为微调
        llm_conf = float(llm_result.get("confidence", 0.5) or 0.5)
        score = score * 0.85 + llm_conf * 0.15
        return round(min(score, 1.0), 3)

    @staticmethod
    def _calculate_confidence(
        articles: List[RawArticle],
        facts: List[Dict[str, Any]],
    ) -> float:
        """计算总结置信度（规则降级用）"""
        if not articles:
            return 0.0

        volume_score = min(len(articles) / 10, 1.0)
        has_content = sum(1 for a in articles if a.content and len(a.content) > 20)
        content_score = has_content / len(articles)
        fact_score = min(len(facts) / 5, 1.0)
        verified = sum(1 for a in articles if a.raw and a.raw.get("verified"))
        verify_score = verified / len(articles)

        return round(
            volume_score * 0.2 + content_score * 0.3 + fact_score * 0.3 + verify_score * 0.2,
            3,
        )

    # ─── Step 6: 记忆回写 ───────────────────────────────────────────────
    def _memory_writeback(
        self,
        articles: List[RawArticle],
        summary_text: str,
        llm_result: Dict[str, Any],
        level: str,
    ) -> None:
        """Step 6 — 写入 L2 短期记忆 + L3 长期记忆（带 tier 标识）"""
        if self._memory is None:
            return

        symbols = self._extract_symbols(articles)
        confidence = float(llm_result.get("confidence", 0.5) or 0.5)

        # 写入 L2 短期记忆（tier=shallow）
        try:
            for sym in symbols[:3]:
                self._memory.add_short_term(
                    symbol=sym,
                    content=summary_text[:500],
                    metadata={
                        "type": "summarized",
                        "item_count": len(articles),
                        "level": level,
                        "trend": llm_result.get("trend", "unknown"),
                        "confidence": confidence,
                        "tier": "shallow",
                    },
                )
        except Exception as exc:
            logger.warning("L2 短期记忆回写失败: %s", exc)

        # 写入 L3 长期记忆（高置信度才写，tier=shallow，importance_score=confidence）
        if confidence >= 0.6 and symbols:
            try:
                primary_symbol = symbols[0]
                # 用 add_intermediate 接口（tier=intermediate 季报级），或 fallback 到 add_long_term
                # 这里用 add_long_term 更通用（保持向后兼容），写入 tier=shallow
                self._memory.add_long_term({
                    "user_id": getattr(self._memory.l3, "_user_id", "test_user"),
                    "symbol": primary_symbol,
                    "content": summary_text[:1000],
                    "summary": summary_text[:200],
                    "metadata": {
                        "type": "pipeline_summary",
                        "level": level,
                        "trend": llm_result.get("trend", "unknown"),
                        "article_count": len(articles),
                    },
                    "tier": "shallow",
                    "period_type": "ad_hoc",
                    "importance_score": confidence,
                    "timestamp": datetime.now().isoformat(),
                    "confidence": confidence,
                })
            except Exception as exc:
                logger.warning("L3 长期记忆回写失败: %s", exc)


# ─── 工厂函数 ─────────────────────────────────────────────────────────
def make_summarize_stage(
    memory: Any = None,
    llm_adapter: Any = None,
) -> SummarizeStage:
    """构造 SummarizeStage — 便捷工厂"""
    return SummarizeStage(memory=memory, llm_adapter=llm_adapter)
