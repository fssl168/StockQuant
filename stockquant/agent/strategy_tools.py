# -*- coding: utf-8 -*-
"""F022 策略生成工具集 — 6 个 @tool 注册到 ToolRegistry"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from stockquant.agent.tool_registry import tool
from stockquant.ai.json_utils import robust_json_parse
from stockquant.ai.models import (
    StrategyScore,
    ValidationResult,
)
from stockquant.api.routers.settings import build_data_feed

logger = logging.getLogger("stockquant.agent")


# ── Tool 1: parse_strategy_intent ──


def _make_parse_strategy_intent(adapter: Any) -> Any:
    """工厂函数：创建带 LLM 闭包的意图解析工具。"""

    @tool
    def parse_strategy_intent(description: str) -> str:
        """解析自然语言策略描述为结构化策略意图。

        提取技术指标、入场/出场条件、仓位管理、风控参数等要素。

        Parameters
        ----------
        description : str
            自然语言策略描述，如"当MACD金叉且RSI<30时买入，仓位20%，止损5%"
        """
        prompt = f"""请将以下自然语言策略描述解析为结构化 JSON。

策略描述：{description}

输出格式（严格 JSON）：
{{
    "indicators": [
        {{"name": "MACD", "params": {{"fast": 12, "slow": 26, "signal": 9}}}},
        {{"name": "RSI", "params": {{"period": 14}}}}
    ],
    "entry_conditions": ["MACD 金叉", "RSI < 30"],
    "exit_conditions": ["MACD 死叉", "止损 5%"],
    "position_method": "FixedFraction",
    "position_params": {{"pct": 0.2}},
    "risk_params": {{"stop_loss": 0.05}}
}}

注意：
- indicators 中的 name 必须是 SQ 支持的指标：MA/EMA/RSI/MACD/BOLL/ATR/KDJ
- position_method 可选：FixedFraction/Kelly/ATRBased/EqualWeight
- stop_loss 为小数比例（如 0.05 表示 5%）
- 如果用户未指定某项，使用合理默认值
"""
        try:
            response = adapter.call(
                messages=[{"role": "user", "content": prompt}]
            )
            parsed = robust_json_parse(response.content or "")
            if parsed is None:
                return json.dumps({
                    "error": "Failed to parse LLM response as JSON",
                    "raw": response.content[:500],
                }, ensure_ascii=False)
            return json.dumps(parsed, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    return parse_strategy_intent


# ── Tool 2: generate_strategy_code ──


def _make_generate_strategy_code(adapter: Any) -> Any:
    """工厂函数：创建带 LLM 闭包的策略代码生成工具。"""

    @tool
    def generate_strategy_code(
        intent_json: str,
        strategy_name: str = "AIStrategy",
    ) -> str:
        """根据策略意图生成 BaseStrategy 子类代码。

        Parameters
        ----------
        intent_json : str
            策略意图 JSON 字符串（parse_strategy_intent 的输出）
        strategy_name : str
            策略类名
        """
        try:
            intent_data = json.loads(intent_json) if isinstance(intent_json, str) else intent_json
        except json.JSONDecodeError:
            intent_data = {"raw": intent_json}

        prompt = f"""请根据以下策略意图，生成一个完整的 StockQuant BaseStrategy 子类代码。

策略意图：
{json.dumps(intent_data, ensure_ascii=False, indent=2)}

代码规范：
1. 必须继承 BaseStrategy
2. 必须设置 name 和 parameters 类属性
3. 必须实现 on_start() 初始化指标
4. 必须实现 on_bar() 执行交易逻辑
5. 使用 self.SMA/EMA/RSI/MACD/BOLL/ATR/KDJ 创建指标
6. 使用 IndicatorProxy 的 crossed_above/crossed_below 判断交叉
7. 使用 self.order_market(bar, qty) 买入，self.order_sell(bar, qty) 卖出
8. 使用 self.log() 记录交易日志
9. 买入数量必须为 100 的整数倍（A 股规则）
10. 策略类名：{strategy_name}

