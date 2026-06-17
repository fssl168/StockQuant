# -*- coding: utf-8 -*-
"""AI Agent Orchestrator — 统一管理所有 AI Agent 的中央协调器

Spec F020/F024/F025 要求: AI Agent Orchestrator 中枢架构
- 策略编排 + 信号融合 + 决策推荐 + 风险审核
- Agent 间通过 AIEvent 事件总线通信
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from stockquant.models.base import Event, EventType

from stockquant.ai.collectors.base import BaseCollector, RawInfoItem
from stockquant.ai.collectors.news_collector import NewsCollector
from stockquant.ai.collectors.announcement_collector import AnnouncementCollector
from stockquant.ai.collectors.social_collector import SocialCollector
from stockquant.ai.collectors.verifier import SourceVerifier
from stockquant.ai.signal_fusion import SignalFusion, SourceSignal, FusedSignal

logger = logging.getLogger("stockquant.ai.orchestrator")


class AgentOrchestrator:
    """AI Agent 中枢协调器

    职责:
    1. 统一管理所有 Agent 实例（注册/注销）
    2. 路由请求到正确的 Agent
    3. 通过事件总线实现 Agent 间异步通信
    4. 编排多 Agent 协作流程
    """

    def __init__(self):
        self._agents: Dict[str, Any] = {}
        self._event_handlers: Dict[EventType, List[Callable]] = {}
        self._event_queue: List[Event] = []
        self._collectors: List[BaseCollector] = [
            NewsCollector(),
            AnnouncementCollector(),
            SocialCollector(),
        ]
        self._verifier = SourceVerifier()
        self._signal_fusion = SignalFusion()
        logger.info("AgentOrchestrator 初始化完成")

    # ── Agent 注册 ──────────────────────────────────────────

    def register_agent(self, name: str, agent: Any) -> None:
        """注册 Agent 实例"""
        self._agents[name] = agent
        logger.info("Agent 注册: %s (%s)", name, type(agent).__name__)

    def unregister_agent(self, name: str) -> None:
        """注销 Agent 实例"""
        self._agents.pop(name, None)
        logger.info("Agent 注销: %s", name)

    def get_agent(self, name: str) -> Optional[Any]:
        """获取 Agent 实例"""
        return self._agents.get(name)

    @property
    def registered_agents(self) -> List[str]:
        """已注册的 Agent 名称列表"""
        return list(self._agents.keys())

    # ── 请求路由 ──────────────────────────────────────────

    def route_request(self, task_type: str, payload: Dict[str, Any]) -> Any:
        """路由请求到正确的 Agent

        Args:
            task_type: 任务类型 (chat/monitor/decision/strategy/comparison/risk/indicator/backtest)
            payload: 请求参数

        Returns:
            Agent 处理结果
        """
        # 任务类型到 Agent 名称的映射
        agent_map = {
            "chat": "chat_agent",
            "monitor": "monitor_agent",
            "decision": "decision_agent",
            "strategy": "strategy_agent",
            "comparison": "comparison_agent",
            "risk": "risk_agent",
            "indicator": "indicator_agent",
            "backtest": "backtest_agent",
        }

        agent_name = agent_map.get(task_type)
        if not agent_name:
            raise ValueError(f"未知任务类型: {task_type}")

        agent = self._agents.get(agent_name)
        if not agent:
            raise RuntimeError(f"Agent 未注册: {agent_name}")

        logger.debug("路由请求: %s → %s", task_type, agent_name)
        return agent

    # ── 事件总线 ──────────────────────────────────────────

    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """订阅事件"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        logger.debug("事件订阅: %s → %s", event_type.value, handler.__name__)

    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """取消订阅"""
        handlers = self._event_handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, event: Event) -> None:
        """发布事件到事件总线

        事件会被推送到所有订阅该类型的处理器。
        典型流程:
        - 采集器发布 NewsEvent → MonitorAgent/DecisionAgent 消费
        - MonitorAgent 发布 AlertEvent → DecisionAgent 消费
        - DecisionAgent 发布 DecisionEvent → 交易执行层消费
        """
        handlers = self._event_handlers.get(event.type, [])
        if not handlers:
            self._event_queue.append(event)
            return

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("事件处理失败: %s → %s: %s", event.type.value, handler.__name__, e)

        logger.debug("事件发布: %s → %d handlers", event.type.value, len(handlers))

    def get_pending_events(self, event_type: Optional[EventType] = None) -> List[Event]:
        """获取待处理事件"""
        if event_type:
            return [e for e in self._event_queue if e.type == event_type]
        return list(self._event_queue)

    def clear_pending_events(self) -> None:
        """清空待处理事件"""
        self._event_queue.clear()

    # ── 多 Agent 协作 ──────────────────────────────────────

    async def orchestrate_signal_evaluation(self, symbol: str, signal_data: Dict) -> Dict[str, Any]:
        """编排信号评估流程 (F024→F025)

        流程: MonitorAgent 扫描 → DecisionAgent 评估 → 返回决策建议
        """
        results = {}

        # Step 1: MonitorAgent 扫描异动
        monitor_agent = self._agents.get("monitor_agent")
        if monitor_agent:
            try:
                scan_result = await monitor_agent.scan(symbol)
                results["scan"] = scan_result
            except Exception as e:
                logger.error("MonitorAgent 扫描失败: %s", e)

        # Step 2: DecisionAgent 评估信号
        decision_agent = self._agents.get("decision_agent")
        if decision_agent and results.get("scan"):
            try:
                from stockquant.strategy.signal import Signal
                signal = Signal(
                    symbol=symbol,
                    side=results["scan"].get("side", "HOLD"),
                    source="AI_MONITOR",
                    confidence=results["scan"].get("confidence", 0.5),
                    reason=results["scan"].get("reason", ""),
                )
                decision = await decision_agent.evaluate(signal)
                results["decision"] = decision
            except Exception as e:
                logger.error("DecisionAgent 评估失败: %s", e)

        return results

    # ── 信号融合 ──────────────────────────────────────────

    def fuse_signals(self, symbol: str, signals: List[SourceSignal]) -> FusedSignal:
        """F024 AI 信号融合 — 技术面+情绪面+基本面三源融合。

        Parameters
        ----------
        symbol : str
            股票代码
        signals : List[SourceSignal]
            各来源信号列表

        Returns
        -------
        FusedSignal
            融合后的信号
        """
        return self._signal_fusion.fuse(signals)

    # ── 多源采集 ──────────────────────────────────────────

    async def collect_info(self, symbol: str = "", limit: int = 20) -> List[RawInfoItem]:
        """并行运行所有采集器并验证结果

        Args:
            symbol: 股票代码（可选）
            limit: 每个采集器的最大条目数

        Returns:
            经过来源验证和去重后的信息列表
        """
        import asyncio

        tasks = [collector.collect(symbol=symbol, limit=limit) for collector in self._collectors]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items: List[RawInfoItem] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("采集器异常: %s", result)
                continue
            if isinstance(result, list):
                all_items.extend(result)

        # 来源验证
        verified = self._verifier.verify(all_items)
        # 去重
        deduped = self._verifier.deduplicate(verified)

        logger.info("采集完成: 原始 %d 条 → 验证 %d 条 → 去重 %d 条",
                     len(all_items), len(verified), len(deduped))
        return deduped


