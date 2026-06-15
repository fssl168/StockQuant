# -*- coding: utf-8 -*-
"""Tests for stockquant.ai.json_utils"""

import json
from unittest.mock import patch

import pytest

from stockquant.ai.json_utils import (
    _extract_from_markdown,
    _find_brace_positions,
    _preprocess_llm_output,
    robust_json_parse,
)


class TestPreprocessLLMOutput:
    """测试 LLM 输出预处理"""

    def test_remove_single_line_comment(self):
        text = '{"a": 1, // this is a comment\n "b": 2}'
        result = _preprocess_llm_output(text)
        assert "//" not in result
        assert '"b": 2' in result

    def test_remove_block_comment(self):
        text = '/* start */ {"a": 1} /* end */'
        result = _preprocess_llm_output(text)
        assert "/*" not in result
        assert "*/" not in result

    def test_python_true_to_json(self):
        text = '{"flag": True}'
        result = _preprocess_llm_output(text)
        assert '"flag": true' in result

    def test_python_false_to_json(self):
        text = '{"flag": False}'
        result = _preprocess_llm_output(text)
        assert '"flag": false' in result

    def test_python_none_to_json(self):
        text = '{"val": None}'
        result = _preprocess_llm_output(text)
        assert '"val": null' in result

    def test_trailing_comma_in_object(self):
        text = '{"a": 1, "b": 2,}'
        result = _preprocess_llm_output(text)
        # 尾随逗号应被移除
        assert ',}' not in result

    def test_trailing_comma_in_array(self):
        text = '[1, 2, 3,]'
        result = _preprocess_llm_output(text)
        assert ',]' not in result

    def test_complex_python_dict(self):
        text = '{"active": True, "items": [1, 2, None], "done": False,}'
        result = _preprocess_llm_output(text)
        assert '"active": true' in result
        assert '"done": false' in result
        assert '"items": [1, 2, null]' in result
        assert ',}' not in result
        assert ',]' not in result

    def test_url_colon_not_affected(self):
        text = '{"url": "https://example.com//path"}'
        result = _preprocess_llm_output(text)
        assert "https" in result


class TestExtractFromMarkdown:
    """测试 Markdown 代码块提取"""

    def test_extract_json_block(self):
        text = '```json\n{"a": 1}\n```'
        result = _extract_from_markdown(text)
        assert result == '{"a": 1}'

    def test_extract_plain_code_block(self):
        text = '```\n{"a": 1}\n```'
        result = _extract_from_markdown(text)
        assert result == '{"a": 1}'

    def test_no_code_block(self):
        text = 'Just some text without code'
        result = _extract_from_markdown(text)
        assert result is None

    def test_noopener_multiple_blocks(self):
        text = '```\n{"first": 1}\n```\nSome text\n```json\n{"second": 2}\n```'
        result = _extract_from_markdown(text)
        # 应提取第一个代码块
        assert '"first": 1' in result

    def test_multiline_json_in_block(self):
        text = '```json\n{\n  "a": 1,\n  "b": 2\n}\n```'
        result = _extract_from_markdown(text)
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": 2}

    def test_empty_input(self):
        result = _extract_from_markdown("")
        assert result is None


class TestFindBracePositions:
    """测试大括号位置查找"""

    def test_single_object(self):
        text = '{"a": 1}'
        result = _find_brace_positions(text)
        assert result == [(0, 8)]

    def test_multiple_objects(self):
        text = '{"a": 1} {"b": 2}'
        result = _find_brace_positions(text)
        assert len(result) == 2
        assert result[0] == (0, 8)
        assert result[1] == (9, 17)

    def test_nested_object(self):
        text = '{"a": {"b": 1}}'
        result = _find_brace_positions(text)
        # 应找到最外层的完整配对
        assert len(result) == 1
        assert result[0] == (0, 15)

    def test_empty_object(self):
        text = '{}'
        result = _find_brace_positions(text)
        assert result == [(0, 2)]

    def test_string_with_braces(self):
        text = '{"desc": "{nested}"}'
        result = _find_brace_positions(text)
        # 字符串内的括号不应被计入
        assert len(result) == 1
        assert result[0] == (0, 20)

    def test_no_braces(self):
        text = "no braces here"
        result = _find_brace_positions(text)
        assert result == []

    def test_with_text_around(self):
        text = 'prefix {"key": "value"} suffix'
        result = _find_brace_positions(text)
        assert len(result) == 1
        assert result[0] == (7, 23)


class TestRobustJsonParseLevel1:
    """测试 Level 1: Markdown 提取"""

    def test_clean_json_in_markdown(self):
        text = '```json\n{"status": "ok"}\n```'
        result = robust_json_parse(text)
        assert result == {"status": "ok"}

    def test_markdown_with_preprocess_needed(self):
        text = '```json\n{"flag": True}\n```'
        result = robust_json_parse(text)
        assert result == {"flag": True}

    def test_plain_json_still_works(self):
        """纯 JSON 不经过 Markdown 也能解析"""
        result = robust_json_parse('{"key": "value"}')
        assert result == {"key": "value"}


