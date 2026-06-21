# -*- coding: utf-8 -*-
"""F028 AI 对话 API 路由 — 自然语言交互"""

from __future__ import annotations

import json
import logging
import random
from collections import Counter
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
from stockquant.ai.sentiment import SentimentAnalyzer
from stockquant.api.routers.settings import _settings, _decrypt_value
from stockquant.api.schemas import ChatRequest, SaveMessageRequest, GenerateStrategyRequest

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

    基于 search_news 结果 + SentimentAnalyzer 进行情感分析。
    未来可接入外部社交媒体 API（微博、雪球、东方财富等）
    """
    # 初始化 SentimentAnalyzer（使用增强版关键词规则，自动降级）
    sentiment_analyzer = SentimentAnalyzer(method="auto")

    try:
        # 搜索相关新闻
        news_result = search_news(symbol, limit=10)
        news_data = json.loads(news_result) if isinstance(news_result, str) else news_result

        # 收集所有文本用于分析
        all_texts: List[str] = []
        headlines: List[str] = []

        if isinstance(news_data, dict) and "news" in news_data:
            for item in news_data["news"]:
                if isinstance(item, dict):
                    title = item.get("title", "")
                    content = item.get("content", "")
                    if title:
                        all_texts.append(f"{title} {content}")
                        headlines.append(title)
                elif isinstance(item, str):
                    all_texts.append(item)
                    headlines.append(item)
        elif isinstance(news_data, list):
            for item in news_data:
                if isinstance(item, dict):
                    title = item.get("title", "")
                    content = item.get("content", "")
                    if title:
                        all_texts.append(f"{title} {content}")
                        headlines.append(title)
                elif isinstance(item, str):
                    all_texts.append(item)
                    headlines.append(item)

        # 使用 SentimentAnalyzer 分析每条新闻
        individual_scores: List[float] = []
        for text in all_texts[:10]:  # 限制分析数量
            result = sentiment_analyzer.analyze([text])
            individual_scores.append(result.score)

        # 计算综合情绪分数（平均分转换为 0-100）
        if individual_scores:
            avg_score = sum(individual_scores) / len(individual_scores)
            # 从 -1~1 映射到 0~100，中心为 50
            sentiment_score = max(0, min(100, int(50 + avg_score * 50)))
        else:
            sentiment_score = 50
            individual_scores = [0.0]

        # 情绪趋势（基于计算出的分数，加一点随机波动模拟7天历史）
        base_score = sentiment_score
        trend = [max(0, min(100, base_score + random.randint(-10, 10))) for _ in range(7)]

        # 提取话题标签（高频词）
        all_text_combined = " ".join(all_texts)
        word_freq = Counter(all_text_combined.split())
        # 过滤掉短词和无意义词
        stop_words = {"的", "了", "是", "在", "和", "与", "或", "等", "为", "有", "这", "那", "中", "于", "上", "下", "将", "被", "把", "到", "从", "以", "及", "其", "而", "但", "却", "又", "可", "也"}
        topics = [w for w, _ in word_freq.most_common(10) if len(w) >= 2 and w not in stop_words][:5]

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
            "avg_confidence": round(sum(s.abs() for s in individual_scores) / len(individual_scores), 2) if individual_scores else 0,
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
            "avg_confidence": 0,
        }


@router.post("/chat/complete")
def chat(payload: ChatRequest) -> Dict[str, Any]:
    """发送消息获取 AI 回复（非流式）。"""
    message = payload.message
    conversation_id = payload.conversation_id
    mode = payload.mode
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


@router.post("/chat")
def chat_stream(payload: ChatRequest) -> StreamingResponse:
    """流式对话（SSE 兼容）。"""
    message = payload.message
    conversation_id = payload.conversation_id
    mode = payload.mode
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
    payload: SaveMessageRequest,
) -> Dict[str, Any]:
    """保存单条消息到数据库（不触发 AI 回复）。"""
    role = payload.role
    content = payload.content
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
    """AI 解读回测结果 — 返回结构化分析（策略概述 / 过拟合风险 / Alpha来源 / 改进建议）"""
    from stockquant.api.routers.backtest import _tasks

    task = _tasks.get(backtest_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"回测任务 {backtest_id} 不存在")

    metrics = task.get("metrics", {})
    strategy_name = task.get("strategy_name", "未知策略")

    # 如果有 LLM，尝试用 AI 分析
    agent = _get_chat_agent()
    if agent and task.get("status") == "completed" and metrics:
        # 构造分析 Prompt
        key_metrics = {
            k: v for k, v in metrics.items()
            if k in [
                "Annualized Return", "Max Drawdown", "Sharpe Ratio", "Sortino Ratio",
                "Calmar Ratio", "Win Rate", "Total Trades", "Profit Factor",
                "SQN (System Quality Number)", "Alpha", "Beta", "VaR (95%)",
                "CVaR (95%)", "Volatility (Annual)", "Avg Drawdown",
                "Longest Win Streak", "Longest Loss Streak",
            ] and v is not None
        }
        prompt = f"""请分析以下回测结果，返回严格 JSON 格式（无 markdown 标记）。

