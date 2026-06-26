# -*- coding: utf-8 -*-
"""F025 决策验证工具集 — 6 个 @tool 注册到 ToolRegistry"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

import numpy as np

from stockquant.agent.tool_registry import tool
from stockquant.ai.json_utils import robust_json_parse

logger = logging.getLogger("stockquant.agent")


# ── Tool 1: verify_signal ──


def _make_verify_signal(fetcher_manager: Any) -> Any:
    """工厂函数：创建带数据源闭包的信号验证工具。"""

    @tool
    def verify_signal(
        symbol: str,
        direction: str,
        signal_type: str = "strategy",
    ) -> str:
        """对交易信号进行技术面二次确认。

        多指标交叉验证信号可靠性：MA 趋势 + MACD 动量 + RSI 超买超卖 + BOLL 位置。

        Parameters
        ----------
        symbol : str
            标的代码，如 "sh600519"
        direction : str
            交易方向 "BUY" 或 "SELL"
        signal_type : str
            信号来源类型
        """
        try:
            df = fetcher_manager.fetch(symbol, timeframe="1d")
            if df is None or df.empty or len(df) < 60:
                return json.dumps({
                    "confirmed": False,
                    "indicators_summary": {},
                    "contradictions": ["数据不足，无法验证"],
                }, ensure_ascii=False)

            closes = df["close"].values.astype(float)
            df["volume"].values.astype(float) if "volume" in df.columns else np.ones(len(closes))

            # MA 趋势判断
            ma5 = np.mean(closes[-5:])
            ma20 = np.mean(closes[-20:])
            ma60 = np.mean(closes[-60:]) if len(closes) >= 60 else ma20
            ma_trend = "多头排列" if ma5 > ma20 > ma60 else ("空头排列" if ma5 < ma20 < ma60 else "交叉震荡")

            # MACD 简易判断
            ema12 = _ema(closes, 12)
            ema26 = _ema(closes, 26)
            dif = ema12 - ema26
            dea = _ema(dif, 9)
            macd_hist = 2 * (dif - dea)
            macd_signal = "金叉/多头" if macd_hist[-1] > 0 and macd_hist[-1] > macd_hist[-2] else (
                "死叉/空头" if macd_hist[-1] < 0 and macd_hist[-1] < macd_hist[-2] else "震荡"
            )

            # RSI
            rsi = _calc_rsi(closes, 14)
            rsi_label = "超买" if rsi > 70 else ("超卖" if rsi < 30 else "中性")

            # BOLL 位置
            ma20_val = np.mean(closes[-20:])
            std20 = np.std(closes[-20:])
            upper = ma20_val + 2 * std20
            lower = ma20_val - 2 * std20
            current = closes[-1]
            boll_pos = "上轨上方" if current > upper else ("下轨下方" if current < lower else "轨道内")

            indicators_summary = {
                "MA": f"{ma_trend} (MA5={ma5:.2f}, MA20={ma20:.2f}, MA60={ma60:.2f})",
                "MACD": f"{macd_signal} (DIF={dif[-1]:.4f})",
                "RSI": f"{rsi:.1f} ({rsi_label})",
                "BOLL": f"{boll_pos} (上={upper:.2f}, 下={lower:.2f})",
            }

            # 交叉验证
            contradictions = []
            confirmations = []

            if direction == "BUY":
                if ma_trend == "空头排列":
                    contradictions.append(f"MA {ma_trend}，与买入信号矛盾")
                elif ma_trend == "多头排列":
                    confirmations.append(f"MA {ma_trend}，支持买入")

                if rsi > 70:
                    contradictions.append(f"RSI={rsi:.1f} 超买，与买入信号矛盾")
                elif rsi < 30:
                    confirmations.append(f"RSI={rsi:.1f} 超卖，支持买入")

                if macd_signal == "死叉/空头":
                    contradictions.append(f"MACD {macd_signal}，与买入信号矛盾")
                elif macd_signal == "金叉/多头":
                    confirmations.append(f"MACD {macd_signal}，支持买入")

                if boll_pos == "上轨上方":
                    contradictions.append(f"BOLL {boll_pos}，短期可能回调")

            elif direction == "SELL":
                if ma_trend == "多头排列":
                    contradictions.append(f"MA {ma_trend}，与卖出信号矛盾")
                elif ma_trend == "空头排列":
                    confirmations.append(f"MA {ma_trend}，支持卖出")

                if rsi < 30:
                    contradictions.append(f"RSI={rsi:.1f} 超卖，与卖出信号矛盾")
                elif rsi > 70:
                    confirmations.append(f"RSI={rsi:.1f} 超买，支持卖出")

            confirmed = len(contradictions) == 0 and len(confirmations) >= 2

            return json.dumps({
                "confirmed": confirmed,
                "indicators_summary": indicators_summary,
                "contradictions": contradictions,
                "confirmations": confirmations,
            }, ensure_ascii=False)

        except Exception as exc:
            return json.dumps({
                "confirmed": False,
                "indicators_summary": {},
                "contradictions": [f"验证异常: {exc}"],
            }, ensure_ascii=False)

    return verify_signal


# ── Tool 2: assess_risk ──


def _make_assess_risk() -> Any:
    """工厂函数：创建风险评估工具。"""

    @tool
    def assess_risk(
        symbol: str,
        position_pct: float = 0.2,
        direction: str = "BUY",
        max_position_pct: float = 0.3,
        max_daily_loss_pct: float = 0.02,
    ) -> str:
        """评估交易风险。

        检查仓位/回撤/集中度风险，给出调整建议。

        Parameters
        ----------
        symbol : str
            标的代码
        position_pct : float
            拟建仓比例 (0.0-1.0)
        direction : str
            交易方向
        max_position_pct : float
            单标的最大仓位比例
        max_daily_loss_pct : float
            单日最大亏损比例
        """
        warnings = []
        adjusted_params: Dict[str, Any] = {}
        level = "low"

        # 仓位检查
        if position_pct > max_position_pct:
            warnings.append(
                f"拟建仓 {position_pct:.0%} 超过单标的上限 {max_position_pct:.0%}，"
                f"建议降至 {max_position_pct:.0%}"
            )
            adjusted_params["position_pct"] = max_position_pct
            level = "high"

        # 方向性风险
        if direction == "BUY" and position_pct > 0.3:
            warnings.append("买入仓位超过 30%，集中度风险较高")
            if level != "high":
                level = "medium"

        if direction == "SELL":
            warnings.append("卖出操作需确认是否有足够持仓")

        # 止损建议
        if position_pct > 0.1:
            stop_loss = max_daily_loss_pct / position_pct
            adjusted_params["stop_loss_pct"] = round(stop_loss, 4)
            if stop_loss < 0.03:
                warnings.append(f"建议止损 {stop_loss:.1%} 过紧，可能频繁触发")

        return json.dumps({
            "level": level,
            "warnings": warnings,
            "adjusted_params": adjusted_params,
        }, ensure_ascii=False)

    return assess_risk


# ── Tool 3: check_market_env ──


def _make_check_market_env(fetcher_manager: Any) -> Any:
    """工厂函数：创建带数据源闭包的市场环境评估工具。"""

    @tool
    def check_market_env(symbol: str = "sh000300") -> str:
        """评估当前市场环境。

        判断牛市/熊市/震荡/暴跌，给出仓位建议。

        Parameters
        ----------
        symbol : str
            基准指数代码，默认沪深 300
        """
        try:
            from stockquant.ai.risk_agent import MarketEnvDetector, MarketEnvironment

            df = fetcher_manager.fetch(symbol, timeframe="1d")
            if df is None or df.empty or len(df) < 60:
                return json.dumps({
                    "environment": "sideways",
                    "suggestion": "数据不足，维持标准仓位",
                }, ensure_ascii=False)

            closes = df["close"].values.astype(float)
            detector = MarketEnvDetector()
            env = detector.detect(closes)

            suggestion_map = {
                MarketEnvironment.BULL: "市场上升趋势，可适当放大仓位至 80-90%",
                MarketEnvironment.BEAR: "市场下降趋势，建议降低仓位至 30-50%",
                MarketEnvironment.SIDEWAYS: "市场震荡，维持标准仓位 50-70%",
                MarketEnvironment.CRASH: "市场暴跌，建议仓位降至 10-20%，暂停新开仓",
            }

            return json.dumps({
                "environment": env.value,
                "suggestion": suggestion_map.get(env, "维持标准仓位"),
            }, ensure_ascii=False)

        except Exception as exc:
            return json.dumps({
                "environment": "sideways",
                "suggestion": f"环境检测异常: {exc}，维持标准仓位",
            }, ensure_ascii=False)

    return check_market_env


# ── Tool 4: analyze_news_sentiment ──


def _make_analyze_news_sentiment(news_searcher: Any) -> Any:
    """工厂函数：创建带新闻搜索闭包的消息面验证工具。"""

    @tool
    def analyze_news_sentiment(symbol: str, query: str = "") -> str:
        """搜索标的最新新闻并分析消息面。

        Parameters
        ----------
        symbol : str
            标的代码
        query : str
            搜索关键词（可选）
        """
        try:
            items = news_searcher.search(symbol, query=query if query else None)

            if not items:
                return json.dumps({
                    "score": 0.5,
                    "key_events": [],
                    "warnings": ["未找到相关新闻"],
                }, ensure_ascii=False)

            # 基于关键词的情感分析
            positive_keywords = ["利好", "增长", "超预期", "突破", "新高", "回购", "增持", "涨停"]
            negative_keywords = ["利空", "下跌", "亏损", "减持", "违规", "退市", "跌停", "暴雷", "风险"]

            pos_count = 0
            neg_count = 0
            key_events = []

            for item in items[:10]:
                title = getattr(item, "title", "") or ""
                content = getattr(item, "content", "") or ""
                text = f"{title} {content}"

                is_pos = any(kw in text for kw in positive_keywords)
                is_neg = any(kw in text for kw in negative_keywords)

                if is_pos:
                    pos_count += 1
                    key_events.append(f"[利好] {title[:50]}")
                if is_neg:
                    neg_count += 1
                    key_events.append(f"[利空] {title[:50]}")

            total = pos_count + neg_count
            if total > 0:
                score = 0.5 + (pos_count - neg_count) / (2 * total)
            else:
                score = 0.5

            score = max(0.0, min(1.0, score))

            warnings = []
            if score < 0.3:
                warnings.append("消息面偏空，建议谨慎操作")
            elif score > 0.7:
                warnings.append("消息面偏多，注意利好出尽风险")

            return json.dumps({
                "score": round(score, 2),
                "key_events": key_events[:5],
                "warnings": warnings,
            }, ensure_ascii=False)

        except Exception as exc:
            return json.dumps({
                "score": 0.5,
                "key_events": [],
                "warnings": [f"新闻搜索异常: {exc}"],
            }, ensure_ascii=False)

    return analyze_news_sentiment


# ── Tool 5: evaluate_position ──


@tool
def evaluate_position(
    symbol: str,
    current_positions_json: str = "{}",
    proposed_qty: int = 0,
    proposed_price: float = 0.0,
    total_cash: float = 1000000.0,
    max_total_position_pct: float = 0.9,
) -> str:
    """检查仓位合理性。

    评估是否过度集中、是否超出总仓位限制。

    Parameters
    ----------
    symbol : str
        标的代码
    current_positions_json : str
        当前持仓 JSON，格式 {"symbol1": {"qty": 100, "value": 50000}, ...}
    proposed_qty : int
        拟交易数量
    proposed_price : float
        拟交易价格
    total_cash : float
        总资金
    max_total_position_pct : float
        总仓位上限
    """
    try:
        positions = json.loads(current_positions_json) if current_positions_json and current_positions_json != "{}" else {}
    except json.JSONDecodeError:
        positions = {}

    # 当前持仓市值
    current_value = sum(p.get("value", 0) for p in positions.values())
    current_exposure = current_value / total_cash if total_cash > 0 else 0.0

    # 拟交易后
    proposed_value = proposed_qty * proposed_price if proposed_price > 0 else 0
    proposed_exposure = (current_value + proposed_value) / total_cash if total_cash > 0 else 0.0

    reasonable = True
    suggestion = ""

    if proposed_exposure > max_total_position_pct:
        reasonable = False
        suggestion = f"总仓位将达 {proposed_exposure:.0%}，超过上限 {max_total_position_pct:.0%}，建议减少交易量"
    elif proposed_exposure > 0.7:
        suggestion = f"总仓位将达 {proposed_exposure:.0%}，偏高但可接受"
    else:
        suggestion = f"总仓位 {proposed_exposure:.0%}，合理"

    # 单标的集中度
    symbol_existing = positions.get(symbol, {}).get("value", 0)
    symbol_total = symbol_existing + proposed_value
    symbol_pct = symbol_total / total_cash if total_cash > 0 else 0.0
    if symbol_pct > 0.3:
        reasonable = False
        suggestion += f"；单标的 {symbol} 占比 {symbol_pct:.0%}，超过 30% 集中度限制"

    return json.dumps({
        "reasonable": reasonable,
        "suggestion": suggestion,
        "current_exposure": round(current_exposure, 4),
        "proposed_exposure": round(proposed_exposure, 4),
    }, ensure_ascii=False)


# ── Tool 6: generate_decision ──


def _make_generate_decision(adapter: Any) -> Any:
    """工厂函数：创建带 LLM 闭包的综合决策工具。"""

    @tool
    def generate_decision(
        verification_json: str,
        risk_json: str,
        env_json: str,
        sentiment_json: str,
        position_json: str,
        direction: str = "BUY",
        signal_source: str = "strategy",
    ) -> str:
        """综合所有验证结果，生成最终决策建议。

        Parameters
        ----------
        verification_json : str
            信号验证结果 JSON
        risk_json : str
            风险评估结果 JSON
        env_json : str
            市场环境结果 JSON
        sentiment_json : str
            消息面验证结果 JSON
        position_json : str
            仓位评估结果 JSON
        direction : str
            交易方向
        signal_source : str
            信号来源
        """
        prompt = f"""请根据以下多维度验证结果，给出最终交易决策建议。

