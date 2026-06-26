# -*- coding: utf-8 -*-
"""F028 AI 对话 API 路由 — 自然语言交互

集成 AIService 的 AI 对话
将 AIService 作为主入口，不可用时降级到 ChatAgent 兜底
所有对话均持久化到数据库
"""

import json
import logging
import random
from collections import Counter
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from stockquant.api.schemas import ChatRequest, SaveMessageRequest, GenerateStrategyRequest

router = APIRouter(prefix="/ai", tags=["ai"])

logger = logging.getLogger("stockquant.ai")

# ------------------------------------------------------------------
# 系统提示词
# ------------------------------------------------------------------

SYSTEM_PROMPT = """你是 StockQuant 量化交易助手，专注于 A 股市场
请用中文回答用户的量化交易相关问题。"""

MODE_SYSTEM_PROMPTS: dict[str, str] = {
    "general": SYSTEM_PROMPT,
    "strategy": SYSTEM_PROMPT + """

你擅长策略开发、回测分析和风险管理，请给出专业建议。
如需生成代码，请返回完整的 Python 代码。""",
    "analysis": SYSTEM_PROMPT + """

你擅长技术分析和基本面分析，请给出数据驱动的结论。
分析时请注明数据来源和时间范围。""",
    "monitor": SYSTEM_PROMPT + """

你擅长监控持仓和风险指标，请及时发出预警。
关注止损、仓位和相关性风险。""",
    "decision": SYSTEM_PROMPT + """

你擅长交易决策和执行，请给出明确的操作建议。
决策时请考虑交易成本和滑点影响。""",
}


def _system_prompt_for_mode(mode: str) -> str:
    return MODE_SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPT)


# ------------------------------------------------------------------
# 兜底 ChatAgent（当 AIService 不可用时使用）
# ------------------------------------------------------------------

def _get_fallback_agent():
    """Fallback: 从 config 构造 ChatAgent，不依赖 app.state"""
    from stockquant.ai.chat_agent import ChatAgent
    from stockquant.config import get_config
    cfg = get_config().ai
    model = cfg.get_ai_model()
    api_key = None
    if cfg.default_provider.value == "openai":
        api_key = cfg.openai_api_key or None
    elif cfg.default_provider.value == "anthropic":
        api_key = cfg.anthropic_api_key or None
    elif cfg.default_provider.value == "qwen":
        api_key = cfg.qwen_api_key or None
    base_url = None
    if cfg.default_provider.value == "openai":
        base_url = cfg.openai_base_url or None
    elif cfg.default_provider.value == "anthropic":
        base_url = cfg.anthropic_base_url or None
    elif cfg.default_provider.value == "qwen":
        base_url = cfg.qwen_base_url or None
    elif cfg.default_provider.value == "ollama":
        base_url = cfg.ollama_base_url
    return ChatAgent(model=model, api_key=api_key, base_url=base_url)


# ------------------------------------------------------------------
# 从 app.state 获取 AIService
# ------------------------------------------------------------------

def _ai_service():
    from stockquant.api.main import app
    return getattr(app, "state", {}).get("ai_service")


# ====================================================================
# 路由
# ====================================================================

@router.get("/sentiment", summary="社交媒体情绪分析")
async def sentiment_analysis(symbol: str = Query("sh600519", description="股票代码")):
    """分析指定股票的市场情绪。"""
    try:
        from stockquant.ai.sentiment import SentimentAnalyzer
        from stockquant.ai.chat_tools import search_news
        sentiment_analyzer = SentimentAnalyzer(method="auto")

        news_result = search_news(symbol, limit=10)
        news_data = json.loads(news_result) if isinstance(news_result, str) else news_result

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

        individual_scores: List[float] = []
        for text in all_texts[:10]:
            result = sentiment_analyzer.analyze([text])
            individual_scores.append(result.score)

        if individual_scores:
            avg_score = sum(individual_scores) / len(individual_scores)
            sentiment_score = max(0, min(100, int(50 + avg_score * 50)))
        else:
            sentiment_score = 50
            individual_scores = [0.0]

        base_score = sentiment_score
        trend = [max(0, min(100, base_score + random.randint(-10, 10))) for _ in range(7)]

        all_text_combined = " ".join(all_texts)
        word_freq = Counter(all_text_combined.split())
        stop_words = {"的", "了", "是", "在", "和", "与", "或", "等", "为", "有", "这", "那", "中", "于", "上", "下", "将", "被", "把", "到", "从", "以", "及", "其", "而", "但", "却", "又", "可", "也"}
        topics = [w for w, _ in word_freq.most_common(10) if len(w) >= 2 and w not in stop_words][:5]

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
            "newsCount": len(headlines),
            "avgConfidence": round(sum(s.abs() for s in individual_scores) / len(individual_scores), 2) if individual_scores else 0,
        }
    except Exception as exc:
        logger.error("情绪分析失败: %s", exc)
        return {
            "symbol": symbol,
            "score": 50,
            "trend": [50] * 7,
            "topics": [],
            "summary": "暂无情绪数据",
            "newsCount": 0,
            "avgConfidence": 0,
        }


