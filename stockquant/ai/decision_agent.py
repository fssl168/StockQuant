# -*- coding: utf-8 -*-
"""F025 AI 辅助决策 Agent — 信号二次验证 + 交易决策建议"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from stockquant.agent.decision_tools import (
    _make_analyze_news_sentiment,
    _make_assess_risk,
    _make_check_market_env,
    _make_generate_decision,
    _make_verify_signal,
    evaluate_position,
)
from stockquant.agent.llm_adapter import LLMAdapter
from stockquant.agent.react_agent import ReActAgent, ReActResult
from stockquant.ai.json_utils import robust_json_parse
from stockquant.ai.models import (
    AuditLog,
    DecisionAdvice,
    DecisionMode,
    MarketEnvResult,
    PositionEvaluation,
    RiskAssessment,
    SentimentResult,
    Signal,
    SignalSource,
    SignalVerification,
)

logger = logging.getLogger("stockquant.ai")


class DecisionAgent:
    """F025 AI 辅助决策 Agent。

    在交易执行前，AI 作为"第二大脑"对信号进行二次验证，给出决策建议。

    支持三种人机协同模式：
    - AUTO: AI 建议自动下单
    - SEMI_AUTO: AI 建议 → 用户确认 → 下单
    - READ_ONLY: AI 只推送建议

    用法::

        agent = DecisionAgent(model="deepseek/deepseek-chat", api_key="...")
        advice = agent.evaluate(signal={"symbol": "sh600519", "direction": "BUY", "qty": 100})
        print(advice.action)         # confirm/reject/modify
        print(advice.confidence)     # 0.0-1.0
        print(advice.risk_warnings)  # 风险警告

    Parameters
    ----------
    model : str
        LLM 模型名称（litellm 格式）
    api_key : str | None
        API Key
    fallback_models : list[str] | None
        回退模型列表
    base_url : str | None
        API 基础 URL
    mode : DecisionMode
        人机协同模式
    fetcher_manager : Any | None
        DataFetcherManager 实例
    news_searcher : Any | None
        NewsSearcher 实例
    max_steps : int
        最大推理步数
    """

    SYSTEM_PROMPT = """你是一个专业的 A 股交易决策顾问。你的任务是对交易信号进行二次验证，
给出是否执行、如何执行的建议。

工作流程（严格按顺序）：
1. **技术面验证**：调用 verify_signal 多指标交叉确认信号可靠性
2. **风险评估**：调用 assess_risk 检查仓位/回撤/集中度风险
3. **市场环境**：调用 check_market_env 判断当前牛/熊/震荡/暴跌
4. **消息面验证**：调用 analyze_news_sentiment 搜索最新新闻确认利空/利好
5. **仓位合理性**：调用 evaluate_position 检查是否过度集中
6. **综合决策**：调用 generate_decision 综合以上分析给出 confirm/reject/modify 建议

决策原则：
- 信号优先级：传统策略信号 > AI 辅助信号 > AI 生成策略信号
- 风险优先：有疑虑则否决，宁可错过不可做错
- 仓位保守：建议仓位不超过信号原始建议的 80%
- 止损必设：每笔交易必须设置止损点
- T+1 意识：当日买入不可卖出，注意流动性风险