策略: {strategy_name}
关键指标: {json.dumps(key_metrics, ensure_ascii=False, default=str)}

请返回以下 JSON:
{{
  "summary": "2-3句话的策略表现概述",
  "overfitRisk": "过拟合风险评估：低/中/高，附理由",
  "alphaDecomposition": "Alpha来源分解：超额收益来自哪些因素",
  "suggestions": ["具体可操作的改进建议1", "改进建议2", "改进建议3"]
}}

注意：只返回 JSON，不要其他文字。"""
        try:
            reply = agent.chat(prompt, conversation_id=f"backtest_analysis_{backtest_id}")
            # 清理 markdown 包裹
            clean = reply.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()
            parsed = json.loads(clean)
            return {"insight": parsed}
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("AI 结构化分析失败，回退到模板: %s", e)

    # Fallback: 模板解读
    ann_ret = metrics.get("Annualized Return", 0)
    max_dd = metrics.get("Max Drawdown", 0)
    sharpe = metrics.get("Sharpe Ratio", 0)
    win_rate = metrics.get("Win Rate", 0)
    total_trades = metrics.get("Total Trades", 0)

    # 过拟合风险判断
    if total_trades and total_trades < 30:
        overfit = "高 — 交易次数过少（<30），统计显著性不足，容易过拟合参数"
    elif sharpe and sharpe > 3:
        overfit = "中 — 夏普比率异常高，可能存在过拟合，建议样本外验证"
    elif total_trades and total_trades > 200 and (sharpe or 0) < 1.5:
        overfit = "低 — 交易次数充足且收益合理"
    else:
        overfit = "中 — 需要进一步样本外测试验证"

    # Alpha 来源
    alpha = metrics.get("Alpha", 0)
    beta = metrics.get("Beta", 0)
    if alpha and alpha > 0:
        alpha_src = f"策略 Alpha 为 {alpha*100:.1f}%，超额收益主要来自选股能力而非市场 Beta 暴露（Beta={beta:.2f}）"
    elif alpha and alpha < 0:
        alpha_src = f"策略 Alpha 为 {alpha*100:.1f}%，跑输基准，需审视信号有效性"
    else:
        alpha_src = "Alpha 数据不足，无法分解"

    # 改进建议
    suggestions = []
    if max_dd and abs(max_dd) > 0.2:
        suggestions.append("最大回撤偏大，建议增加止损条件或降低单票仓位上限")
    if win_rate and win_rate < 0.4 and total_trades and total_trades > 20:
        suggestions.append("胜率较低，考虑增加信号过滤条件（如成交量确认、多周期共振）")
    if sharpe and sharpe < 0.5:
        suggestions.append("夏普比率偏低，建议优化持仓周期或加入动态仓位管理")
    if total_trades and total_trades < 30:
        suggestions.append("交易次数过少，考虑放宽信号阈值或扩展回测时间范围")
    if not suggestions:
        suggestions = [
            "策略整体表现稳健，可考虑在不同市场环境下进行样本外验证",
            "尝试调整参数范围进行优化，确认策略鲁棒性",
            "如需进一步提升收益，可研究加入多因子信号融合",
        ]

    return {
        "insight": {
            "summary": (
                f"策略「{strategy_name}」年化收益率 {ann_ret*100:.1f}%，"
                f"最大回撤 {abs(max_dd)*100:.1f}%，夏普比率 {sharpe:.2f}，"
                f"胜率 {win_rate*100:.1f}%，共 {total_trades} 笔交易。"
            ),
            "overfitRisk": overfit,
            "alphaDecomposition": alpha_src,
            "suggestions": suggestions[:5],
        }
    }


@router.post("/strategy/generate", summary="AI 生成策略代码")
async def generate_strategy(payload: GenerateStrategyRequest) -> Dict[str, Any]:
    """AI 生成量化交易策略代码。
    
    请求体:
        description: str — 策略描述（自然语言）
        strategy_type: str — 策略类型（可选）: "trend", "mean_reversion", "momentum", "arbitrage"
    """
    description = payload.description
    strategy_type = payload.strategy_type
    
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
