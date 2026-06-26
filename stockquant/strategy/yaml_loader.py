# -*- coding: utf-8 -*-
"""F031 YAML 策略加载器 — 零代码策略定义"""

from __future__ import annotations

import logging
from typing import Any, Dict, Type

import yaml

from stockquant.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)

# Indicator factory registry: maps YAML type name -> (import_path, factory_fn)
_INDICATOR_REGISTRY: Dict[str, Any] = {
    "MA": lambda data, **kw: __import__("stockquant.indicators.moving_avg", fromlist=["SMA"]).SMA(data, period=kw.get("period", 20)).calculate(),
    "EMA": lambda data, **kw: __import__("stockquant.indicators.moving_avg", fromlist=["EMA"]).EMA(data, period=kw.get("period", 12)).calculate(),
    "RSI": None,   # resolved lazily
    "MACD": None,
    "BOLL": None,
    "ATR": None,
    "KDJ": None,
}


def _resolve_indicator(ind_type: str, data, **params) -> Any:
    """根据类型名解析指标计算"""
    if ind_type == "MA" or ind_type == "SMA":
        from stockquant.indicators.moving_avg import SMA as _SMA
        return _SMA(data, period=params.get("period", 20)).calculate()
    elif ind_type == "EMA":
        from stockquant.indicators.moving_avg import EMA as _EMA
        return _EMA(data, period=params.get("period", 12)).calculate()
    elif ind_type == "RSI":
        from stockquant.indicators.oscillators import RSI as _RSI
        return _RSI(data, timeperiod=params.get("period", 14)).calculate()
    elif ind_type == "MACD":
        from stockquant.indicators.trend import MACD as _MACD
        return _MACD(
            data,
            fastperiod=params.get("fast", 12),
            slowperiod=params.get("slow", 26),
            signalperiod=params.get("signal", 9),
        ).calculate()
    elif ind_type == "BOLL":
        from stockquant.indicators.volatility import BOLL as _BOLL
        return _BOLL(data, timeperiod=params.get("period", 20)).calculate()
    elif ind_type == "ATR":
        from stockquant.indicators.volatility import ATR as _ATR
        return _ATR(
            params.get("high", data),
            params.get("low", data),
            data,
            timeperiod=params.get("period", 14),
        ).calculate()
    elif ind_type == "KDJ":
        from stockquant.indicators.oscillators import KDJ as _KDJ
        return _KDJ(
            params.get("high", data),
            params.get("low", data),
            data,
            fastk_period=params.get("fastk", 9),
            slowk_period=params.get("slowk", 3),
            slowd_period=params.get("slowd", 3),
        ).calculate()
    else:
        raise ValueError(f"Unknown indicator type: {ind_type}")


