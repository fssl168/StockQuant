# -*- coding: utf-8 -*-
"""F028 AI 自然语言交互界面 — 对话式策略/数据/盯盘 + 工具调用 + 持久化"""

from __future__ import annotations

import logging
from typing import Any, Dict, Generator, List, Optional

from stockquant.agent.llm_adapter import LLMAdapter
from stockquant.agent.tool_registry import ToolRegistry

logger = logging.getLogger("stockquant.ai")

SYSTEM_PROMPT = """你是 StockQuant 量化交易助手，专注于中国 A 股市场。

你的能力包括：
1. 策略开发：根据自然语言描述生成 BaseStrategy 代码
2. 数据分析：查询市场数据、板块表现、个股走势
3. 回测解读：分析回测结果，解释盈亏原因
4. 盯盘配置：帮助用户设置自选股和监控条件
5. 交易建议：基于技术指标和市场面给出参考建议

回答规范：
- 使用中文回答
- 涉及数据时给出具体数值
- 涉及代码时用 markdown code block 包裹
- 涉及风险提示时明确指出
- 简洁专业，避免废话
"""

# 不同模式下的 system prompt 增强
MODE_SYSTEM_PROMPTS: dict[str, str] = {
    "general": SYSTEM_PROMPT,
    "strategy": SYSTEM_PROMPT + """

【策略模式】
你当前处于策略开发模式。
- 优先使用 BaseStrategy 模板生成策略代码
- 策略必须继承 BaseStrategy，实现 on_bar 方法
- 使用 self.buy / self.sell 下单，self.log 记录日志
- 使用 self.cerebro 进行策略配置
- 代码必须包含完整的 import 语句
- 每次生成策略后，给出简要的交易日志说明
- 支持的技术指标：MA, RSI, MACD, Bollinger Bands, KDJ, ATR 等
""",
    "analysis": SYSTEM_PROMPT + """

【数据分析模式】
你当前处于数据分析模式。
- 优先调用工具获取真实数据进行分析
- 提供数据表格、指标计算结果
- 给出统计分析结论和投资建议
- 用 Markdown 表格展示结构化数据
""",
    "monitor": SYSTEM_PROMPT + """

【盯盘模式】
你当前处于盯盘监控模式。
- 关注实时信号：MACD 金叉/死叉、RSI 超买超卖、放量突破等
- 给出明确的买入/卖出/观望建议
- 标注信号置信度（高/中/低）
- 关注涨停/跌停、放量异常等异动
""",
    "decision": SYSTEM_PROMPT + """

【决策模式】
你当前处于交易决策模式。
- 对每个交易信号进行多维度验证（技术面+基本面+资金面）
- 评估风险敞口和仓位比例
- 分析当前市场环境（牛市/熊市/震荡市）
- 给出明确的执行/放弃/观望建议
- 标注决策依据和风险等级
""",
}