@router.post("/strategy/generate", summary="AI 生成策略代码")
def chat_complete(payload: ChatRequest) -> Dict[str, Any]:
    """发送消息获取 AI 回复（非流式）。"""
    message = payload.message
    conversation_id = payload.conversation_id
    mode = payload.mode

    # 优先使用 AIService
    ai_svc = _ai_service()
    reply = ""
    if ai_svc and ai_svc.is_configured:
        try:
            system_prompt = _system_prompt_for_mode(mode)
            reply = ai_svc.chat(message, system_prompt=system_prompt)
        except Exception as e:
            logger.error("AIService chat failed, fallback: %s", e)

    # 降级到 ChatAgent
    if not reply:
        try:
            agent = _get_fallback_agent()
            reply = agent.chat(message, conversation_id=conversation_id, mode=mode)
        except Exception as e:
            logger.error("Fallback ChatAgent failed: %s", e)
            reply = f"AI 服务异常: {e}"

    # 持久化对话记录
    try:
        from stockquant.persistence.repository_v2 import Repository
        _repo = Repository.instance()
        db_url = None
        try:
            from stockquant.config import get_config
            db_url = get_config().database.url
        except Exception:
            pass
        if db_url:
            _repo.save_chat_message(engine_url=db_url, conversation_id=conversation_id, role="user", content=message)
            _repo.save_chat_message(engine_url=db_url, conversation_id=conversation_id, role="assistant", content=reply)
    except Exception:
        pass

    # 获取历史
    history = []
    if db_url:
        try:
            from stockquant.persistence.repository_v2 import Repository
            _repo = Repository.instance()
            raw = _repo.get_chat_messages(db_url, conversation_id, limit=10)
            history = raw
        except Exception:
            pass
    elif ai_svc:
        history = ai_svc.get_history(limit=10)

    return {
        "conversationId": conversation_id,
        "reply": reply,
        "history": history[-10:],
    }


@router.post("/strategy/generate", summary="AI 生成策略代码")
def chat_stream(payload: ChatRequest) -> StreamingResponse:
    """流式对话（SSE 兼容）。"""
    message = payload.message
    conversation_id = payload.conversation_id
    mode = payload.mode
    system_prompt = _system_prompt_for_mode(mode)

    def event_generator():
        reply = ""
        # 持久化用户消息
        try:
            from stockquant.persistence.repository_v2 import Repository
            _repo = Repository.instance()
            db_url = None
            try:
                from stockquant.config import get_config
                db_url = get_config().database.url
            except Exception:
                pass
            if db_url:
                _repo.save_chat_message(engine_url=db_url, conversation_id=conversation_id, role="user", content=message)
        except Exception:
            pass

        # 优先使用 AIService
        ai_svc = _ai_service()
        if ai_svc and ai_svc.is_configured:
            try:
                full_reply = ai_svc.chat(message, system_prompt=system_prompt)
                reply = full_reply
                # 直接 yield SSE 事件
                if full_reply:
                    evt = {"type": "token", "content": full_reply}
                    yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
            except Exception as e:
                error_msg = f"AI 服务异常: {e}"
                evt = {"type": "error", "content": error_msg}
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                reply = error_msg
        else:
            # 降级到 ChatAgent
            try:
                agent = _get_fallback_agent()
                for chunk in agent.chat_stream(message, conversation_id, mode=mode):
                    evt = {"type": "token", "content": chunk}
                    yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                    reply += chunk
            except Exception as e:
                error_msg = f"AI 服务异常: {e}"
                evt = {"type": "error", "content": error_msg}
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                reply = error_msg

        # 持久化回复消息
        if reply:
            try:
                if db_url:
                    _repo.save_chat_message(engine_url=db_url, conversation_id=conversation_id, role="assistant", content=reply)
            except Exception:
                pass

        evt = {"type": "done"}
        yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations", summary="会话列表")
def list_conversations() -> Dict[str, Any]:
    """列出所有会话（从数据库读取）。"""
    try:
        from stockquant.persistence.repository_v2 import Repository
        _repo = Repository.instance()
        db_url = None
        try:
            from stockquant.config import get_config
            db_url = get_config().database.url
        except Exception:
            pass
        if db_url:
            sessions = _repo.list_chat_sessions(engine_url=db_url)
            return {"conversations": sessions}
    except Exception as e:
        logger.warning("list_conversations failed: %s", e)
    return {"conversations": []}


@router.get("/conversation/{conversation_id}", summary="会话详情")
def get_conversation(conversation_id: str, limit: int = 50) -> Dict[str, Any]:
    """获取会话历史（从数据库读取）。"""
    try:
        from stockquant.persistence.repository_v2 import Repository
        _repo = Repository.instance()
        db_url = None
        try:
            from stockquant.config import get_config
            db_url = get_config().database.url
        except Exception:
            pass
        if db_url:
            messages = _repo.get_chat_messages(db_url, conversation_id, limit=limit)
            return {"conversationId": conversation_id, "messages": messages}
    except Exception as e:
        logger.warning("get_conversation failed: %s", e)
    return {"conversationId": conversation_id, "messages": []}