class YamlStrategyLoader:
    """从 YAML 定义加载策略。

    支持的 YAML 格式：

    ```yaml
    name: "Dual MA Crossover"
    description: "双均线交叉策略"

    indicators:
      fast_ma:
        type: "MA"
        params: {period: 5}
      slow_ma:
        type: "MA"
        params: {period: 20}

    entry_rules:
      - condition: "fast_ma > slow_ma"
        action: "BUY"
        confidence: 0.8

    exit_rules:
      - condition: "fast_ma < slow_ma"
        action: "SELL"
        confidence: 0.7

    position:
      method: "FixedFraction"
      params: {pct: 0.3}

    risk:
      max_position_pct: 0.3
      max_daily_loss_pct: 0.02
      max_drawdown_pct: 0.15
    ```
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Type[BaseStrategy]] = {}

    def load(self, yaml_path: str) -> Type[BaseStrategy]:
        """从 YAML 文件加载策略类。

        Returns
        -------
        Type[BaseStrategy]
            动态生成的策略类（尚未实例化）。
        """
        with open(yaml_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self.load_string(content, source=yaml_path)

    def load_string(self, yaml_content: str, source: str = "<string>") -> Type[BaseStrategy]:
        """从 YAML 字符串加载策略类。

        Parameters
        ----------
        yaml_content : str
            YAML 格式的策略定义
        source : str
            来源标识（用于缓存键和日志）

        Returns
        -------
        Type[BaseStrategy]
        """
        config: Dict[str, Any] = yaml.safe_load(yaml_content)
        if not isinstance(config, dict):
            raise ValueError(f"YAML must be a mapping, got {type(config).__name__}")

        cache_key = f"{source}:{id(config)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        strategy_cls = self._build_strategy_class(config)
        self._cache[cache_key] = strategy_cls
        logger.info(f"Loaded YAML strategy: {strategy_cls.name} (from {source})")
        return strategy_cls

    def _build_strategy_class(self, config: Dict[str, Any]) -> Type[BaseStrategy]:
        """根据 YAML 配置动态生成策略类。

        使用 Python ``type()`` 构造器创建新类，覆盖 ``on_start`` 和
        ``on_bar`` 以实现在 YAML 中定义的交易逻辑。
        """
        name = config.get("name", "YAML Strategy")
        indicators_cfg = config.get("indicators", {})
        entry_rules = config.get("entry_rules", [])
        exit_rules = config.get("exit_rules", [])
        risk_cfg = config.get("risk", {})

        class _YamlStrategy(BaseStrategy):
            pass

        _YamlStrategy.name = name
        _YamlStrategy.__module__ = __name__

        # --- on_start: 初始化指标 ---
        def on_start(self: BaseStrategy) -> None:
            self._yaml_indicators: Dict[str, Any] = {}
            self._yaml_price_hist: Dict[str, list] = {}
            self._yaml_previous_signals: Dict[str, str] = {}

            for ind_name, ind_def in indicators_cfg.items():
                ind_type = ind_def.get("type", "MA")
                ind_params = ind_def.get("params", {})
                # Store indicator definition for on_bar
                self._yaml_indicators[ind_name] = (ind_type, ind_params)

            # Risk config
            self._yaml_risk = risk_cfg

            # Position sizing configuration
            self._yaml_position_method = config.get("position", {}).get("method", "FixedFraction")
            self._yaml_position_params = config.get("position", {}).get("params", {})

        _YamlStrategy.on_start = on_start

        # --- on_bar: 计算指标并执行规则 ---
        def on_bar(self: BaseStrategy, bars: Dict[str, Any]) -> None:
            for symbol, bar in bars.items():
                # Accumulate price history
                if symbol not in self._yaml_price_hist:
                    self._yaml_price_hist[symbol] = []
                self._yaml_price_hist[symbol].append(bar.close)

                closes = self._yaml_price_hist[symbol]

                # Calculate indicators
                for ind_name, (ind_type, ind_params) in self._yaml_indicators.items():
                    try:
                        indicator_value = _resolve_indicator(ind_type, closes, **ind_params)
                        # Store last value for rule evaluation
                        if hasattr(indicator_value, '__len__') and len(indicator_value) > 0:
                            self._yaml_indicators[f"{ind_name}_value"] = indicator_value[-1]
                            if len(indicator_value) >= 2:
                                self._yaml_indicators[f"{ind_name}_prev"] = indicator_value[-2]
                        else:
                            self._yaml_indicators[f"{ind_name}_value"] = indicator_value
                    except Exception as exc:
                        logger.debug(f"Indicator {ind_name} for {symbol}: {exc}")

                # Evaluate rules
                signal = self._yaml_eval_rules(symbol, entry_rules, exit_rules)
                if signal and signal != self._yaml_previous_signals.get(symbol):
                    self._yaml_previous_signals[symbol] = signal
                    self._yaml_execute_action(symbol, bar, signal)

        _YamlStrategy.on_bar = on_bar

        # --- 内部方法 ---
        def _eval_rules(self: BaseStrategy, symbol: str,
                        entries: list, exits: list) -> str | None:
            """Evaluate entry/exit rules and return action string."""
            indicators = self._yaml_indicators

            # Check entry rules
            for rule in entries:
                if self._eval_condition(rule["condition"], indicators):
                    return f"BUY:{rule.get('action', 'BUY')}"

            # Check exit rules
            for rule in exits:
                if self._eval_condition(rule["condition"], indicators):
                    return f"SELL:{rule.get('action', 'SELL')}"

            return None

        _YamlStrategy._yaml_eval_rules = _eval_rules

        def _execute_action(self: BaseStrategy, symbol: str, bar: Any, action_str: str) -> None:
            """Execute BUY or SELL action based on rule result."""
            if not action_str.startswith("BUY") and not action_str.startswith("SELL"):
                return

            risk = self._yaml_risk
            max_pos = risk.get("max_position_pct", 0.3)
            pct = self._yaml_position_params.get("pct", max_pos)

            if action_str.startswith("BUY"):
                try:
                    qty = int(self.cash * pct / bar.close / 100) * 100
                    if qty > 0:
                        self.order_market(bar, qty)
                        self.log(f"YAML BUY: {symbol} qty={qty} (rule: {action_str})")
                except Exception as exc:
                    logger.warning(f"YAML BUY execution failed for {symbol}: {exc}")
            else:
                try:
                    self.order_sell(bar, 100)
                    self.log(f"YAML SELL: {symbol} qty=100 (rule: {action_str})")
                except Exception as exc:
                    logger.warning(f"YAML SELL execution failed for {symbol}: {exc}")

        _YamlStrategy._yaml_execute_action = _execute_action

        def _eval_condition(self: BaseStrategy, condition: str,
                            indicators: dict) -> bool:
            """简单条件求值。

            支持比较表达式: "fast_ma > slow_ma", "price > boll_upper", etc.
            """

            # Replace indicator names with their values
            # Sort by name length descending to avoid partial replacement
            sorted_names = sorted(indicators.keys(), key=len, reverse=True)
            expr = condition

            for name in sorted_names:
                if not name.endswith("_value") and not name.endswith("_prev"):
                    continue
                val = indicators.get(name)
                if val is None:
                    continue
                # Use repr to avoid partial replacement issues
                placeholder = f"__YAML_VAL_{name}__"
                expr = expr.replace(name, placeholder)
                indicators[placeholder] = val

            # Also replace raw indicator names that have _value set
            for name in sorted(indicators.keys(), key=len, reverse=True):
                if name.endswith("_value") or name.endswith("_prev"):
                    val = indicators[name]
                    placeholder = f"__YAML_V_{name}__"
                    expr = expr.replace(name, placeholder)
                    indicators[placeholder] = val

            # Evaluate the expression safely
            try:
                local_ns: Dict[str, float] = {}
                for k, v in indicators.items():
                    if isinstance(k, str) and k.startswith("__YAML"):
                        local_ns[k] = float(v)

                result = eval(expr, {"__builtins__": {}}, local_ns)  # noqa: S307
                return bool(result)
            except Exception:
                logger.debug(f"Condition evaluation failed: {condition}")
                return False

        _YamlStrategy._eval_condition = _eval_condition

        return _YamlStrategy
