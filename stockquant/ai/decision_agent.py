# -*- coding: utf-8 -*-
"""F025 AI 辅助决策 Agent — 信号二次验证 + 交易决策建议"""

from __future__ import annotations

import json
import logging
import os
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
from stockquant.ai.models import (
    AuditLog,
    DecisionAdvice,
    DecisionMode,
    MarketEnvResult,
    PositionEvaluation,
    RiskAssessment,
    SentimentResult,
    SignalVerification,
)
from stockquant.config import get_config
from stockquant.persistence.repository import save_audit_log

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

    SYSTEM_PROMPT = """你是一个专业的 A 股交易决策顾问。你的任务是对交易信号进行二次验证，给出是否执行、如何执行的建议。

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

7. **风险偏好约束**（D2 新增）：根据 user_profile 调整仓位上限、止损止盈
   - conservative（保守）: 仓位上限 5%，止损 3%，止盈 6%
   - neutral（中性）: 仓位上限 10%，止损 5%，止盈 10%
   - aggressive（激进）: 仓位上限 20%，止损 8%，止盈 20%
8. **洞察整合**（D2 新增）：如果传入 insights，结合 F020 的市场洞察做综合判断
   - F020 升华洞察是市场级与公司级的高层判断
   - 结合 WorkingMemory 反思与历史记忆做时间维度上的连贯性校验
   - 当 insights 显示与信号方向冲突时，应当 reject 或 modify
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
        db_url: Optional[str] = None,
    ) -> None:
        self._mode = mode
        self._fetcher_manager = fetcher_manager
        self._news_searcher = news_searcher
        self._audit_logs: List[AuditLog] = []
        self._db_url = db_url or os.environ.get("DATABASE_URL", "sqlite:///./stockquant.db")
        self._model_usage_stats: Dict[str, int] = {}

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

    def select_model_for_frequency(self, frequency: str) -> str:
        """根据数据频率自动选择 AI 模型

        - Tick 级（< 1s）: 使用本地规则引擎，延迟 < 200ms
        - 分钟级（1s-60s）: 使用轻量 LLM（如 gpt-4o-mini），延迟 < 3s
        - Bar 级（> 60s）: 使用重量 LLM（如 gpt-4o），延迟 < 10s

        Parameters
        ----------
        frequency : str
            数据频率，如 "tick", "1min", "5min", "1h", "daily"

        Returns
        -------
        str
            选择的模型名称
        """
        config = get_config()
        ai_config = config.get("ai", {})

        # 频率 → 模型映射
        tick_models = ["local_rule_engine"]
        lightweight_models = [ai_config.get("lightweight_model", "gpt-4o-mini")]
        heavyweight_models = [ai_config.get("model", "gpt-4o")]

        freq_lower = frequency.lower().strip()

        # Tick 级: tick, 100ms, 500ms 等
        if freq_lower == "tick" or freq_lower.endswith("ms"):
            selected = tick_models[0]
            logger.info("频率 '%s' → 选择本地规则引擎 (延迟 < 200ms)", frequency)

        # 分钟级: 1s, 5s, 10s, 15s, 30s, 1min, 5min, 15min, 30min, 60s 等
        elif self._is_minute_level(freq_lower):
            selected = lightweight_models[0]
            logger.info("频率 '%s' → 选择轻量 LLM %s (延迟 < 3s)", frequency, selected)

        # Bar 级: 1h, 4h, daily, weekly, monthly 等
        else:
            selected = heavyweight_models[0]
            logger.info("频率 '%s' → 选择重量 LLM %s (延迟 < 10s)", frequency, selected)

        # 更新使用统计
        self._model_usage_stats[selected] = self._model_usage_stats.get(selected, 0) + 1

        return selected

    @staticmethod
    def _is_minute_level(freq: str) -> bool:
        """判断频率是否为分钟级（1s ~ 60s）"""
        # 纯秒数: "1s", "5s", "10s", "15s", "30s", "60s"
        if freq.endswith("s") and not freq.endswith("ms"):
            try:
                seconds = int(freq[:-1])
                return 1 <= seconds <= 60
            except ValueError:
                pass
        # 分钟: "1min", "5min", "15min", "30min", "60min"
        if freq.endswith("min"):
            try:
                minutes = int(freq.replace("min", ""))
                return 1 <= minutes <= 60
            except ValueError:
                pass
        return False

    def get_model_usage_stats(self) -> Dict[str, int]:
        """获取模型使用统计。

        Returns
        -------
        dict
            模型名称 → 使用次数的映射
        """
        return dict(self._model_usage_stats)

    def evaluate(
        self,
        signal: Dict[str, Any],
        current_positions: Optional[Dict[str, Any]] = None,
        total_cash: float = 1000000.0,
        insights: Optional[List[Dict[str, Any]]] = None,
        user_profile: Optional[Any] = None,
        decision_context: Optional[Any] = None,
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
        insights : list[dict] | None
            F020 升华后的洞察列表（D2 新增）。若提供，将整合到决策查询中。
        user_profile : RiskProfile | None
            用户风险偏好（D2 新增）。若提供，将按 ProfileParams 调整仓位/止损止盈。
            支持传入 RiskProfile 枚举或字符串（"conservative"/"neutral"/"aggressive"）。
        decision_context : DecisionContext | None
            F020 → F025 完整决策上下文（D2 新增）。若提供，将作为决策辅助信息。
            优先级高于 insights（context.insights 覆盖单独传入的 insights）。

        Returns
        -------
        DecisionAdvice
        """
        symbol = signal.get("symbol", "")
        direction = signal.get("direction", "BUY")
        source = signal.get("source", "strategy")
        qty = signal.get("qty", 0)
        price = signal.get("price", 0.0)

        # D2: 解析 user_profile → ProfileParams（用于仓位/止损止盈约束）
        profile_params = self._resolve_profile_params(user_profile)

        # D2: 如果传入 decision_context，从中提取 insights（优先级高于单独传入的 insights）
        effective_insights = insights or []
        if decision_context is not None:
            ctx_insights = getattr(decision_context, "insights", None)
            if ctx_insights:
                effective_insights = ctx_insights
            # 同时提取反思文本（作为决策辅助信息）
            ctx_reflection = getattr(decision_context, "reflection", "") or ""
            ctx_memory = getattr(decision_context, "memory_retrieval", []) or []
        else:
            ctx_reflection = ""
            ctx_memory = []

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

        # 构建查询（含 D2 扩展：风险偏好 + F020 洞察 + 反思）
        positions_json = json.dumps(current_positions or {}, ensure_ascii=False)
        query_lines = [
            f"请评估以下交易信号：",
            f"标的: {symbol}, 方向: {direction}, 数量: {qty}, 价格: {price}",
            f"信号来源: {source}",
            f"当前持仓: {positions_json}",
            f"总资金: {total_cash:,.0f}",
        ]
        # D2: 注入风险偏好约束
        if profile_params is not None:
            query_lines.append(
                f"风险偏好: {self._profile_label(user_profile)} "
                f"(仓位上限 {profile_params.max_position_pct*100:.0f}%, "
                f"止损 {profile_params.stop_loss_pct*100:.0f}%, "
                f"止盈 {profile_params.take_profit_pct*100:.0f}%)"
            )
        # D2: 注入 F020 升华洞察
        if effective_insights:
            insights_text = self._format_insights(effective_insights)
            query_lines.append(f"F020 市场洞察:\n{insights_text}")
        # D2: 注入 WorkingMemory 反思
        if ctx_reflection:
            query_lines.append(f"WorkingMemory 反思: {ctx_reflection[:300]}")
        # D2: 注入历史记忆摘要（取前 3 条）
        if ctx_memory:
            memory_text = self._format_memory(ctx_memory[:3])
            query_lines.append(f"历史记忆:\n{memory_text}")

        query = "\n".join(query_lines)

        react_result = self._react.run(query)
        advice = self._parse_react_result(react_result, signal)

        # D2: 根据 ProfileParams 强制覆盖止损止盈（如未在 LLM 响应中设置）
        if profile_params is not None:
            cost_price = float(signal.get("price", 0.0) or 0.0)
            if cost_price > 0:
                if advice.stop_loss is None:
                    advice.stop_loss = round(cost_price * (1 - profile_params.stop_loss_pct), 4)
                if advice.take_profit is None:
                    advice.take_profit = round(cost_price * (1 + profile_params.take_profit_pct), 4)
            # 仓位约束：若修改后的 qty 超过 profile 约束，记录风险告警
            if advice.modified_params and "qty" in advice.modified_params:
                advised_qty = advice.modified_params["qty"]
                max_qty = int(total_cash * profile_params.max_position_pct / max(cost_price, 0.001))
                if advised_qty > max_qty:
                    advice.risk_warnings.append(
                        f"建议仓位 {advised_qty} 股超过 {self._profile_label(user_profile)} 档位上限 "
                        f"{max_qty} 股（{profile_params.max_position_pct*100:.0f}% 仓位约束），请调整"
                    )

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

    # ── D2: Profiling + Insights 辅助方法 ─────────────────────────────────

    @staticmethod
    def _resolve_profile_params(user_profile: Optional[Any]):
        """将 user_profile 解析为 ProfileParams

        支持：
        - RiskProfile 枚举（推荐）
        - 字符串（"conservative"/"neutral"/"aggressive"）
        - ProfileParams 实例（直接返回）
        - None（返回 None，不应用约束）

        Returns:
            ProfileParams 实例或 None
        """
        if user_profile is None:
            return None
        # 已是 ProfileParams
        try:
            from stockquant.ai.profiling import ProfileParams
            if isinstance(user_profile, ProfileParams):
                return user_profile
        except ImportError:
            pass
        # RiskProfile 枚举或字符串
        try:
            from stockquant.ai.profiling import RiskProfile, get_params
            if isinstance(user_profile, RiskProfile):
                return get_params(user_profile)
            if isinstance(user_profile, str):
                profile = RiskProfile.from_str(user_profile)
                return get_params(profile)
        except ImportError:
            logger.debug("Profiling 模块不可用，跳过 user_profile 解析")
        return None

    @staticmethod
    def _profile_label(user_profile: Optional[Any]) -> str:
        """获取风险偏好的人类可读标签"""
        if user_profile is None:
            return "未指定"
        try:
            from stockquant.ai.profiling import RiskProfile
            if isinstance(user_profile, RiskProfile):
                return user_profile.value
        except ImportError:
            pass
        if isinstance(user_profile, str):
            return user_profile
        return "未知"

    @staticmethod
    def _format_insights(insights: List[Dict[str, Any]]) -> str:
        """格式化 F020 升华洞察为 LLM 可读文本"""
        if not insights:
            return ""
        lines = []
        for i, item in enumerate(insights[:5], 1):  # 限制 5 条，避免上下文超长
            if not isinstance(item, dict):
                continue
            content = item.get("content") or item.get("insight") or ""
            confidence = item.get("confidence", "")
            symbol = item.get("symbol", "")
            line = f"{i}. "
            if symbol:
                line += f"[{symbol}] "
            if confidence:
                line += f"(置信度: {confidence}) "
            line += str(content)[:200]
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _format_memory(memory_items: List[Dict[str, Any]]) -> str:
        """格式化历史记忆为 LLM 可读文本"""
        if not memory_items:
            return ""
        lines = []
        for i, item in enumerate(memory_items, 1):
            if not isinstance(item, dict):
                continue
            content = item.get("content") or item.get("summary") or ""
            symbol = item.get("symbol", "")
            tier = item.get("tier") or item.get("layer") or ""
            timestamp = item.get("timestamp", "")
            line = f"{i}. "
            if symbol:
                line += f"[{symbol}] "
            if tier:
                line += f"({tier}) "
            if timestamp:
                line += f"@{timestamp[:10]} "
            line += str(content)[:150]
            lines.append(line)
        return "\n".join(lines)

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
        """记录审计日志（内存 + 持久化）。"""
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

        # 持久化到 SQLite
        try:
            save_audit_log(
                engine_url=self._db_url,
                timestamp=log.timestamp,
                signal_source=log.signal_source,
                symbol=log.symbol,
                direction=log.direction,
                original_signal=log.original_signal,
                ai_decision={
                    "action": advice.action,
                    "confidence": advice.confidence,
                    "reason": advice.reason,
                    "modified_params": advice.modified_params,
                    "risk_warnings": advice.risk_warnings,
                    "stop_loss": advice.stop_loss,
                    "take_profit": advice.take_profit,
                },
                final_action=final_action,
                user_confirmed=log.user_confirmed,
                llm_model=self._react.model if hasattr(self._react, "model") else None,
                llm_prompt=advice._raw_prompt if hasattr(advice, "_raw_prompt") else None,
                llm_response=advice._raw_response if hasattr(advice, "_raw_response") else None,
                llm_reasoning_content=advice._reasoning_content if hasattr(advice, "_reasoning_content") else None,
                llm_tokens_used=advice._tokens_used if hasattr(advice, "_tokens_used") else None,
                llm_cost=advice._cost if hasattr(advice, "_cost") else None,
            )
        except Exception:
            logger.debug("Audit log persistence failed (non-fatal)")