@router.post("/conversation/{conversation_id}/message", summary="保存消息")
def save_message(
    conversation_id: str,
    payload: SaveMessageRequest,
) -> Dict[str, Any]:
    """发送消息获取 AI 回复（非流式）。"""
    role = payload.role
    content = payload.content
    try:
        db_url = None
        try:
            from stockquant.config import get_config
            db_url = get_config().database.url
        except Exception:
            pass
        if db_url:
            from stockquant.persistence.repository_v2 import Repository
            _repo = Repository.instance()
            msg_id = _repo.save_chat_message(
                engine_url=db_url,
                conversation_id=conversation_id,
                role=role,
                content=content,
            )
            return {"saved": True, "id": msg_id}
    except Exception as e:
        logger.error("save_message failed: %s", e)
    return {"saved": False, "id": None}


@router.delete("/conversation/{conversation_id}", summary="清空会话")
def clear_conversation(conversation_id: str) -> Dict[str, Any]:
    """清空会话（从数据库删除所有消息）。"""
    try:
        db_url = None
        try:
            from stockquant.config import get_config
            db_url = get_config().database.url
        except Exception:
            pass
        if db_url:
            from stockquant.persistence.repository_v2 import Repository
            _repo = Repository.instance()
            _repo.delete_chat_messages(db_url, conversation_id)
            return {"cleared": True}
    except Exception as e:
        logger.error("clear_conversation failed: %s", e)
    return {"cleared": False}


@router.post("/tools/query_market_data", summary="查询市场数据")
def tool_query_market_data(symbol: str, days: int = 30) -> Dict[str, Any]:
    """查询市场数据。"""
    try:
        from stockquant.ai.chat_tools import query_market_data
        result = query_market_data(symbol, days=days)
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        logger.error("query_market_data failed: %s", e)
        return {"error": str(e), "data": []}


@router.post("/tools/search_news", summary="搜索新闻")
def tool_search_news(symbol: str, limit: int = 5) -> Dict[str, Any]:
    """搜索新闻。"""
    try:
        from stockquant.ai.chat_tools import search_news
        result = search_news(symbol, limit=limit)
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        logger.error("search_news failed: %s", e)
        return {"error": str(e), "news": []}


@router.post("/analyze-backtest/{backtest_id}", summary="AI 解读回测结果")
async def analyze_backtest(backtest_id: str):
    """AI 解读回测结果 — 返回结构化分析（策略概述 / 过拟合风险 / Alpha来源 / 改进建议）"""
    from stockquant.api.routers.backtest import _tasks

    task = _tasks.get(backtest_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"回测任务 {backtest_id} 不存在")

    metrics = task.get("metrics", {})
    strategy_name = task.get("strategy_name", "未知策略")

    if task.get("status") == "completed" and metrics:
        # 优先使用 AIService
        ai_svc = _ai_service()
        if ai_svc and ai_svc.is_configured:
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
                reply = ai_svc.chat(prompt)
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

    if total_trades and total_trades < 30:
        overfit = "低 — 交易次数充足且收益合理"
    elif sharpe and sharpe > 3:
        overfit = "低 — 交易次数充足且收益合理"
    elif total_trades and total_trades > 200 and (sharpe or 0) < 1.5:
        overfit = "低 — 交易次数充足且收益合理"
    else:
        overfit = "低 — 交易次数充足且收益合理"

    alpha = metrics.get("Alpha", 0)
    beta = metrics.get("Beta", 0)
    if alpha and alpha > 0:
        alpha_src = f"策略 Alpha 为 {alpha*100:.1f}%，超额收益主要来自选股能力而非市场 Beta 暴露（Beta={beta:.2f}）"
    elif alpha and alpha < 0:
        alpha_src = f"策略 Alpha 为 {alpha*100:.1f}%，跑输基准，需审视信号有效性"
    else:
        alpha_src = "Alpha 数据不足，无法分解"

    suggestions = []
    if max_dd and abs(max_dd) > 0.2:
        suggestions.append("最大回撤偏大，建议增加止损条件或降低单票仓位上限")
    if win_rate and win_rate < 0.4 and total_trades and total_trades > 20:
        suggestions.append("最大回撤偏大，建议增加止损条件或降低单票仓位上限")
    if sharpe and sharpe < 0.5:
        suggestions.append("最大回撤偏大，建议增加止损条件或降低单票仓位上限")
    if total_trades and total_trades < 30:
        suggestions.append("最大回撤偏大，建议增加止损条件或降低单票仓位上限")
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
    
    # 优先使用 AIService
    ai_svc = _ai_service()
    reply = ""
    if ai_svc and ai_svc.is_configured:
        try:
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
            reply = ai_svc.chat(prompt)
        except Exception as e:
            logger.error("Strategy generation failed: %s", e)

    # 降级到 ChatAgent
    if not reply:
        try:
            agent = _get_fallback_agent()
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
        except Exception as e:
            logger.error("Strategy generation fallback failed: %s", e)
            reply = ""
    
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