# ── 全局单例 ──────────────────────────────────────────

_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """获取全局 Orchestrator 单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


def init_orchestrator() -> AgentOrchestrator:
    """初始化 Orchestrator 并注册所有 Agent"""
    global _orchestrator
    orch = get_orchestrator()

    # 懒加载注册 Agent（避免循环导入）
    try:
        from stockquant.ai.chat_agent import ChatAgent
        orch.register_agent("chat_agent", ChatAgent())
    except Exception as e:
        logger.warning("ChatAgent 注册失败: %s", e)

    try:
        from stockquant.ai.monitor_agent import MonitorAgent
        orch.register_agent("monitor_agent", MonitorAgent())
    except Exception as e:
        logger.warning("MonitorAgent 注册失败: %s", e)

    try:
        from stockquant.ai.decision_agent import DecisionAgent
        orch.register_agent("decision_agent", DecisionAgent())
    except Exception as e:
        logger.warning("DecisionAgent 注册失败: %s", e)

    try:
        from stockquant.ai.strategy_agent import StrategyAgent
        orch.register_agent("strategy_agent", StrategyAgent())
    except Exception as e:
        logger.warning("StrategyAgent 注册失败: %s", e)

    try:
        from stockquant.ai.comparison_agent import ComparisonAgent
        orch.register_agent("comparison_agent", ComparisonAgent())
    except Exception as e:
        logger.warning("ComparisonAgent 注册失败: %s", e)

    try:
        from stockquant.ai.risk_agent import RiskAgent
        orch.register_agent("risk_agent", RiskAgent())
    except Exception as e:
        logger.warning("RiskAgent 注册失败: %s", e)

    try:
        from stockquant.ai.indicator_agent import IndicatorAgent
        orch.register_agent("indicator_agent", IndicatorAgent())
    except Exception as e:
        logger.warning("IndicatorAgent 注册失败: %s", e)

    try:
        from stockquant.ai.backtest_agent import BacktestAgent
        orch.register_agent("backtest_agent", BacktestAgent())
    except Exception as e:
        logger.warning("BacktestAgent 注册失败: %s", e)

    logger.info("Orchestrator 初始化完成，已注册 %d 个 Agent", len(orch.registered_agents))
    _orchestrator = orch
    return orch