如果验证过程中发现重大风险，可以直接否决，不需要继续后续步骤。
"""

    def __init__(
        self,
        model: str = "deepseek/deepseek-chat",
        api_key: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        base_url: Optional[str] = None,
        mode: DecisionMode = DecisionMode.SEMI_AUTO,
        fetcher_manager: Any = None,
        news_searcher: Any = None,
        max_steps: int = 10,
    ) -> None:
        self._mode = mode
        self._fetcher_manager = fetcher_manager
        self._news_searcher = news_searcher
        self._audit_logs: List[AuditLog] = []

        # 构建 ReActAgent
        self._react = ReActAgent(
            model=model,
            api_key=api_key,
            fallback_models=fallback_models,
            base_url=base_url,
            max_steps=max_steps,
        )

        # 构建 LLMAdapter（供 generate_decision 使用）
        self._adapter = LLMAdapter(
            model=model,
            api_key=api_key,
            fallback_models=fallback_models or [],
            base_url=base_url,
        )

        # 注册决策验证工具
        self._react.register_tools(
            _make_verify_signal(fetcher_manager),
            _make_assess_risk(),
            _make_check_market_env(fetcher_manager),
            _make_analyze_news_sentiment(news_searcher),
            evaluate_position,
            _make_generate_decision(self._adapter),
        )

        # 覆盖系统提示词
        self._react.SYSTEM_PROMPT = self.SYSTEM_PROMPT

    @property
    def mode(self) -> DecisionMode:
        """当前人机协同模式。"""
        return self._mode

    @mode.setter
    def mode(self, value: DecisionMode) -> None:
        self._mode = value

    def evaluate(
        self,
        signal: Dict[str, Any],
        current_positions: Optional[Dict[str, Any]] = None,
        total_cash: float = 1000000.0,
    ) -> DecisionAdvice:
        """评估交易信号，给出决策建议。

        Parameters
        ----------
        signal : dict
            交易信号，格式 {"symbol": "sh600519", "direction": "BUY", "qty": 100, ...}
        current_positions : dict | None
            当前持仓
        total_cash : float
            总资金

        Returns
        -------
        DecisionAdvice
        """
        symbol = signal.get("symbol", "")
        direction = signal.get("direction", "BUY")
        source = signal.get("source", "strategy")
        qty = signal.get("qty", 0)
        price = signal.get("price", 0.0)

        # 只读模式：直接返回建议，不执行
        if self._mode == DecisionMode.READ_ONLY:
            advice = DecisionAdvice(
                action="confirm",
                confidence=0.0,
                reason="只读模式：AI 仅提供建议，不自动执行",
                risk_warnings=["只读模式下 AI 不执行任何交易"],
            )
            self._record_audit(signal, advice, "read_only")
            return advice

        # 构建查询
        positions_json = json.dumps(current_positions or {}, ensure_ascii=False)
        query = (
            f"请评估以下交易信号：\n"
            f"标的: {symbol}, 方向: {direction}, 数量: {qty}, 价格: {price}\n"
            f"信号来源: {source}\n"
            f"当前持仓: {positions_json}\n"
            f"总资金: {total_cash:,.0f}"
        )

        react_result = self._react.run(query)
        advice = self._parse_react_result(react_result, signal)

        # 记录审计日志
        final_action = advice.action if self._mode == DecisionMode.AUTO else "pending_user_confirm"
        self._record_audit(signal, advice, final_action)

        return advice

    def batch_evaluate(
        self,
        signals: List[Dict[str, Any]],
        current_positions: Optional[Dict[str, Any]] = None,
        total_cash: float = 1000000.0,
    ) -> List[DecisionAdvice]:
        """批量评估信号。

        Parameters
        ----------
        signals : list[dict]
            交易信号列表
        current_positions : dict | None
            当前持仓
        total_cash : float
            总资金

        Returns
        -------
        list[DecisionAdvice]
        """
        return [
            self.evaluate(sig, current_positions, total_cash)
            for sig in signals
        ]

    def get_audit_logs(self, limit: int = 50) -> List[AuditLog]:
        """获取审计日志。"""
        return self._audit_logs[-limit:]

    def _parse_react_result(
        self, react_result: ReActResult, signal: Dict[str, Any]
    ) -> DecisionAdvice:
        """解析 ReAct 推理结果为 DecisionAdvice。"""
        advice = DecisionAdvice()

        if not react_result.success:
            advice.action = "reject"
            advice.confidence = 0.0
            advice.reason = f"推理失败: {react_result.error}"
            return advice

        # 从推理步骤中提取各工具的输出
        for thought in react_result.thoughts:
            if not thought.observation:
                continue

            obs = thought.observation

            if thought.action == "verify_signal":
                try:
                    parsed = json.loads(obs)
                    advice.verification = SignalVerification(
                        confirmed=parsed.get("confirmed", False),
                        indicators_summary=parsed.get("indicators_summary", {}),
                        contradictions=parsed.get("contradictions", []),
                    )
                except json.JSONDecodeError:
                    pass

            elif thought.action == "assess_risk":
                try:
                    parsed = json.loads(obs)
                    advice.risk = RiskAssessment(
                        level=parsed.get("level", "low"),
                        warnings=parsed.get("warnings", []),
                        adjusted_params=parsed.get("adjusted_params", {}),
                    )
                except json.JSONDecodeError:
                    pass

            elif thought.action == "check_market_env":
                try:
                    parsed = json.loads(obs)
                    advice.market_env = MarketEnvResult(
                        environment=parsed.get("environment", "sideways"),
                        suggestion=parsed.get("suggestion", ""),
                    )
                except json.JSONDecodeError:
                    pass

            elif thought.action == "analyze_news_sentiment":
                try:
                    parsed = json.loads(obs)
                    advice.sentiment = SentimentResult(
                        score=parsed.get("score", 0.5),
                        key_events=parsed.get("key_events", []),
                        warnings=parsed.get("warnings", []),
                    )
                except json.JSONDecodeError:
                    pass

            elif thought.action == "evaluate_position":
                try:
                    parsed = json.loads(obs)
                    advice.position_eval = PositionEvaluation(
                        reasonable=parsed.get("reasonable", True),
                        suggestion=parsed.get("suggestion", ""),
                        current_exposure=parsed.get("current_exposure", 0.0),
                        proposed_exposure=parsed.get("proposed_exposure", 0.0),
                    )
                except json.JSONDecodeError:
                    pass

            elif thought.action == "generate_decision":
                try:
                    parsed = json.loads(obs)
                    advice.action = parsed.get("action", "reject")
                    advice.confidence = parsed.get("confidence", 0.0)
                    advice.reason = parsed.get("reason", "")
                    advice.modified_params = parsed.get("modified_params")
                    advice.risk_warnings = parsed.get("risk_warnings", [])
                    advice.stop_loss = parsed.get("stop_loss")
                    advice.take_profit = parsed.get("take_profit")
                except json.JSONDecodeError:
                    pass

        # 如果没有从 generate_decision 提取到决策，基于验证结果生成默认决策
        if advice.action == "reject" and not advice.reason:
            if advice.verification and advice.verification.contradictions:
                advice.reason = f"技术面矛盾: {'; '.join(advice.verification.contradictions)}"
            elif advice.risk and advice.risk.level in ("high", "extreme"):
                advice.reason = f"风险过高: {'; '.join(advice.risk.warnings)}"
            else:
                advice.reason = "无法生成决策，默认否决"

        return advice

    def _record_audit(
        self,
        signal: Dict[str, Any],
        advice: DecisionAdvice,
        final_action: str,
    ) -> None:
        """记录审计日志。"""
        log = AuditLog(
            timestamp=datetime.now(),
            signal_source=signal.get("source", "unknown"),
            symbol=signal.get("symbol", ""),
            direction=signal.get("direction", ""),
            original_signal=signal,
            ai_decision=advice,
            final_action=final_action,
            user_confirmed=None if self._mode != DecisionMode.SEMI_AUTO else False,
        )
        self._audit_logs.append(log)
        logger.info(
            f"Decision audit: {log.symbol} {log.direction} → "
            f"{advice.action} (confidence={advice.confidence:.2f})"
        )
