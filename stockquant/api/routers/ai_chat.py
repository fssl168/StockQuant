# -*- coding: utf-8 -*-
"""F028 AI 对话 API 路由 — 自然语言交互"""

from __future__ import annotations

import json
import os
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import StreamingResponse

from stockquant.ai.chat_agent import ChatAgent
from stockquant.ai.chat_memory import ChatMemory
from stockquant.ai.chat_tools import (
    query_market_data,
    generate_chart_json,
    trigger_backtest,
    search_news,
)
from stockquant.api.routers.settings import _settings, _decrypt_value

router = APIRouter(prefix="/ai", tags=["ai"])

logger = logging.getLogger("stockquant.ai")

# 全局 AI 实例
_chat_agent: Optional[ChatAgent] = None
_chat_memory: Optional[ChatMemory] = None


def _get_chat_agent() -> ChatAgent:
    global _chat_agent
    if _chat_agent is None:
        model = _settings.get("ai.model", "gpt-4o")
        api_key_raw = _settings.get("ai.api_key", "")
        api_base_raw = _settings.get("ai.api_base", "")
        db_url = _settings.get("database.url")
        # 解密敏感值（settings 存储的是 Fernet 加密后的值）
        api_key = _decrypt_value(api_key_raw) if api_key_raw else ""
        api_base = _decrypt_value(api_base_raw) if api_base_raw else ""
        _chat_agent = ChatAgent(
            model=model,
            api_key=api_key if api_key else None,
            base_url=api_base if api_base else None,
            db_url=db_url,  # 传入 db_url 使内部 ChatMemory 生效，消息持久化到数据库
        )
    return _chat_agent


def _get_chat_memory() -> ChatMemory:
    global _chat_memory
    if _chat_memory is None:
        _chat_memory = ChatMemory()
    return _chat_memory


@router.get("/sentiment", summary="社交媒体情绪分析")
async def sentiment_analysis(symbol: str = Query("sh600519", description="股票代码")):
    """分析指定股票的市场情绪。
    
    MVP 实现：基于 search_news 结果 + 关键词简单分析
    未来可接入外部社交媒体 API（微博、雪球、东方财富等）
    """
    try:
        # 搜索相关新闻
        news_result = search_news(symbol, limit=10)
        news_data = json.loads(news_result) if isinstance(news_result, str) else news_result
        
        # 基于关键词的情绪分析（简单版）
        positive_words = ["利好", "上涨", "突破", "增长", "盈利", "强劲", "看好", "买入", "推荐", "新高", "反弹"]
        negative_words = ["利空", "下跌", "亏损", "风险", "预警", "暴跌", "跌停", "减持", "抛售", "违约", "调查"]
        
        all_text = ""
        headlines = []
        if isinstance(news_data, dict) and "news" in news_data:
            for item in news_data["news"]:
                if isinstance(item, dict):
                    all_text += item.get("title", "") + " " + item.get("content", "")
                    if item.get("title"):
                        headlines.append(item["title"])
                elif isinstance(item, str):
                    all_text += item
                    headlines.append(item)
        elif isinstance(news_data, list):
            for item in news_data:
                if isinstance(item, dict):
                    all_text += item.get("title", "") + " " + item.get("content", "")
                    if item.get("title"):
                        headlines.append(item["title"])
                elif isinstance(item, str):
                    all_text += item
                    headlines.append(item)
        
        # 计算情绪分数
        pos_count = sum(1 for w in positive_words if w in all_text)
        neg_count = sum(1 for w in negative_words if w in all_text)
        
        # 归一化到 0-100
        sentiment_score = max(0, min(100, 50 + (pos_count - neg_count) * 8))
        
        # 情绪趋势（模拟近 7 天数据）
        import random
        base_score = sentiment_score
        trend = [max(0, min(100, base_score + random.randint(-10, 10))) for _ in range(7)]
        
        # 提取话题标签
        from collections import Counter
        word_freq = Counter(all_text.split())
        topics = [w for w, _ in word_freq.most_common(5) if len(w) >= 2][:5]
        
        # 情绪总结
        if sentiment_score >= 70:
            summary = f"近期市场情绪偏乐观，{symbol} 相关新闻以正面消息为主。"
        elif sentiment_score <= 30:
            summary = f"近期市场情绪偏谨慎，{symbol} 相关新闻存在一定负面因素，建议关注风险。"
        else:
            summary = f"近期市场情绪中性，{symbol} 利好与利空消息交织，需结合技术面综合判断。"
        
        return {
            "symbol": symbol,
            "score": sentiment_score,
            "trend": trend,
            "topics": topics if topics else ["市场动态", "板块轮动", "资金流向"],
            "summary": summary,
            "news_count": len(headlines),
        }
    except Exception as exc:
        logger.error("情绪分析失败: %s", exc)
        return {
            "symbol": symbol,
            "score": 50,
            "trend": [50] * 7,
            "topics": [],
            "summary": "暂无情绪数据",
            "news_count": 0,
        }


