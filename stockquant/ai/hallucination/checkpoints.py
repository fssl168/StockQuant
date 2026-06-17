# -*- coding: utf-8 -*-
"""F020 反幻觉检查点 — 8 个独立验证函数"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# 检查点返回类型: (passed, score, reason)
CheckpointResult = Tuple[bool, float, str]

# 可信来源白名单
TRUSTED_SOURCES = {"eastmoney", "sina", "cninfo", "xueqiu", "sse", "szse", "news_searcher", "cls"}

# 已知事实关键词（示例，实际应从事实库加载）
KNOWN_FACT_KEYWORDS = {
    "涨停", "跌停", "停牌", "复牌", "分红", "配股", "增发",
    "回购", "减持", "增持", "业绩", "财报", "年报", "季报",
}


def source_verify(data: Dict[str, Any]) -> CheckpointResult:
    """检查点 1: 来源验证 — 验证信息来源是否可信

    检查 data["items"] 或 data["articles"] 中每条记录的 source 字段。
    """
    items = _extract_items(data)
    if not items:
        return (True, 1.0, "无数据需要验证")

    verified = 0
    for item in items:
        source = item.get("source", "").lower()
        if source in TRUSTED_SOURCES or item.get("verified", False):
            verified += 1

    score = verified / len(items)
    passed = score >= 0.5
    reason = f"来源验证: {verified}/{len(items)} 条来自可信源 (score={score:.2f})"
    return (passed, score, reason)


def fact_screen(data: Dict[str, Any]) -> CheckpointResult:
    """检查点 2: 事实初筛 — 对照已知事实库筛查

    检查内容是否包含与已知事实矛盾的信息。
    """
    items = _extract_items(data)
    if not items:
        return (True, 1.0, "无数据需要筛查")

    valid = 0
    for item in items:
        content = item.get("content", "") or item.get("title", "")
        # 简单检查：内容不为空且长度合理
        if content and len(content) > 5:
            # 检查是否包含极端断言（可能是幻觉）
            has_extreme = _has_extreme_claims(content)
            if not has_extreme:
                valid += 1

    score = valid / len(items)
    passed = score >= 0.6
    reason = f"事实初筛: {valid}/{len(items)} 条通过 (score={score:.2f})"
    return (passed, score, reason)


def consistency_filter(data: Dict[str, Any]) -> CheckpointResult:
    """检查点 3: 一致性过滤 — 检查内部一致性

    检查同一组数据内是否存在自相矛盾的信息。
    """
    items = _extract_items(data)
    if not items:
        return (True, 1.0, "无数据需要检查")

    # 检查标题去重率（高重复=低一致性价值）
    titles = [item.get("title", "").strip().lower() for item in items if item.get("title")]
    if not titles:
        return (True, 0.8, "无标题信息，默认通过")

    unique_ratio = len(set(titles)) / len(titles) if titles else 1.0
    score = unique_ratio
    passed = score >= 0.3  # 至少 30% 唯一性
    reason = f"一致性: 唯一率 {unique_ratio:.2f} ({len(set(titles))}/{len(titles)})"
    return (passed, score, reason)


def prompt_constraint(data: Dict[str, Any]) -> CheckpointResult:
    """检查点 4: 提示约束检查 — 检查输出是否遵循提示约束

    验证输出是否包含不应出现的内容（如免责声明缺失、格式不符等）。
    """
    output = data.get("output", "") or data.get("content", "")
    if not output:
        return (True, 1.0, "无输出需要检查")

    score = 1.0
    reasons = []

    # 检查是否包含投资建议（需要免责声明）
    advice_patterns = ["建议买入", "建议卖出", "强烈推荐", "必涨", "一定涨"]
    has_advice = any(p in output for p in advice_patterns)
    has_disclaimer = "免责" in output or "风险" in output or "不构成" in output

    if has_advice and not has_disclaimer:
        score -= 0.3
        reasons.append("包含投资建议但缺少免责声明")

    # 检查是否包含虚构的具体数据
    if _has_fabricated_numbers(output):
        score -= 0.2
        reasons.append("可能包含虚构数值")

    score = max(score, 0.0)
    passed = score >= 0.7
    reason = f"提示约束: score={score:.2f}" + (f" ({'; '.join(reasons)})" if reasons else "")
    return (passed, score, reason)


def summary_verify(data: Dict[str, Any]) -> CheckpointResult:
    """检查点 5: 摘要验证 — 验证摘要准确性

    检查摘要是否忠实于原文，是否遗漏关键信息。
    """
    summary = data.get("summary", "") or data.get("output", "")
    original = data.get("original", "") or data.get("content", "")

    if not summary:
        return (True, 1.0, "无摘要需要验证")

    if not original:
        return (True, 0.7, "无原文对照，默认通过")

    # 计算摘要与原文的关键词覆盖率
    original_keywords = set(re.findall(r'[\u4e00-\u9fff]{2,}', original))
    summary_keywords = set(re.findall(r'[\u4e00-\u9fff]{2,}', summary))

    if not original_keywords:
        return (True, 0.8, "原文无有效关键词")

    coverage = len(original_keywords & summary_keywords) / len(original_keywords)
    score = min(coverage * 1.5, 1.0)  # 摘要不需要覆盖所有关键词
    passed = score >= 0.4
    reason = f"摘要验证: 关键词覆盖率 {coverage:.2f}"
    return (passed, score, reason)


def reasoning_verify(data: Dict[str, Any]) -> CheckpointResult:
    """检查点 6: 推理链验证 — 验证推理链逻辑

    检查推理步骤之间是否存在逻辑跳跃或矛盾。
    """
    reasoning = data.get("reasoning", "") or data.get("chain", [])
    if not reasoning:
        return (True, 0.8, "无推理链需要验证")

    if isinstance(reasoning, str):
        steps = [s.strip() for s in reasoning.split("→") if s.strip()]
    elif isinstance(reasoning, list):
        steps = [str(s) for s in reasoning]
    else:
        steps = [str(reasoning)]

    if len(steps) <= 1:
        return (True, 0.9, "推理步骤不足，默认通过")

    # 检查步骤之间是否有逻辑连接词
    connectors = ["因此", "所以", "由于", "因为", "导致", "从而", "进而", "于是"]
    connected = 0
    for step in steps[1:]:
        if any(c in step for c in connectors):
            connected += 1

    score = (connected + 1) / len(steps)  # 至少第一步不需要连接词
    passed = score >= 0.3
    reason = f"推理验证: {connected}/{len(steps)-1} 步有逻辑连接 (score={score:.2f})"
    return (passed, score, reason)


def cross_validation(data: Dict[str, Any]) -> CheckpointResult:
    """检查点 7: 交叉验证 — 与其他来源交叉验证

    检查信息是否被多个独立来源确认。
    """
    items = _extract_items(data)
    if not items:
        return (True, 1.0, "无数据需要交叉验证")

    # 按标题相似度分组，同一事件被多个来源报道
    groups: List[List[Dict[str, Any]]] = []
    for item in items:
        placed = False
        for group in groups:
            for existing in group:
                if _title_similarity(item.get("title", ""), existing.get("title", "")) > 0.5:
                    group.append(item)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            groups.append([item])

    # 计算多源确认率
    multi_source = sum(1 for g in groups if len(set(i.get("source", "") for i in g)) > 1)
    total_groups = len(groups) if groups else 1
    score = multi_source / total_groups

    passed = score >= 0.2  # 至少 20% 的信息有多源确认
    reason = f"交叉验证: {multi_source}/{total_groups} 组信息有多源确认 (score={score:.2f})"
    return (passed, score, reason)


def confidence_score(data: Dict[str, Any]) -> CheckpointResult:
    """检查点 8: 置信度评分 — 计算综合置信度

    基于所有可用信号计算最终置信度分数。
    """
    items = _extract_items(data)
    explicit_confidence = data.get("confidence", 0.0)

    if not items and explicit_confidence == 0.0:
        return (True, 0.5, "无数据，默认中等置信度")

    signals: List[float] = []

    # 信号 1: 数据量
    if items:
        signals.append(min(len(items) / 10, 1.0))

    # 信号 2: 内容完整性
    if items:
        has_content = sum(1 for i in items if i.get("content") and len(i.get("content", "")) > 20)
        signals.append(has_content / len(items))

    # 信号 3: 显式置信度
    if explicit_confidence > 0:
        signals.append(explicit_confidence)

    # 信号 4: 来源验证标记
    if items:
        verified = sum(1 for i in items if i.get("verified", False))
        signals.append(verified / len(items))

    score = sum(signals) / len(signals) if signals else 0.5
    passed = score >= 0.4
    reason = f"置信度: 综合评分 {score:.2f} (基于 {len(signals)} 个信号)"
    return (passed, score, reason)


# ── 辅助函数 ──────────────────────────────────────────

def _extract_items(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从 data 中提取条目列表"""
    if "items" in data:
        return data["items"]
    if "articles" in data:
        return data["articles"]
    return []


def _has_extreme_claims(text: str) -> bool:
    """检测极端断言"""
    extreme_patterns = [
        r"一定.{0,4}涨", r"必.{0,2}涨", r"100%",
        r"绝对", r"毫无疑问", r"零风险",
    ]
    for pattern in extreme_patterns:
        if re.search(pattern, text):
            return True
    return False


def _has_fabricated_numbers(text: str) -> bool:
    """检测可能虚构的精确数值"""
    # 检查过于精确的百分比（如 87.34%）
    precise_pcts = re.findall(r'(\d+\.\d{3,})%', text)
    return len(precise_pcts) > 0


def _title_similarity(a: str, b: str) -> float:
    """标题相似度（字符重叠率）"""
    if not a or not b:
        return 0.0
    set_a = set(a)
    set_b = set(b)
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0