信号验证：{verification_json}
风险评估：{risk_json}
市场环境：{env_json}
消息面：{sentiment_json}
仓位评估：{position_json}
交易方向：{direction}
信号来源：{signal_source}

决策原则：
1. 信号优先级：传统策略信号 > AI 辅助信号 > AI 生成策略信号
2. 风险优先：有疑虑则否决
3. 仓位保守：建议仓位不超过原始建议的 80%
4. 止损必设

输出格式（严格 JSON）：
{{
    "action": "confirm|reject|modify",
    "confidence": 0.0-1.0,
    "reason": "决策理由",
    "modified_params": {{"qty": ..., "position_pct": ...}} or null,
    "risk_warnings": ["风险1", "风险2"],
    "stop_loss": 止损价或null,
    "take_profit": 止盈价或null
}}
"""
        try:
            response = adapter.call(
                messages=[{"role": "user", "content": prompt}]
            )
            parsed = robust_json_parse(response.content or "")
            if parsed is None:
                # 默认否决
                return json.dumps({
                    "action": "reject",
                    "confidence": 0.0,
                    "reason": "无法解析 LLM 决策，默认否决",
                    "modified_params": None,
                    "risk_warnings": ["AI 决策解析失败"],
                    "stop_loss": None,
                    "take_profit": None,
                }, ensure_ascii=False)
            return json.dumps(parsed, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({
                "action": "reject",
                "confidence": 0.0,
                "reason": f"决策生成异常: {exc}",
                "modified_params": None,
                "risk_warnings": [str(exc)],
                "stop_loss": None,
                "take_profit": None,
            }, ensure_ascii=False)

    return generate_decision


# ── 辅助函数 ──


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """计算指数移动平均。"""
    if len(data) < period:
        return np.full_like(data, data[-1] if len(data) > 0 else 0)
    result = np.empty_like(data)
    result[:period] = np.mean(data[:period])
    multiplier = 2.0 / (period + 1)
    for i in range(period, len(data)):
        result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def _calc_rsi(closes: np.ndarray, period: int = 14) -> float:
    """计算 RSI。"""
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - 100 / (1 + rs))
