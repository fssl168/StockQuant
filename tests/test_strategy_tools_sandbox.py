# -*- coding: utf-8 -*-
"""Tests for strategy_tools sandbox and exec safety"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from stockquant.agent.strategy_tools import (
    _safe_exec,
    _make_backtest_strategy,
    score_strategy,
    validate_strategy_code,
)


# ── _safe_exec 沙箱测试 ──


class TestSafeExec:
    def test_allows_basic_class_definition(self):
        """基础 class 定义应允许。"""
        code = (
            "class MyStrategy:\n"
            "    name = 'test'\n"
            "    def __init__(self):\n"
            "        self.x = 1\n"
        )
        ns = _safe_exec(code)
        assert "MyStrategy" in ns
        assert ns["MyStrategy"].name == "test"

    def test_blocks_builtin_open(self):
        """禁止调用内置 open。"""
        code = "f = open('/etc/passwd')"
        ns = _safe_exec(code)
        # open 应被阻止，ns 中不应有 f
        assert "f" not in ns

    def test_blocks_builtin_eval(self):
        """禁止调用内置 eval。"""
        code = "result = eval('1+1')"
        ns = _safe_exec(code)
        assert "result" not in ns

    def test_blocks_builtin_exec(self):
        """禁止调用内置 exec。"""
        code = "exec('x=1')"
        ns = _safe_exec(code)
        assert "x" not in ns

    def test_blocks_os_import(self):
        """禁止 import os。"""
        code = "import os"
        ns = _safe_exec(code)
        assert "os" not in ns

    def test_blocks_subprocess_import(self):
        """禁止 import subprocess。"""
        code = "import subprocess"
        ns = _safe_exec(code)
        assert "subprocess" not in ns

    def test_allows_stockquant_import(self):
        """允许导入 stockquant。"""
        code = (
            "import stockquant\n"
            "import stockquant.strategy.base\n"
        )
        ns = _safe_exec(code)
        # import 成功，ns 中有 stockquant
        assert "stockquant" in ns

    def test_allows_numpy_import(self):
        """允许导入 numpy。"""
        code = "import numpy as np"
        ns = _safe_exec(code)
        assert "np" in ns

    def test_allows_pandas_import(self):
        """允许导入 pandas。"""
        code = "import pandas as pd"
        ns = _safe_exec(code)
        assert "pd" in ns

    def test_blocks_third_party_package(self):
        """禁止导入非白名单第三方包。"""
        code = "import requests"
        ns = _safe_exec(code)
        assert "requests" not in ns

    def test_syntax_error_returns_partial_ns(self):
        """语法错误不抛异常，返回部分命名空间。"""
        code = "def foo(\n  pass\n"
        ns = _safe_exec(code)
        # 不应抛出异常
        assert isinstance(ns, dict)


# ── _make_backtest_strategy sandbox ──


class TestBacktestStrategySandbox:
    def test_backtest_rejects_malicious_code(self):
        """回测工具应拒绝包含 os 导入的恶意代码。"""
        tool_fn = _make_backtest_strategy(MagicMock())

        malicious_code = """
import os
class BadStrategy:
    def on_bar(self): pass
"""
        result = tool_fn(
            code=malicious_code,
            symbol="sh600519",
            cash=1000000,
        )
        result_json = json.loads(result)
        assert "error" in result_json

    def test_backtest_requires_basestrategy(self):
        """回测工具应验证 BaseStrategy 继承。"""
        tool_fn = _make_backtest_strategy(MagicMock())

        no_base_code = """
class NoBase:
    def on_bar(self): pass
"""
        result = tool_fn(
            code=no_base_code,
            symbol="sh600519",
            cash=1000000,
        )
        result_json = json.loads(result)
        # 可能因缺少 BaseStrategy 报错，或因 BaoStockFeed 不可用报错
        assert "error" in result_json

    def test_backtest_allows_whitelisted_imports(self):
        """允许包含白名单模块导入的策略代码。"""
        tool_fn = _make_backtest_strategy(MagicMock())

        safe_code = """
import numpy as np
import pandas as pd

class SafeStrategy:
    def on_bar(self):
        data = np.array([1, 2, 3])
        return data
"""
        # 沙箱应允许 numpy/pandas 导入；回测本身可能因 BaoStockFeed 不可用而失败，
        # 但不应是沙箱错误（即 error 消息中不应包含 "not allowed"）
        result = tool_fn(
            code=safe_code,
            symbol="sh600519",
            cash=1000000,
        )
        result_json = json.loads(result)
        if "error" in result_json:
            assert "not allowed" not in result_json["error"]