@router.post("/chat")
def chat(payload: dict = Body(...)) -> Dict[str, Any]:
    """发送消息获取 AI 回复。"""
    message = payload.get("message", "")
    conversation_id = payload.get("conversation_id", "default")
    mode = payload.get("mode", "general")
    agent = _get_chat_agent()
    reply = agent.chat(message, conversation_id=conversation_id, mode=mode)
    raw_messages = agent.get_conversation(conversation_id, limit=10)

    # 兼容 dict 和 object 两种格式
    history = []
    for m in raw_messages:
        if isinstance(m, dict):
            history.append({
                "role": m.get("role", ""),
                "content": m.get("content", ""),
                "timestamp": m.get("timestamp", "") if isinstance(m.get("timestamp"), str) else str(m.get("timestamp", "")),
            })
        else:
            history.append({
                "role": getattr(m, "role", ""),
                "content": getattr(m, "content", ""),
                "timestamp": getattr(m, "timestamp", "").isoformat() if hasattr(getattr(m, "timestamp", None), "isoformat") else str(getattr(m, "timestamp", "")),
            })

    return {
        "conversation_id": conversation_id,
        "reply": reply,
        "history": history[-10:],
    }


@router.post("/chat/stream")
def chat_stream(payload: dict = Body(...)) -> StreamingResponse:
    """流式对话（SSE 兼容）。"""
    message = payload.get("message", "")
    conversation_id = payload.get("conversation_id", "default")
    mode = payload.get("mode", "general")
    agent = _get_chat_agent()

    def event_generator():
        for event in agent.chat_stream(message, conversation_id, mode=mode):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations")
def list_conversations() -> Dict[str, Any]:
    """列出所有会话（从数据库读取）。"""
    try:
        from stockquant.persistence.repository import list_chat_sessions
        db_url = _settings.get("database.url")
        sessions = list_chat_sessions(db_url)
        return {"conversations": sessions}
    except Exception:
        # 降级：返回空列表
        return {"conversations": []}


@router.get("/conversation/{conversation_id}")
def get_conversation(conversation_id: str, limit: int = 50) -> Dict[str, Any]:
    """获取会话历史（从数据库读取）。"""
    try:
        from stockquant.persistence.repository import get_chat_messages
        db_url = _settings.get("database.url")
        messages = get_chat_messages(db_url, conversation_id, limit=limit)
        return {"conversation_id": conversation_id, "messages": messages}
    except Exception:
        return {"conversation_id": conversation_id, "messages": []}


@router.post("/conversation/{conversation_id}/message")
def save_message(
    conversation_id: str,
    payload: dict = Body(...),
) -> Dict[str, Any]:
    """保存单条消息到数据库（不触发 AI 回复）。"""
    role = payload.get("role", "user")
    content = payload.get("content", "")
    try:
        from stockquant.persistence.repository import save_chat_message
        db_url = _settings.get("database.url")
        from datetime import datetime
        msg_id = save_chat_message(
            engine_url=db_url,
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        return {"saved": True, "id": msg_id}
    except Exception:
        return {"saved": False, "id": None}


@router.delete("/conversation/{conversation_id}")
def clear_conversation(conversation_id: str) -> Dict[str, Any]:
    """清空会话（从数据库删除）。"""
    try:
        from stockquant.persistence.repository import delete_chat_messages
        db_url = _settings.get("database.url")
        delete_chat_messages(db_url, conversation_id)
        return {"cleared": True}
    except Exception:
        return {"cleared": False}


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


@router.post("/strategy/generate", summary="AI 生成策略代码")
async def generate_strategy(payload: dict):
    """AI 生成量化交易策略代码。
    
    请求体:
        description: str — 策略描述（自然语言）
        strategy_type: str — 策略类型（可选）: "trend", "mean_reversion", "momentum", "arbitrage"
    """
    description = payload.get("description", "")
    strategy_type = payload.get("strategy_type", "trend")
    
    if not description.strip():
        raise HTTPException(status_code=400, detail="策略描述不能为空")
    
    agent = _get_chat_agent()
    
    # 调用 AI 生成策略代码
    prompt = f"""你是一个专业的量化交易策略开发者。请根据以下描述生成一个完整的双因子策略代码（使用 Python，基于 Cerebro 框架）。

策略描述: {description}
策略类型: {strategy_type}

要求:
1. 继承自 CerebroStrategy 基类
2. 实现 on_bar(candle) 方法处理每根K线
3. 包含买入/卖出信号逻辑
4. 包含必要的参数和配置
5. 代码要完整可运行
6. 添加详细注释说明策略逻辑

请直接返回 Python 代码，不要其他解释。"""

    reply = agent.chat(prompt, conversation_id="strategy_gen")
    
    # 提取代码块
    code = reply
    if "```python" in reply:
        code = reply.split("```python")[1].split("```")[0].strip()
    elif "```" in reply:
        code = reply.split("```")[1].split("```")[0].strip()
    
    strategy_names = {
        "trend": "趋势跟踪策略",
        "mean_reversion": "均值回归策略", 
        "momentum": "动量策略",
        "arbitrage": "套利策略",
    }
    
    return {
        "code": code,
        "name": strategy_names.get(strategy_type, "自定义策略"),
        "description": description,
    }