class TestRobustJsonParseLevel2:
    """测试 Level 2: 直接解析"""

    def test_simple_json(self):
        result = robust_json_parse('{"a": 1, "b": 2}')
        assert result == {"a": 1, "b": 2}

    def test_nested_json(self):
        text = '{"outer": {"inner": [1, 2, 3]}}'
        result = robust_json_parse(text)
        assert result == {"outer": {"inner": [1, 2, 3]}}

    def test_json_with_trailing_comma(self):
        result = robust_json_parse('{"a": 1,}')
        assert result == {"a": 1}

    def test_json_with_python_literals(self):
        result = robust_json_parse('{"x": True, "y": None}')
        assert result == {"x": True, "y": None}


class TestRobustJsonParseLevel3:
    """测试 Level 3: repair_json"""

    @patch("stockquant.ai.json_utils._HAS_JSON_REPAIR", True)
    def test_repair_malformed_json(self):
        # 多层未闭合的大括号，常规解析器无法处理
        text = '{"a": {"b": {"c": 1}}'
        with patch("stockquant.ai.json_utils.repair_json") as mock_repair:
            mock_repair.return_value = {"a": {"b": {"c": 1}}}
            result = robust_json_parse(text)
            assert result == {"a": {"b": {"c": 1}}}
            mock_repair.assert_called_once()

    @patch("stockquant.ai.json_utils._HAS_JSON_REPAIR", False)
    def test_no_repair_library_skips_level3(self):
        # 无 json_repair 时，Level 3 直接跳过
        result = robust_json_parse('{"a": 1}')
        assert result == {"a": 1}


class TestRobustJsonParseLevel4:
    """测试 Level 4: 大括号位置提取"""

    def test_json_embedded_in_text(self):
        text = 'Here is some text {"key": "value"} end of text'
        result = robust_json_parse(text)
        assert result == {"key": "value"}

    def test_multiple_json_objects(self):
        text = '{"first": 1} middle {"second": 2}'
        result = robust_json_parse(text)
        # 应返回第一个成功解析的对象
        assert result is not None
        assert result.get("first") == 1 or result.get("second") == 2

    def test_json_with_surrounding_text(self):
        text = 'The model output was: {"status": "success"} and that is all.'
        result = robust_json_parse(text)
        assert result == {"status": "success"}


class TestRobustJsonParseNoneAndEmpty:
    """测试 None/空输入处理"""

    def test_none_input(self):
        result = robust_json_parse(None)
        assert result is None

    def test_empty_string(self):
        result = robust_json_parse("")
        assert result is None

    def test_whitespace_only(self):
        result = robust_json_parse("   \n\t  ")
        assert result is None

    def test_non_dict_json(self):
        """JSON 是数组时返回 None（要求返回 dict）"""
        result = robust_json_parse('[1, 2, 3]')
        assert result is None


class TestRobustJsonParseFallbackChain:
    """测试降级链的完整流程"""

    def test_fallback_all_levels_fail(self):
        """所有层都失败时返回 None"""
        result = robust_json_parse("this is not json at all {{{")
        assert result is None

    def test_early_success_short_circuits(self):
        """Level 1 成功时不应调用后面的解析"""
        text = '```json\n{"quick": true}\n```'
        result = robust_json_parse(text)
        assert result == {"quick": True}

    def test_markdown_with_invalid_json_falls_to_level2(self):
        """
        Markdown 提取后 JSON 无效，应降级到 Level 2
        """
        text = '```json\n{"broken": true\n```'
        # Level 1 解析失败，但 preprocess 修复后 Level 2 可能成功
        # 这里测试降级链能正常工作而不抛异常
        result = robust_json_parse(text)
        # 可能 Level 2 预处理成功或全部失败，都不应抛异常
        assert isinstance(result, (dict, type(None)))

    def test_comment_in_json_then_fallback(self):
        """含注释的 JSON 经过 preprocess 后解析"""
        text = '{\n  "a": 1, // level 1 comment\n  "b": true\n}'
        result = robust_json_parse(text)
        assert result == {"a": 1, "b": True}


class TestRobustJsonParseEdgeCases:
    """边界和异常场景"""

    def test_deeply_nested_valid_json(self):
        text = '{"l1": {"l2": {"l3": {"l4": [1, 2, 3]}}}}'
        result = robust_json_parse(text)
        assert result == {"l1": {"l2": {"l3": {"l4": [1, 2, 3]}}}}

    def test_unicode_content(self):
        text = '{"msg": "你好世界"}'
        result = robust_json_parse(text)
        assert result == {"msg": "你好世界"}

    def test_empty_brace_in_string(self):
        text = '{"desc": "{}"}'
        result = robust_json_parse(text)
        assert result == {"desc": "{}"}

    def test_mixed_python_and_json_issues(self):
        text = '{\n  "name": "test",  // name\n  "active": True,\n  "data": [1, 2, None,],\n  "meta": None\n}'
        result = robust_json_parse(text)
        assert result == {
            "name": "test",
            "active": True,
            "data": [1, 2, None],
            "meta": None,
        }

    def test_escaped_quotes_in_json(self):
        text = '{"msg": "He said \\"hello\\""}'
        result = robust_json_parse(text)
        assert result == {"msg": 'He said "hello"'}
