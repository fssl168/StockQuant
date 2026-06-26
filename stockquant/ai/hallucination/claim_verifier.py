# -*- coding: utf-8 -*-
"""F020 反幻觉增强（Phase E1）— FINGROUND 六类原子声明验证

借鉴 FINGROUND 论文（arxiv 2406.12697）的声明分类方法：
将文本中的声明分解为六类原子声明，按类型路由到不同的验证策略：

1. NUMERIC（数值型）：营收/利润/PE 等具体数字 → 查询数据库验证
2. TEMPORAL（时间型）：财报日期/事件日期 → 查询历史数据验证时间一致性
3. ENTITY_ATTR（实体属性）：董事长/注册地/主营业务 → 查询公司信息验证
4. COMPARATIVE（比较型）：同比/环比/排名 → 交叉查询比较
5. REGULATORY（监管型）：政策/法规/处罚 → 查询公告验证
6. COMPUTATIONAL（计算型）：增长率/比率 → 公式重构验证

设计原则：
- 每类声明有独立的 verify_*_claim 方法，便于扩展
- 验证失败不抛异常，返回 ClaimVerification(verified=False, reason=...)
- 依赖 memory_system 做事实查询；memory 不可用时降级到关键词检查
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("stockquant.ai.hallucination.claim_verifier")


class ClaimType(str, Enum):
    """FINGROUND 六类原子声明类型

    使用 str mixin 以便 JSON 序列化。
    """
    NUMERIC = "numeric"                # 数值型：营收/利润/PE/价格/成交量
    TEMPORAL = "temporal"               # 时间型：财报日期/事件日期
    ENTITY_ATTR = "entity_attr"         # 实体属性：董事长/注册地/主营业务
    COMPARATIVE = "comparative"         # 比较型：同比/环比/排名
    REGULATORY = "regulatory"           # 监管型：政策/法规/处罚
    COMPUTATIONAL = "computational"     # 计算型：增长率/比率/百分比

    @classmethod
    def from_str(cls, value: str | None) -> "ClaimType":
        """从字符串安全解析，无效值返回 ENTITY_ATTR（最宽松的兜底）"""
        if value is None:
            return cls.ENTITY_ATTR
        # 兼容 elevate.py 的 "computed" 与本枚举的 "computational"
        if value == "computed":
            return cls.COMPUTATIONAL
        if value == "entity":
            return cls.ENTITY_ATTR
        try:
            return cls(value.lower())
        except (ValueError, AttributeError):
            return cls.ENTITY_ATTR


@dataclass
class ClaimVerification:
    """原子声明验证结果

    Attributes:
        claim: 原始声明文本
        claim_type: 声明类型
        verified: 是否通过验证
        confidence: 验证置信度 [0, 1]
        reason: 验证理由
        evidence: 验证证据（如数据库查询结果、历史记忆条目）
        source: 验证来源（database/memory/keyword）
    """
    claim: str = ""
    claim_type: str = ""
    verified: bool = False
    confidence: float = 0.0
    reason: str = ""
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    source: str = ""


class ClaimVerifier:
    """FINGROUND 六类原子声明验证器

    用法::

        verifier = ClaimVerifier(memory_system=memory)
        result = await verifier.verify_claim(
            claim="贵州茅台 2023 年净利润同比增长 30%",
            claim_type=ClaimType.COMPUTATIONAL,
        )
        if not result.verified:
            logger.warning("声明验证失败: %s", result.reason)
    """

    def __init__(self, memory_system: Optional[Any] = None) -> None:
        self._memory = memory_system

    async def verify_claim(
        self,
        claim: str,
        claim_type: Optional[ClaimType] = None,
        memory_system: Optional[Any] = None,
    ) -> ClaimVerification:
        """验证单个原子声明

        Args:
            claim: 声明文本
            claim_type: 声明类型（None 时自动分类）
            memory_system: 可选，覆盖实例级 memory_system

        Returns:
            ClaimVerification 验证结果
        """
        if not claim or not claim.strip():
            return ClaimVerification(
                claim=claim,
                verified=False,
                reason="声明为空",
            )

        # 自动分类（如未指定类型）
        if claim_type is None:
            claim_type = self.classify_claim(claim)

        mem = memory_system or self._memory

        # 类型路由
        try:
            if claim_type == ClaimType.NUMERIC:
                return await self._verify_numeric(claim, mem)
            if claim_type == ClaimType.TEMPORAL:
                return await self._verify_temporal(claim, mem)
            if claim_type == ClaimType.ENTITY_ATTR:
                return await self._verify_entity_attr(claim, mem)
            if claim_type == ClaimType.COMPARATIVE:
                return await self._verify_comparative(claim, mem)
            if claim_type == ClaimType.REGULATORY:
                return await self._verify_regulatory(claim, mem)
            if claim_type == ClaimType.COMPUTATIONAL:
                return await self._verify_computational(claim, mem)
        except Exception as exc:
            logger.warning("声明验证异常 (type=%s): %s", claim_type.value, exc)
            return ClaimVerification(
                claim=claim,
                claim_type=claim_type.value,
                verified=False,
                confidence=0.0,
                reason=f"验证异常: {exc}",
                source="exception",
            )

        # 未知类型，默认通过（宽松模式）
        return ClaimVerification(
            claim=claim,
            claim_type=claim_type.value,
            verified=True,
            confidence=0.5,
            reason="未知声明类型，默认通过",
            source="fallback",
        )

    async def verify_claims_batch(
        self,
        claims: List[Tuple[str, Optional[ClaimType]]],
        memory_system: Optional[Any] = None,
    ) -> List[ClaimVerification]:
        """批量验证声明

        Args:
            claims: [(claim_text, claim_type), ...] 列表，claim_type 可为 None
            memory_system: 可选 memory

        Returns:
            验证结果列表（顺序与输入一致）
        """
        results = []
        for claim, claim_type in claims:
            result = await self.verify_claim(claim, claim_type, memory_system)
            results.append(result)
        return results

    # ── 声明分类（与 elevate.py _classify_claim 对齐） ──────────────────

    @staticmethod
    def classify_claim(text: str) -> ClaimType:
        """分类声明类型

        优先级与 elevate.py _classify_claim 保持一致：
        temporal → computational（同比/环比+digit）→ comparative → numeric → regulatory → entity_attr
        """
        if not text:
            return ClaimType.ENTITY_ATTR
        # temporal: 含日期
        if re.search(r'\d{4}年|\d{1,2}月|\d{1,2}日|季度|年度|Q[1-4]', text):
            return ClaimType.TEMPORAL
        # computational: 同比/环比 + 数字
        if any(w in text for w in ["同比", "环比", "增长率", "增速"]):
            if any(c.isdigit() for c in text):
                return ClaimType.COMPUTATIONAL
        # comparative: 比较词
        if any(w in text for w in ["高于", "低于", "超过", "不及", "对比"]):
            return ClaimType.COMPARATIVE
        # numeric: 数字 + 单位
        if any(c.isdigit() for c in text) and ("%" in text or "亿" in text or "万" in text):
            return ClaimType.NUMERIC
        # regulatory: 监管类
        if any(w in text for w in ["监管", "证监会", "政策", "处罚", "公告", "披露"]):
            return ClaimType.REGULATORY
        # entity_attr: 公司名/股票代码
        if re.search(r'[A-Za-z]\d{6}|sh\d{6}|sz\d{6}|公司|集团|董事长|注册地', text):
            return ClaimType.ENTITY_ATTR
        return ClaimType.ENTITY_ATTR

    # ── 六类验证策略 ──────────────────────────────────────────────────

    async def _verify_numeric(
        self, claim: str, memory_system: Optional[Any]
    ) -> ClaimVerification:
        """数值型声明验证：查询数据库/记忆验证数字

        策略：
        1. 从声明中提取所有数字
        2. 查询 memory 中匹配的数字（symbol + 数字匹配）
        3. 若至少一个数字在记忆中找到匹配，则验证通过
        """
        numbers = re.findall(r'\d+(?:\.\d+)?', claim)
        if not numbers:
            return ClaimVerification(
                claim=claim, claim_type=ClaimType.NUMERIC.value,
                verified=False, confidence=0.3,
                reason="数值型声明但未提取到数字",
                source="regex",
            )

        # 从 memory 检索
        evidence: List[Dict[str, Any]] = []
        if memory_system is not None:
            try:
                # 用声明中的关键词检索
                keyword = claim[:50]  # 取前 50 字符作为查询
                items = self._search_memory(memory_system, keyword=keyword, limit=5)
                for item in items:
                    content = str(item.get("content") or item.get("summary") or "")
                    # 检查记忆中是否包含相同数字
                    mem_numbers = re.findall(r'\d+(?:\.\d+)?', content)
                    common = set(numbers) & set(mem_numbers)
                    if common:
                        evidence.append({
                            "source": "memory",
                            "matched_numbers": list(common),
                            "content_snippet": content[:100],
                        })
            except Exception as exc:
                logger.debug("memory 检索失败: %s", exc)

        # 验证逻辑：有证据则通过，否则降级到格式检查
        if evidence:
            return ClaimVerification(
                claim=claim, claim_type=ClaimType.NUMERIC.value,
                verified=True, confidence=0.85,
                reason=f"数值在记忆中找到 {len(evidence)} 条匹配",
                evidence=evidence,
                source="memory",
            )
        # 降级：数字格式合理（不超过 3 位小数）
        precise_check = any(len(n.split(".")[-1]) > 3 for n in numbers if "." in n)
        if precise_check:
            return ClaimVerification(
                claim=claim, claim_type=ClaimType.NUMERIC.value,
                verified=False, confidence=0.4,
                reason="数字过于精确（超过 3 位小数），可能是虚构",
                source="format_check",
            )
        return ClaimVerification(
            claim=claim, claim_type=ClaimType.NUMERIC.value,
            verified=True, confidence=0.6,
            reason="数值格式合理（无可对照记忆，降级通过）",
            source="format_check",
        )

    async def _verify_temporal(
        self, claim: str, memory_system: Optional[Any]
    ) -> ClaimVerification:
        """时间型声明验证：检查日期是否合理

        策略：
        1. 提取所有日期
        2. 检查日期是否在未来（不合理）
        3. 检查日期格式是否一致
        """
        from datetime import datetime
        dates = re.findall(r'(\d{4})[-/年](\d{1,2})[-/月]?(\d{1,2})?', claim)
        if not dates:
            return ClaimVerification(
                claim=claim, claim_type=ClaimType.TEMPORAL.value,
                verified=True, confidence=0.6,
                reason="时间型声明但未提取到完整日期，默认通过",
                source="regex",
            )
        now = datetime.now()
        future_dates = []
        for y_str, m_str, d_str in dates:
            try:
                year = int(y_str)
                month = int(m_str) if m_str else 1
                day = int(d_str) if d_str else 1
                if not (1 <= month <= 12):
                    return ClaimVerification(
                        claim=claim, claim_type=ClaimType.TEMPORAL.value,
                        verified=False, confidence=0.3,
                        reason=f"月份超出范围: {month}",
                        source="format_check",
                    )
                if not (1 <= day <= 31):
                    return ClaimVerification(
                        claim=claim, claim_type=ClaimType.TEMPORAL.value,
                        verified=False, confidence=0.3,
                        reason=f"日期超出范围: {day}",
                        source="format_check",
                    )
                extracted_date = datetime(year, month, day)
                if extracted_date > now:
                    future_dates.append(extracted_date.strftime("%Y-%m-%d"))
            except ValueError:
                return ClaimVerification(
                    claim=claim, claim_type=ClaimType.TEMPORAL.value,
                    verified=False, confidence=0.3,
                    reason=f"日期解析失败: {y_str}-{m_str}-{d_str}",
                    source="format_check",
                )

        if future_dates:
            return ClaimVerification(
                claim=claim, claim_type=ClaimType.TEMPORAL.value,
                verified=False, confidence=0.2,
                reason=f"日期在未来: {future_dates}",
                source="format_check",
            )
        return ClaimVerification(
            claim=claim, claim_type=ClaimType.TEMPORAL.value,
            verified=True, confidence=0.8,
            reason=f"日期格式合理 ({len(dates)} 个日期)",
            source="format_check",
        )

    async def _verify_entity_attr(
        self, claim: str, memory_system: Optional[Any]
    ) -> ClaimVerification:
        """实体属性声明验证：查询公司信息

        策略：检索 memory 中是否提到该公司/实体
        """
        # 提取可能的股票代码或公司名
        symbol_match = re.search(r'(sh|sz|bj)?\d{6}', claim, re.IGNORECASE)
        company_match = re.search(r'[\u4e00-\u9fff]{2,}(公司|集团|股份)', claim)

        if not symbol_match and not company_match:
            return ClaimVerification(
                claim=claim, claim_type=ClaimType.ENTITY_ATTR.value,
                verified=False, confidence=0.3,
                reason="未识别到实体（公司名/股票代码）",
                source="regex",
            )

        keyword = symbol_match.group(0) if symbol_match else company_match.group(0)
        evidence: List[Dict[str, Any]] = []
        if memory_system is not None:
            try:
                items = self._search_memory(memory_system, keyword=keyword, limit=3)
                for item in items:
                    content = str(item.get("content") or "")
                    if keyword.lower() in content.lower():
                        evidence.append({
                            "source": "memory",
                            "matched_entity": keyword,
                            "content_snippet": content[:100],
                        })
            except Exception as exc:
                logger.debug("memory 检索失败: %s", exc)

        if evidence:
            return ClaimVerification(
                claim=claim, claim_type=ClaimType.ENTITY_ATTR.value,
                verified=True, confidence=0.85,
                reason=f"实体在记忆中找到 {len(evidence)} 条匹配",
                evidence=evidence,
                source="memory",
            )
        return ClaimVerification(
            claim=claim, claim_type=ClaimType.ENTITY_ATTR.value,
            verified=True, confidence=0.5,
            reason="识别到实体格式但无记忆可对照，默认通过",
            source="format_check",
        )

    async def _verify_comparative(
        self, claim: str, memory_system: Optional[Any]
    ) -> ClaimVerification:
        """比较型声明验证：交叉查询比较

        策略：检查比较方向是否与记忆中的趋势一致
        """
        # 提取比较词
        direction = None
        if any(w in claim for w in ["高于", "超过", "增长", "上升"]):
            direction = "up"
        elif any(w in claim for w in ["低于", "不及", "下降", "减少"]):
            direction = "down"

        if direction is None:
            return ClaimVerification(
                claim=claim, claim_type=ClaimType.COMPARATIVE.value,
                verified=True, confidence=0.6,
                reason="比较型声明但未识别方向，默认通过",
                source="format_check",
            )

        # 检索记忆中的趋势
        evidence: List[Dict[str, Any]] = []
        if memory_system is not None:
            try:
                items = self._search_memory(memory_system, keyword=claim[:30], limit=3)
                for item in items:
                    content = str(item.get("content") or "")
                    # 简单检查：记忆中是否提到反向趋势
                    opposite = "下降" if direction == "up" else "上升"
                    if opposite in content:
                        evidence.append({
                            "source": "memory",
                            "conflict": True,
                            "content_snippet": content[:100],
                        })
            except Exception:
                pass

        if evidence:
            return ClaimVerification(
                claim=claim, claim_type=ClaimType.COMPARATIVE.value,
                verified=False, confidence=0.3,
                reason=f"比较方向与 {len(evidence)} 条记忆冲突",
                evidence=evidence,
                source="memory",
            )
        return ClaimVerification(
            claim=claim, claim_type=ClaimType.COMPARATIVE.value,
            verified=True, confidence=0.7,
            reason=f"比较方向 {direction} 无冲突记忆",
            source="format_check",
        )

    async def _verify_regulatory(
        self, claim: str, memory_system: Optional[Any]
    ) -> ClaimVerification:
        """监管型声明验证：查询公告验证

        策略：检查是否提到具体监管机构/政策名称
        """
        regulatory_keywords = ["证监会", "上交所", "深交所", "国务院", "央行", "银保监会"]
        found_agencies = [k for k in regulatory_keywords if k in claim]

        if not found_agencies:
            return ClaimVerification(
                claim=claim, claim_type=ClaimType.REGULATORY.value,
                verified=False, confidence=0.4,
                reason="监管型声明但未识别到具体监管机构",
                source="format_check",
            )

        # 检索公告
        evidence: List[Dict[str, Any]] = []
        if memory_system is not None:
            try:
                for agency in found_agencies:
                    items = self._search_memory(memory_system, keyword=agency, limit=2)
                    for item in items:
                        content = str(item.get("content") or "")
                        if agency in content:
                            evidence.append({
                                "source": "memory",
                                "matched_agency": agency,
                                "content_snippet": content[:100],
                            })
            except Exception:
                pass

        if evidence:
            return ClaimVerification(
                claim=claim, claim_type=ClaimType.REGULATORY.value,
                verified=True, confidence=0.8,
                reason=f"监管机构在记忆中找到 {len(evidence)} 条匹配",
                evidence=evidence,
                source="memory",
            )
        return ClaimVerification(
            claim=claim, claim_type=ClaimType.REGULATORY.value,
            verified=True, confidence=0.6,
            reason=f"识别到监管机构 {found_agencies}，无记忆可对照",
            source="format_check",
        )

    async def _verify_computational(
        self, claim: str, memory_system: Optional[Any]
    ) -> ClaimVerification:
        """计算型声明验证：公式重构验证

        策略：
        1. 提取"同比/环比 + 数字%"
        2. 检查百分比是否在合理范围（通常 < 1000%）
        3. 若有记忆数据，检查趋势是否一致
        """
        # 提取百分比
        pcts = re.findall(r'(\d+(?:\.\d+)?)\s*%', claim)
        if not pcts:
            return ClaimVerification(
                claim=claim, claim_type=ClaimType.COMPUTATIONAL.value,
                verified=False, confidence=0.4,
                reason="计算型声明但未提取到百分比",
                source="regex",
            )

        # 合理性检查
        extreme_pcts = [float(p) for p in pcts if float(p) > 1000]
        if extreme_pcts:
            return ClaimVerification(
                claim=claim, claim_type=ClaimType.COMPUTATIONAL.value,
                verified=False, confidence=0.2,
                reason=f"百分比超出合理范围: {extreme_pcts}",
                source="format_check",
            )

        # 检查同比/环比方向
        is_growth = any(w in claim for w in ["增长", "上升", "同比"])
        is_decline = any(w in claim for w in ["下降", "减少", "下滑"])
        if is_growth and is_decline:
            return ClaimVerification(
                claim=claim, claim_type=ClaimType.COMPUTATIONAL.value,
                verified=False, confidence=0.3,
                reason="同时包含增长与下降关键词，可能矛盾",
                source="format_check",
            )

        # 记忆对照
        evidence: List[Dict[str, Any]] = []
        if memory_system is not None:
            try:
                items = self._search_memory(memory_system, keyword=claim[:30], limit=3)
                for item in items:
                    content = str(item.get("content") or "")
                    mem_pcts = re.findall(r'(\d+(?:\.\d+)?)\s*%', content)
                    if mem_pcts:
                        evidence.append({
                            "source": "memory",
                            "memory_pcts": mem_pcts,
                            "content_snippet": content[:100],
                        })
            except Exception:
                pass

        confidence = 0.85 if evidence else 0.7
        reason = f"百分比 {pcts} 在合理范围内" + (f"，{len(evidence)} 条记忆对照" if evidence else "")
        return ClaimVerification(
            claim=claim, claim_type=ClaimType.COMPUTATIONAL.value,
            verified=True, confidence=confidence,
            reason=reason,
            evidence=evidence,
            source="memory" if evidence else "format_check",
        )

    # ── 辅助方法 ──────────────────────────────────────────────────

    @staticmethod
    def _search_memory(
        memory_system: Any,
        keyword: str = "",
        symbol: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """从 memory 检索条目（兼容多种接口）

        优先级：
        1. search_by_layer（B3 多因子召回）
        2. search_long_term + search_short_term
        3. 空列表
        """
        results: List[Dict[str, Any]] = []
        # 优先 B3 跨层检索
        if hasattr(memory_system, "search_by_layer"):
            try:
                items = memory_system.search_by_layer(
                    query=keyword, layer="all", top_k=limit
                )
                if symbol:
                    items = [i for i in items if i.get("symbol") in (symbol, "", None)]
                return items[:limit]
            except Exception:
                pass
        # 降级 L3
        if hasattr(memory_system, "search_long_term"):
            try:
                items = memory_system.search_long_term(
                    symbol=symbol, keyword=keyword, limit=limit
                )
                results.extend(items)
            except Exception:
                pass
        # 降级 L2
        if hasattr(memory_system, "search_short_term") and len(results) < limit:
            try:
                items = memory_system.search_short_term(
                    symbol=symbol, keyword=keyword, limit=limit - len(results)
                )
                results.extend(items)
            except Exception:
                pass
        return results[:limit]