class ChatMemory:
    """对话持久化 — SQLite 存储"""

    def __init__(self, db_url: str = "sqlite:///./stockquant.db") -> None:
        self._db_url = db_url

    def save_message(self, conversation_id: str, role: str, content: str) -> None:
        """保存单条消息。"""
        try:
            from stockquant.persistence.repository import save_chat_message
            save_chat_message(
                engine_url=self._db_url,
                conversation_id=conversation_id,
                role=role,
                content=content,
            )
        except Exception:
            logger.exception("Failed to persist chat message")

    def load_messages(self, conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """加载会话消息历史。"""
        try:
            from stockquant.persistence.repository import get_chat_messages
            return get_chat_messages(self._db_url, conversation_id, limit=limit)
        except Exception:
            logger.exception("Failed to load chat messages")
            return []

    def delete_messages(self, conversation_id: str) -> None:
        """删除会话消息。"""
        try:
            from stockquant.persistence.repository import delete_chat_messages
            delete_chat_messages(self._db_url, conversation_id)
        except Exception:
            logger.exception("Failed to delete chat messages")


class Conversation:
    """对话会话"""

    def __init__(self, conversation_id: str, memory: Optional[ChatMemory] = None) -> None:
        self.conversation_id = conversation_id
        self.messages: List[Dict[str, Any]] = []
        self.created_at: Any = None
        self.updated_at: Any = None
        self._memory = memory

        from datetime import datetime
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

        # 加载历史
        if memory:
            self.messages = memory.load_messages(conversation_id)

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        self.messages.append({"role": role, "content": content, **kwargs})
        self.updated_at = __import__("datetime").datetime.now()
        # 持久化
        if self._memory:
            self._memory.save_message(self.conversation_id, role, content)

    def get_history(self, limit: int = 20) -> List[Dict]:
        return self.messages[-limit:]


class ChatAgent:
    """F028 AI 自然语言交互界面。

    对话式策略开发、数据分析、回测报告解读、盯盘配置。
    使用 ReActAgent + ToolRegistry 实现工具调用。

    Parameters
    ----------
    model : str
        LLM 模型名称
    api_key : str | None
        API Key
    fallback_models : list[str] | None
        回退模型列表
    base_url : str | None
        API 基础 URL
    db_url : str | None
        SQLite 数据库 URL
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        base_url: Optional[str] = None,
        db_url: Optional[str] = None,
    ) -> None:
        self._adapter = LLMAdapter(
            model=model,
            api_key=api_key,
            fallback_models=fallback_models or [],
            base_url=base_url,
        )
        self._conversations: Dict[str, Conversation] = {}
        self._tool_registry = ToolRegistry()
        self._memory = ChatMemory(db_url=db_url) if db_url else None
        self._current_mode: str = "general"

        # 监控工具仅在 monitor / decision 模式下注册（见 _register_mode_tools）

    def _register_mode_tools(self, mode: str) -> None:
        """根据对话模式注册不同的工具集。

        Parameters
        ----------
        mode : str
            对话模式：'general' | 'strategy' | 'analysis' | 'monitor' | 'decision'
        """
        if mode == self._current_mode:
            return  # 模式未变，无需重新注册

        self._current_mode = mode

        # strategy 模式：策略生成 + 验证 + 回测工具
        if mode == "strategy":
            from stockquant.ai.chat_tools import trigger_backtest, interpret_backtest
            self._tool_registry.register(trigger_backtest)
            self._tool_registry.register(interpret_backtest)
            try:
                from stockquant.agent.strategy_tools import generate_strategy, validate_strategy
                self._tool_registry.register(generate_strategy)
                self._tool_registry.register(validate_strategy)
            except ImportError:
                logger.debug("strategy_tools not available")

        # analysis 模式：市场数据查询 + 新闻搜索 + 回测分析工具
        elif mode == "analysis":
            from stockquant.ai.chat_tools import (
                query_market_data,
                generate_chart_json,
                search_news,
                interpret_backtest,
            )
            self._tool_registry.register(query_market_data)
            self._tool_registry.register(generate_chart_json)
            self._tool_registry.register(search_news)
            self._tool_registry.register(interpret_backtest)

        # monitor 模式：扫描 + 简报 + 摘要 + 新闻分析 + 监控管理工具
        elif mode == "monitor":
            from stockquant.ai.chat_tools import (
                query_market_data,
                search_news,
                start_monitoring,
                stop_monitoring,
                check_monitor_status,
            )
            self._tool_registry.register(query_market_data)
            self._tool_registry.register(search_news)
            self._tool_registry.register(start_monitoring)
            self._tool_registry.register(stop_monitoring)
            self._tool_registry.register(check_monitor_status)
            try:
                from stockquant.ai.monitor_agent import MonitorAgent  # noqa: F401
                # monitor_agent 的 scan / brief / summary 通过已有工具覆盖
            except ImportError:
                logger.debug("MonitorAgent not available")

        # decision 模式：信号验证 + 风险评估 + 市场环境 + 监控管理工具
        elif mode == "decision":
            from stockquant.ai.chat_tools import (
                query_market_data,
                search_news,
                start_monitoring,
                stop_monitoring,
                check_monitor_status,
            )
            self._tool_registry.register(query_market_data)
            self._tool_registry.register(search_news)
            self._tool_registry.register(start_monitoring)
            self._tool_registry.register(stop_monitoring)
            self._tool_registry.register(check_monitor_status)
            try:
                from stockquant.agent.decision_tools import verify_signal, assess_risk, check_market_env
                self._tool_registry.register(verify_signal)
                self._tool_registry.register(assess_risk)
                self._tool_registry.register(check_market_env)
            except ImportError:
                logger.debug("decision_tools not available")

        # general 模式：仅基础工具（已在 __init__ 中注册）
        # 无需额外注册

    def _ensure_conversation(self, conversation_id: str) -> Conversation:
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = Conversation(
                conversation_id=conversation_id,
                memory=self._memory,
            )
        return self._conversations[conversation_id]

    def register_tool(self, tool_fn: Any) -> None:
        """注册对话工具。"""
        self._tool_registry.register(tool_fn)

    def chat(
        self,
        message: str,
        conversation_id: str = "default",
        model: Optional[str] = None,
        mode: str = "general",
    ) -> str:
        """发送消息并获取 AI 回复（通过 ReActAgent + 工具调用）。

        Parameters
        ----------
        mode : str
            对话模式：'general' | 'strategy' | 'analysis' | 'monitor' | 'decision'
        """
        conv = self._ensure_conversation(conversation_id)
        conv.add_message("user", message)

        # 根据模式注册对应工具集
        self._register_mode_tools(mode)

        history = conv.get_history(limit=15)
        system_prompt = MODE_SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPT)
        history.insert(0, {"role": "system", "content": system_prompt})

        # 通过 ReActAgent 执行工具调用
        try:
            from stockquant.agent.react_agent import ReActAgent

            react = ReActAgent(
                model=self._adapter._model,
                api_key=self._adapter._api_key,
                base_url=self._adapter._base_url,
                max_steps=5,
            )

            result = react.run(message)

            # ReActAgent 成功返回答案
            if result.final_answer and result.success:
                conv.add_message("assistant", result.final_answer)
                return result.final_answer

            # ReActAgent 未产出有效结果 → 降级为直接 LLM 调用
            logger.warning(
                "ReActAgent 未产出有效结果 (success=%s, error=%s)，降级为直接 LLM 调用",
                result.success, result.error,
            )
            return self._chat_fallback(message, conversation_id, model)

        except ImportError:
            # 降级：直接调用 LLM（无工具）
            logger.warning("ReActAgent not available, falling back to direct LLM call")
            return self._chat_fallback(message, conversation_id, model)
        except Exception as exc:
            # ReActAgent 初始化或运行时异常 → 降级
            logger.error("ReActAgent 异常，降级为直接 LLM 调用: %s", exc)
            try:
                return self._chat_fallback(message, conversation_id, model)
            except Exception as fallback_exc:
                error_msg = f"AI 调用失败: {fallback_exc}"
                conv.add_message("assistant", error_msg)
                return error_msg

    def _chat_fallback(
        self,
        message: str,
        conversation_id: str,
        model: Optional[str] = None,
    ) -> str:
        """降级模式：直接调用 LLM，不通过 ReActAgent。"""
        conv = self._conversations.get(conversation_id)
        if conv is None:
            conv = self._ensure_conversation(conversation_id)
            conv.add_message("user", message)

        history = conv.get_history(limit=15)
        system_prompt = MODE_SYSTEM_PROMPTS.get("general", SYSTEM_PROMPT)
        history.insert(0, {"role": "system", "content": system_prompt})

        try:
            response = self._adapter.call(
                messages=history,
                model=model,
                temperature=0.3,
                max_tokens=2048,
            )
            reply = response.content or "抱歉，我没有收到有效回复。"
            conv.add_message("assistant", reply)
            return reply
        except Exception as exc:
            error_msg = f"AI 调用失败: {exc}"
            conv.add_message("assistant", error_msg)
            logger.error("Chat failed for conversation %s: %s", conversation_id, exc)
            return error_msg

    def chat_stream(
        self,
        message: str,
        conversation_id: str = "default",
        mode: str = "general",
    ) -> Generator[str, None, None]:
        """流式对话（SSE 兼容）。"""
        conv = self._ensure_conversation(conversation_id)
        conv.add_message("user", message)

        history = conv.get_history(limit=15)
        system_prompt = MODE_SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPT)
        history.insert(0, {"role": "system", "content": system_prompt})

        try:
            response = self._adapter.call(
                messages=history,
                temperature=0.3,
                max_tokens=2048,
            )
            reply = response.content or ""
            conv.add_message("assistant", reply)
            for char in reply:
                yield char
        except Exception as exc:
            error_msg = f"AI 调用失败: {exc}"
            for char in error_msg:
                yield char

    def get_conversation(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        """获取会话消息历史"""
        conv = self._conversations.get(conversation_id)
        if conv is None:
            return []
        return conv.messages[-limit:]

    def get_all_conversations(self) -> List[str]:
        """获取所有会话 ID"""
        return list(self._conversations.keys())

    def clear_conversation(self, conversation_id: str) -> bool:
        """清空会话"""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            if self._memory:
                self._memory.delete_messages(conversation_id)
            return True
        return False