只输出 Python 代码，不要输出任何解释文字。代码用 ```python ``` 包裹。
"""
        try:
            response = adapter.call(
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.content or ""
            # 提取代码块
            code = _extract_code_block(content)
            return code
        except Exception as exc:
            return f"# Error generating strategy code: {exc}"


    return generate_strategy_code


# ── Tool 3: validate_strategy_code ──


@tool
def validate_strategy_code(code: str) -> str:
    """验证策略代码的可用性。

    三层验证：语法检查 → 导入检查 → 实例化检查。

    Parameters
    ----------
    code : str
        策略 Python 代码
    """
    result = ValidationResult()

    # Level 1: 语法检查
    try:
        compile(code, "<strategy>", "exec")
    except SyntaxError as e:
        result.errors.append(f"语法错误 (line {e.lineno}): {e.msg}")
        return json.dumps({"valid": False, "errors": result.errors, "warnings": result.warnings},
                          ensure_ascii=False)

    # Level 2: 导入检查 — 确保只引用 stockquant 内部模块
    allowed_prefixes = ("stockquant", "numpy", "pandas", "datetime", "typing", "abc", "dataclasses", "logging")
    try:
        compile(code, "<strategy>", "exec")
        # Simple check: look for import statements in the code
        for line in code.split("\n"):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                module = stripped.split("import")[0].replace("from", "").strip().split(".")[0]
                if module and not module.startswith(allowed_prefixes):
                    result.warnings.append(f"非标准导入: {stripped} (可能不可用)")
    except Exception as exc:
        result.warnings.append(f"导入检查异常: {exc}")

    # Level 3: 实例化检查 — 确保类定义包含必要方法
    required_methods = ["on_start", "on_bar"]
    for method in required_methods:
        if f"def {method}" not in code:
            result.errors.append(f"缺少必要方法: {method}")

    if "BaseStrategy" not in code:
        result.errors.append("策略类未继承 BaseStrategy")

    result.valid = len(result.errors) == 0
    return json.dumps({
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
    }, ensure_ascii=False)


# ── 安全辅助函数 ──


def _safe_exec(code: str) -> Dict[str, Any]:
    """在沙箱中执行策略代码。

    沙箱限制：
    - 移除危险 builtins（eval/exec/open/import 等）
    - 仅允许 stockquant/numpy/pandas/datetime/typing 等白名单模块导入
    - 捕获所有异常

    Parameters
    ----------
    code : str
        要执行的 Python 代码

    Returns
    -------
    Dict[str, Any]
        执行后的命名空间
    """
    _builtin_import = __import__  # 保存真实的 builtin __import__

    allowed_modules = {
        "stockquant", "numpy", "pandas", "datetime", "typing",
        "abc", "dataclasses", "logging", "math", "collections",
    }

    # 危险的内置函数
    _dangerous = {"eval", "exec", "open", "compile", "__import__",
                  "input", "breakpoint", "globals", "locals", "vars", "getattr",
                  "setattr", "delattr", "dir", "hasattr", "memoryview",
                  "copyright", "exit", "quit", "help", "__loader__",
                  "__spec__", "__build_class__"}

    def _restricted_import(name: str, *args, **kwargs):
        top = name.split(".")[0] if name else ""
        if top not in allowed_modules:
            raise ImportError(f"Module '{name}' not allowed in strategy sandbox")
        return _builtin_import(name, *args, **kwargs)

    # 基于真实 builtins 构建安全子集
    import builtins
    safe_builtins_dict = {
        k: v for k, v in vars(builtins).items()
        if not k.startswith("_") or k in ("__len__", "__iter__", "__getitem__",
                                           "__add__", "__call__", "__name__",
                                           "__import__", "__doc__", "__build_class__",
                                           "__subclasses__", "__contains__",
                                           "__enter__", "__exit__", "__await__",
                                           "__ge__", "__gt__", "__le__", "__lt__",
                                           "__eq__", "__ne__", "__and__", "__or__",
                                           "__mul__", "__truediv__", "__floordiv__",
                                           "__mod__", "__pow__", "__neg__", "__pos__",
                                           "__abs__", "__invert__", "__bool__",
                                           "__sizeof__", "__hash__", "__repr__",
                                           "__format__", "__reversed__", "__getitem__",
                                           "__delitem__", "__setitem__",
                                           "__iter__", "__next__", "__getattribute__",
                                           "__setattr__", "__reduce__", "__reduce_ex__",
                                           "__getstate__", "__class__", "__dict__",
                                           "__bases__", "__mro__", "__dictclass__",
                                           "__cause__", "__context__", "__traceback__",
                                           "__file__", "__path__", "__cached__",
                                           "__spec__", "__loader__",
                                           "__builtins__")
    }
    # 显式移除危险项
    for _k in ("eval", "exec", "open", "compile", "__import__",
               "input", "breakpoint", "globals", "locals", "vars",
               "getattr", "setattr", "delattr", "dir", "hasattr",
               "memoryview", "copyright", "exit", "quit", "help"):
        safe_builtins_dict.pop(_k, None)
    # 注入受限 __import__
    safe_builtins_dict["__import__"] = _restricted_import
    safe_builtins_dict["__name__"] = "sandbox"

    safe_ns: Dict[str, Any] = {"__builtins__": safe_builtins_dict}
    try:
        exec(compile(code, "<strategy_sandbox>", "exec"), safe_ns)
    except Exception as exc:
        logger.warning("Strategy sandbox exec error: %s", exc)
    return safe_ns


# ── Tool 4: backtest_strategy ──


def _make_backtest_strategy(fetcher_manager: Any) -> Any:
    """工厂函数：创建带数据源闭包的回测工具。"""

    @tool
    def backtest_strategy(
        code: str,
        symbol: str = "sh600519",
        start_date: str = "2023-01-01",
        end_date: str = "2024-12-31",
        cash: float = 1000000.0,
    ) -> str:
        """自动回测生成的策略代码。

        策略代码在沙箱中执行，仅允许导入 stockquant/numpy/pandas 等白名单模块。

        Parameters
        ----------
        code : str
            策略 Python 代码
        symbol : str
            回测标的代码
        start_date : str
            回测开始日期
        end_date : str
            回测结束日期
        cash : float
            初始资金
        """
        try:
            from stockquant.engine.cerebro import Cerebro

            # 沙箱执行策略代码，获取策略类
            namespace = _safe_exec(code)

            # 找到 BaseStrategy 的子类
            from stockquant.strategy.base import BaseStrategy
            strategy_cls = None
            for obj in namespace.values():
                if (isinstance(obj, type)
                        and issubclass(obj, BaseStrategy)
                        and obj is not BaseStrategy):
                    strategy_cls = obj
                    break

            if strategy_cls is None:
                return json.dumps({"error": "未找到 BaseStrategy 子类"}, ensure_ascii=False)

            # 构建回测（根据配置动态选择数据源）
            cerebro = Cerebro()
            feed = build_data_feed(
                symbols=[symbol],
                timeframe="1d",
                start_date=start_date,
                end_date=end_date,
            )
            cerebro.add_data(feed)
            cerebro.add_strategy(strategy_cls)
            cerebro.set_cash(cash)

            results = cerebro.run()
            if results:
                metrics = results[0] if isinstance(results[0], dict) else {}
                return json.dumps(metrics, ensure_ascii=False, default=str)
            return json.dumps({"error": "回测无结果"}, ensure_ascii=False)

        except Exception as exc:
            return json.dumps({"error": f"回测执行失败: {exc}"}, ensure_ascii=False)

    return backtest_strategy


# ── Tool 5: score_strategy ──


@tool
def score_strategy(backtest_result_json: str) -> str:
    """对回测结果进行多维度评分。

    从收益、风险、交易质量、稳定性 4 个维度评分。

    Parameters
    ----------
    backtest_result_json : str
        回测结果 JSON 字符串
    """
    try:
        metrics = json.loads(backtest_result_json) if isinstance(backtest_result_json, str) else backtest_result_json
    except json.JSONDecodeError:
        metrics = {}

    score = StrategyScore()

    # 收益维度 (0-100)
    try:
        ann_return = _parse_pct(metrics.get("Annualized Return", "0%"))
        if ann_return > 0.30:
            score.profitability = 90
        elif ann_return > 0.20:
            score.profitability = 75
        elif ann_return > 0.10:
            score.profitability = 60
        elif ann_return > 0:
            score.profitability = 40
        else:
            score.profitability = 10
    except (ValueError, TypeError):
        score.profitability = 30

    # 风险维度 (0-100, 回撤越小分越高)
    try:
        max_dd = _parse_pct(metrics.get("Max Drawdown", "50%"))
        if max_dd < 0.10:
            score.risk_control = 95
        elif max_dd < 0.20:
            score.risk_control = 75
        elif max_dd < 0.30:
            score.risk_control = 55
        else:
            score.risk_control = 25
    except (ValueError, TypeError):
        score.risk_control = 30

    # 交易质量维度 (0-100, 基于夏普和胜率)
    try:
        sharpe = float(metrics.get("Sharpe Ratio", 0))
        win_rate = _parse_pct(metrics.get("Win Rate", "50%"))
        quality_score = min(100, max(0, sharpe * 30 + win_rate * 50))
        score.trading_quality = round(quality_score)
    except (ValueError, TypeError):
        score.trading_quality = 30

    # 稳定性维度 (0-100, 基于 SQN 和交易次数)
    try:
        sqn = float(metrics.get("SQN (System Quality Number)", 0))
        total_trades = int(metrics.get("Total Trades", 0))
        stability_base = min(100, max(0, sqn * 20))
        # 交易次数过少扣分
        if total_trades < 10:
            stability_base *= 0.5
        elif total_trades < 30:
            stability_base *= 0.8
        score.stability = round(stability_base)
    except (ValueError, TypeError):
        score.stability = 30

    # 过拟合风险
    try:
        total_trades = int(metrics.get("Total Trades", 0))
        if total_trades < 10:
            score.overfitting_risk = "high"
        elif total_trades < 30:
            score.overfitting_risk = "medium"
        else:
            score.overfitting_risk = "low"
    except (ValueError, TypeError):
        score.overfitting_risk = "medium"

    # 综合分
    score.total = round(
        score.profitability * 0.30
        + score.risk_control * 0.30
        + score.trading_quality * 0.25
        + score.stability * 0.15
    )

    return json.dumps({
        "total": score.total,
        "profitability": score.profitability,
        "risk_control": score.risk_control,
        "trading_quality": score.trading_quality,
        "stability": score.stability,
        "overfitting_risk": score.overfitting_risk,
    }, ensure_ascii=False)


# ── Tool 6: suggest_improvements ──


def _make_suggest_improvements(adapter: Any) -> Any:
    """工厂函数：创建带 LLM 闭包的优化建议工具。"""

    @tool
    def suggest_improvements(
        code: str,
        score_json: str,
        backtest_result_json: str = "{}",
    ) -> str:
        """基于评分和回测结果，LLM 生成策略优化建议。

        Parameters
        ----------
        code : str
            策略代码
        score_json : str
            评分 JSON 字符串（score_strategy 的输出）
        backtest_result_json : str
            回测结果 JSON 字符串
        """
        prompt = f"""请根据以下策略代码、评分和回测结果，给出具体的优化建议。

