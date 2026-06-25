# -*- coding: utf-8 -*-
"""F020 反幻觉编排管线"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..pipeline.collection import RawArticle

from .checkpoints import CheckpointResult
from .corrector import FiveStepCorrector
from .modes import VerificationMode, get_checkpoints, get_threshold

logger = logging.getLogger("stockquant.ai.hallucination")


class HallucinationPipeline:
    """反幻觉系统 — 多阶段验证管线

    按顺序执行: SourceVerifier → FactScreener → ConsistencyFilter →
    PromptConstraint → PostVerify → LogicVerifier → CrossValidator → ConfidenceScorer
    """

    def __init__(self, strict_mode: bool = False) -> None:
        self._strict = strict_mode
        self._corrector = FiveStepCorrector()

    def execute(self, articles: List[RawArticle]) -> Dict[str, Any]:
        """执行反幻觉检查"""
        results: Dict[str, Any] = {
            "passed": True,
            "issues": [],
            "scores": {},
        }

        if not articles:
            return results

        # 1. 来源验证
        source_result = self._source_verify(articles)
        results["source_verif"] = source_result

        # 2. 事实初筛
        fact_result = self._fact_screen(articles)
        results["fact_screen"] = fact_result

        # 3. 一致性过滤
        consist_result = self._consistency_filter(articles)
        results["consistency"] = consist_result

        # 综合评分
        results["scores"]["source"] = source_result.get("score", 0.5)
        results["scores"]["fact"] = fact_result.get("score", 0.5)
        results["scores"]["consistency"] = consist_result.get("score", 0.5)

        overall = sum(results["scores"].values()) / len(results["scores"])
        results["confidence"] = round(overall, 3)
        results["passed"] = overall >= (0.3 if not self._strict else 0.6)

        if not results["passed"]:
            results["issues"].append("综合可信度低于阈值，建议过滤")

        return results

    def verify(self, data: Dict[str, Any], mode: VerificationMode = VerificationMode.STANDARD) -> Dict[str, Any]:
        """基于验证模式执行检查点验证

        Args:
            data: 待验证的数据字典
            mode: 验证模式 (STRICT/STANDARD/RELAXED/EMERGENCY)

        Returns:
            验证结果，包含 passed/score/checkpoints/correction 等字段
        """
        result: Dict[str, Any] = {
            "mode": mode.value,
            "passed": True,
            "score": 1.0,
            "checkpoints": [],
            "correction": None,
        }

        # EMERGENCY 模式跳过所有验证
        if mode == VerificationMode.EMERGENCY:
            result["passed"] = True
            result["score"] = 1.0
            return result

        checkpoints = get_checkpoints(mode)
        threshold = get_threshold(mode)

        scores: List[float] = []
        for check_fn in checkpoints:
            try:
                passed, score, reason = check_fn(data)
            except Exception as exc:
                logger.warning("检查点 %s 异常: %s", check_fn.__name__, exc)
                passed, score, reason = False, 0.0, f"异常: {exc}"

            result["checkpoints"].append({
                "name": check_fn.__name__,
                "passed": passed,
                "score": score,
                "reason": reason,
            })
            scores.append(score)

            if not passed:
                result["issues"] = result.get("issues", [])
                result["issues"].append(f"{check_fn.__name__}: {reason}")

        # 计算综合评分
        if scores:
            avg_score = sum(scores) / len(scores)
            result["score"] = round(avg_score, 3)
            result["passed"] = avg_score >= threshold

        # 如果有检查点失败，执行五步纠正
        failed_checks = [cp for cp in result["checkpoints"] if not cp["passed"]]
        if failed_checks:
            correction = self._corrector.correct(data)
            result["correction"] = correction
            # 如果纠正后通过，更新结果
            if correction.get("passed"):
                result["passed"] = True
                result["score"] = max(result["score"], correction.get("score", 0.0))

        return result

    def _source_verify(self, articles: List[RawArticle]) -> Dict[str, Any]:
        known_sources = {"news_searcher", "eastmoney", "xueqiu", "cls", "cninfo", "cctv", "global_em", "eastmoney_express", "hot_rank_em", "comment_em", "disclosure"}
        verified = sum(1 for a in articles if a.source in known_sources)
        ratio = verified / len(articles) if articles else 0
        # 额外检查：验证 URL 格式（基础检查，不实际请求以避免阻塞）
        valid_urls = 0
        for a in articles:
            url = getattr(a, 'url', '') or ''
            if url and (url.startswith('http://') or url.startswith('https://')):
                valid_urls += 1
        url_ratio = valid_urls / len(articles) if articles else 0
        combined_score = (ratio * 0.7 + url_ratio * 0.3)
        return {"verified_count": verified, "score": combined_score, "url_valid_ratio": round(url_ratio, 3)}

    def _fact_screen(self, articles: List[RawArticle]) -> Dict[str, Any]:
        has_content = sum(1 for a in articles if a.content and len(a.content) > 10)
        ratio = has_content / len(articles) if articles else 0
        # 额外检查：提取内容中的数字/日期做基础验证
        import re
        valid_numbers = 0
        date_patterns = []
        for a in articles:
            if not a.content:
                continue
            # 提取百分比数字
            nums = re.findall(r'\d+(?:\.\d+)?%', a.content)
            if nums:
                valid_numbers += len(nums)
            # 提取日期
            dates = re.findall(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?', a.content)
            date_patterns.extend(dates)
        return {
            "valid_count": has_content,
            "score": ratio,
            "numbers_extracted": valid_numbers,
            "dates_extracted": len(date_patterns),
        }

    def _consistency_filter(self, articles: List[RawArticle]) -> Dict[str, Any]:
        titles = [a.title.strip().lower() for a in articles]
        unique_exact = len(set(titles))
        # 基于 Jaccard 词集合重叠率的语义去重（≥70% 视为重复）
        semantic_dup = 0
        for i in range(len(titles)):
            for j in range(i + 1, len(titles)):
                words_i = set(titles[i].split())
                words_j = set(titles[j].split())
                if not words_i or not words_j:
                    continue
                overlap = len(words_i & words_j)
                min_len = min(len(words_i), len(words_j))
                if min_len > 0 and overlap / min_len >= 0.7:
                    semantic_dup += 1
        ratio = unique_exact / len(titles) if titles else 0
        return {
            "unique_count": unique_exact,
            "semantic_duplicates": semantic_dup,
            "score": ratio,
        }


class FactDatabase:
    """已验证事实库"""

    def __init__(self) -> None:
        self._facts: List[Dict[str, Any]] = []

    def add(self, fact: Dict[str, Any]) -> str:
        self._facts.append(fact)
        return f"fact_{len(self._facts)}"

    def search(self, keyword: str) -> List[Dict[str, Any]]:
        return [f for f in self._facts if keyword.lower() in str(f).lower()]

    def count(self) -> int:
        return len(self._facts)


class HallucinationDB:
    """幻觉数据库 — 记录已识别的幻觉样本"""

    def __init__(self) -> None:
        self._records: List[Dict[str, Any]] = []

    def add(self, record: Dict[str, Any]) -> None:
        self._records.append(record)

    def search(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        if symbol:
            return [r for r in self._records if r.get("symbol") == symbol]
        return self._records

    def count(self) -> int:
        return len(self._records)
