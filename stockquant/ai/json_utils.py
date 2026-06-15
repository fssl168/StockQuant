# -*- coding: utf-8 -*-
"""F028 健壮 JSON 解析工具 — 处理 LLM 输出的 4 层降级策略"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger("stockquant.ai")

# json_repair 是软依赖：如果安装了，尝试加载；否则跳过修复步骤
try:
    from json_repair import repair_json  # type: ignore[import-not-found, no-redef]

    _HAS_JSON_REPAIR = True
except ImportError:
    _HAS_JSON_REPAIR = False
    repair_json = None  # type: ignore[assignment]

# 重新导出，方便其他模块 import
__all__ = ["robust_json_parse", "repair_json", "_HAS_JSON_REPAIR"]


def _preprocess_llm_output(content: str) -> str:
    """
    预处理 LLM 输出的 JSON 文本，修复常见格式问题。

    处理步骤:
        1. 移除 // 单行注释
        2. 移除 /* */ 块注释
        3. Python True/False/None → JSON true/false/null
        4. 修复 } 或 ] 前的尾随逗号

    Parameters
    ----------
    content : str
        LLM 返回的原始文本，可能包含注释或 Python 字面量。

    Returns
    -------
    str
        预处理后的文本。

    Examples
    --------
    >>> _preprocess_llm_output('{"key": True, // comment\\n"n": None}')  # doctest: +SKIP
    '{"key": true, \\n"n": null}'
    """
    text = content

    # 1. 移除 // 单行注释（排除 URL 中的 :// ）
    text = re.sub(r'(?<!:)//.*$', '', text, flags=re.MULTILINE)

    # 2. 移除 /* */ 块注释
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

    # 3. Python 字面量 → JSON
    text = text.replace('True', 'true').replace('False', 'false').replace('None', 'null')

    # 4. 修复尾随逗号（}, 或 ], 前）
    text = re.sub(r',(\s*[\]}])', r'\1', text)

    return text


def _extract_from_markdown(text: str) -> Optional[str]:
    """
    从 Markdown 代码块中提取 JSON 内容。

    优先匹配 ```json 或 ``` 代码块，提取其中的内容。

    Parameters
    ----------
    text : str
        可能包含 Markdown 代码块的文本。

    Returns
    -------
    str | None
        提取出的 JSON 字符串；如果没有找到代码块则返回 None。

    Examples
    --------
    >>> _extract_from_markdown('```json\\n{"a": 1}\\n```')
    '{"a": 1}'
    >>> _extract_from_markdown('no code here') is None
    True
    """
    # 优先匹配 ```json ... ```
    match = re.search(r'```(?:json)?\s*\n(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _find_brace_positions(text: str) -> list[tuple[int, int]]:
    """
    找出文本中所有顶层（未嵌套）的平衡大括号对。

    用于处理 LLM 输出中包含多个 JSON 对象或 JSON 与文本混合的场景。

    Parameters
    ----------
    text : str
        待搜索的文本。

    Returns
    -------
    list[tuple[int, int]]
        每个元组 (open_idx, close_idx) 表示一个顶层平衡的大括号对
        的起始和结束索引。

    Examples
    --------
    >>> _find_brace_positions('{"a": 1}')
    [(0, 8)]
    >>> _find_brace_positions('x{"a": 1}y{"b": 2}z')  # doctest: +SKIP
    [(1, 9), (10, 18)]
    """
    positions: list[tuple[int, int]] = []
    depth = 0
    in_string = False
    escape_next = False
    open_idx = -1

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            if depth == 0:
                open_idx = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and open_idx >= 0:
                positions.append((open_idx, i + 1))
                open_idx = -1

    return positions


def robust_json_parse(content: str) -> Optional[dict]:
    """
    用 4 层降级策略解析 LLM 返回的 JSON 文本。

    降级策略:
        - Level 1: 从 Markdown 提取 → json.loads() → repair_json()
        - Level 2: 对原始文本直接 json.loads()
        - Level 3: 预处理后 repair_json() → json.loads()
        - Level 4: 用 _find_brace_positions 提取候选 → 逐个尝试解析

    任何一层成功解析即返回结果。所有层均失败时返回 None 并记录警告。

    Parameters
    ----------
    content : str
        LLM 返回的 JSON 文本，可能不完整、含注释、含 Python 字面量等。

    Returns
    -------
    dict | None
        解析出的字典；如果所有降级策略均失败，返回 None。

    Examples
    --------
    >>> robust_json_parse('{"a": 1}')  # doctest: +SKIP
    {'a': 1}
    >>> robust_json_parse('not json at all') is None  # doctest: +SKIP
    True
    """
    if not content or not isinstance(content, str):
        logger.warning("robust_json_parse: empty or non-string input")
        return None

    cleaned = content.strip()
    if not cleaned:
        logger.warning("robust_json_parse: empty string after strip")
        return None

    def _try_parse(text: str) -> Optional[dict]:
        """尝试直接 json.loads，仅接受 dict 结果"""
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
            return None
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug("json.loads failed: %s", e)
            return None

    def _try_repair_and_parse(text: str) -> Optional[dict]:
        """尝试 repair_json，仅接受 dict 结果"""
        if not _HAS_JSON_REPAIR or repair_json is None:
            return None
        try:
            repaired = repair_json(text)
            if isinstance(repaired, dict):
                return repaired
            # repair_json 可能返回 str（如 '[1,2]'），再尝试 json.loads
            if isinstance(repaired, str):
                data = json.loads(repaired)
                if isinstance(data, dict):
                    return data
                return None
            return None
        except Exception as e:
            logger.debug("repair_json failed: %s", e)
            return None

    # ---- Level 1: Markdown 提取 + 预处理 ----
    logger.debug("robust_json_parse: Level 1 — markdown extract + parse")
    md_text = _extract_from_markdown(cleaned)
    if md_text:
        preprocessed = _preprocess_llm_output(md_text)
        result = _try_parse(preprocessed)
        if result is not None:
            logger.info("Level 1 succeeded (markdown extract)")
            return result
        if _HAS_JSON_REPAIR:
            result = _try_repair_and_parse(preprocessed)
            if result is not None:
                logger.info("Level 1 succeeded (markdown extract + repair)")
                return result

    # ---- Level 2: 直接解析原始文本 ----
    logger.debug("robust_json_parse: Level 2 — direct parse")
    preprocessed = _preprocess_llm_output(cleaned)
    result = _try_parse(preprocessed)
    if result is not None:
        logger.info("Level 2 succeeded (direct parse)")
        return result

    # ---- Level 3: 预处理 + repair_json ----
    logger.debug("robust_json_parse: Level 3 — repair + parse")
    if _HAS_JSON_REPAIR:
        result = _try_repair_and_parse(preprocessed)
        if result is not None:
            logger.info("Level 3 succeeded (repair_json)")
            return result

    # ---- Level 4: Brace-position 提取 + 逐个尝试 ----
    logger.debug("robust_json_parse: Level 4 — brace extraction")
    brace_pairs = _find_brace_positions(cleaned)
    for start, end in brace_pairs:
        candidate = cleaned[start:end]
        candidate_pre = _preprocess_llm_output(candidate)
        result = _try_parse(candidate_pre)
        if result is not None:
            logger.info("Level 4 succeeded (brace extraction at %d:%d)", start, end)
            return result
        if _HAS_JSON_REPAIR:
            result = _try_repair_and_parse(candidate_pre)
            if result is not None:
                logger.info("Level 4 succeeded (brace extraction + repair at %d:%d)", start, end)
                return result

    logger.warning("robust_json_parse: all 4 levels failed for input of length %d", len(cleaned))
    return None