策略代码：
```python
{code[:2000]}
```

评分：{score_json}

回测结果：{backtest_result_json[:1000]}

请输出 JSON 格式的建议列表：
[
    {{
        "category": "indicator|condition|risk|position",
        "description": "具体建议内容",
        "priority": "high|medium|low",
        "code_hint": "可选的代码片段提示"
    }}
]

最多给出 5 条建议，按优先级从高到低排列。
"""
        try:
            response = adapter.call(
                messages=[{"role": "user", "content": prompt}]
            )
            parsed = robust_json_parse(response.content or "")
            if parsed is None:
                # 尝试提取列表
                return json.dumps([{
                    "category": "general",
                    "description": response.content[:500] if response.content else "No suggestions",
                    "priority": "medium",
                    "code_hint": "",
                }], ensure_ascii=False)
            return json.dumps(parsed, ensure_ascii=False)
        except Exception as exc:
            return json.dumps([{
                "category": "general",
                "description": f"生成建议失败: {exc}",
                "priority": "low",
                "code_hint": "",
            }], ensure_ascii=False)

    return suggest_improvements


# ── 辅助函数 ──


def _extract_code_block(content: str) -> str:
    """从 LLM 响应中提取 Python 代码块。"""
    # 尝试提取 ```python ... ``` 代码块
    pattern = r"```(?:python)?\s*\n?(.*?)\n?```"
    matches = re.findall(pattern, content, re.DOTALL)
    if matches:
        return matches[0].strip()

    # 如果没有代码块标记，尝试找 class 定义
    if "class " in content and "BaseStrategy" in content:
        lines = content.split("\n")
        start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("class "):
                start = i
                break
        # 找到类定义的结尾（通过缩进判断）
        result_lines = []
        base_indent = None
        for line in lines[start:]:
            if line.strip() == "" and not result_lines:
                continue
            if base_indent is None:
                base_indent = len(line) - len(line.lstrip())
            current_indent = len(line) - len(line.lstrip()) if line.strip() else base_indent
            if current_indent < base_indent and result_lines and line.strip():
                break
            result_lines.append(line)
        return "\n".join(result_lines)

    return content.strip()


def _parse_pct(value: str) -> float:
    """解析百分比字符串为小数。"""
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).replace("%", "").strip()
    v = float(s)
    return v / 100 if abs(v) > 1 else v
