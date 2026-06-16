# -*- coding: utf-8 -*-
"""F028 AI 对话 API 路由 — 自然语言交互"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from stockquant.ai.chat_agent import ChatAgent
from stockquant.ai.chat_memory import ChatMemory
from stockquant.ai.chat_tools import (
    query_market_data,
    generate_chart_json,
    trigger_backtest,
    search_news,
)

router = APIRouter(prefix="/ai", tags=["ai"])

logger = logging.getLogger("stockquant.ai")

# 全局 AI 实例
_chat_agent: Optional[ChatAgent] = None
_chat_memory: Optional[ChatMemory] = None


def _get_chat_agent() -> ChatAgent:
    global _chat_agent
    if _chat_agent is None:
        _chat_agent = ChatAgent()
    return _chat_agent


def _get_chat_memory() -> ChatMemory:
    global _chat_memory
    if _chat_memory is None:
        _chat_memory = ChatMemory()
    return _chat_memory


@router.post("/chat")
def chat(message: str, conversation_id: str = "default") -> Dict[str, Any]:
    """发送消息获取 AI 回复。

    Parameters
    ----------
    message : str
        用户消息
    conversation_id : str
        会话 ID
    """
    agent = _get_chat_agent()
    reply = agent.chat(message, conversation_id=conversation_id)
    messages = agent.get_conversation(conversation_id, limit=10)

    return {
        "conversation_id": conversation_id,
        "reply": reply,
        "history": [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat() if hasattr(m.timestamp, "isoformat") else str(m.timestamp),
            }
            for m in messages[-10:]
        ],
    }


@router.post("/chat/stream")
def chat_stream(message: str, conversation_id: str = "default") -> StreamingResponse:
    """流式对话（SSE 兼容）。"""
    agent = _get_chat_agent()

    def event_generator():
        for event in agent.chat_stream(message, conversation_id):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations")
def list_conversations() -> Dict[str, Any]:
    """列出所有会话。"""
    agent = _get_chat_agent()
    return {"conversations": agent.get_all_conversations()}


@router.get("/conversation/{conversation_id}")
def get_conversation(conversation_id: str, limit: int = 50) -> Dict[str, Any]:
    """获取会话历史。"""
    agent = _get_chat_agent()
    messages = agent.get_conversation(conversation_id, limit=limit)
    return {
        "conversation_id": conversation_id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat() if hasattr(m.timestamp, "isoformat") else str(m.timestamp),
            }
            for m in messages
        ],
    }


@router.delete("/conversation/{conversation_id}")
def clear_conversation(conversation_id: str) -> Dict[str, Any]:
    """清空会话。"""
    agent = _get_chat_agent()
    success = agent.clear_conversation(conversation_id)
    return {"cleared": success}


@router.post("/tools/query_market_data")
def tool_query_market_data(symbol: str, days: int = 30) -> Dict[str, Any]:
    """查询市场数据。"""
    result = query_market_data(symbol, days=days)
    return json.loads(result) if isinstance(result, str) else result


@router.post("/tools/search_news")
def tool_search_news(symbol: str, limit: int = 5) -> Dict[str, Any]:
    """搜索新闻。"""
    result = search_news(symbol, limit=limit)
    return json.loads(result) if isinstance(result, str) else result


@router.post("/analyze-backtest/{backtest_id}", summary="AI 解读回测结果")
async def analyze_backtest(backtest_id: str):
    """AI 解读回测结果"""
    # MVP: 返回模板解读
    return {
        "insight": (
            f"回测任务 {backtest_id} 的 AI 解读：\n\n"
            "1. **策略表现**: 该策略在回测期间表现出较好的收益风险比，"
            "年化收益率处于中等偏上水平。\n\n"
            "2. **风险分析**: 最大回撤控制在合理范围内，"
            "建议关注尾部风险事件的影响。\n\n"
            "3. **优化建议**: 可考虑调整止损参数和仓位管理策略，"
            "以进一步改善风险调整后收益。\n\n"
            "4. **市场适应性**: 策略在趋势行情中表现较佳，"
            "震荡市中需注意信号过滤。"
        )
    }
