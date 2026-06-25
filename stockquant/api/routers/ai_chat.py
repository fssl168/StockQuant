# -*- coding: utf-8 -*-
"""F028 AI ?? API ?? ? ??????

??? AIService ?? AI ??
? AIService ?????????? ChatAgent ???
???????????
"""

from __future__ import annotations

import json
import logging
import random
from collections import Counter
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import StreamingResponse

from stockquant.api.schemas import ChatRequest, SaveMessageRequest, GenerateStrategyRequest

router = APIRouter(prefix="/ai", tags=["ai"])

logger = logging.getLogger("stockquant.ai")

# ------------------------------------------------------------------
# ?????
# ------------------------------------------------------------------

SYSTEM_PROMPT = """?? StockQuant ???????????? A ????
???????????????????????"""

MODE_SYSTEM_PROMPTS: dict[str, str] = {
    "general": SYSTEM_PROMPT,
    "strategy": SYSTEM_PROMPT + """

??????????????????????????????????
??????????????????????""",
    "analysis": SYSTEM_PROMPT + """

???????????????????????????????
??????????????????????????""",
    "monitor": SYSTEM_PROMPT + """

??????????????????????????????
?????????""",
    "decision": SYSTEM_PROMPT + """

???????????????????????????
???????????????????????????""",
}


def _system_prompt_for_mode(mode: str) -> str:
    return MODE_SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPT)


# ------------------------------------------------------------------
# ?? ChatAgent ???? AIService ???????
# ------------------------------------------------------------------

def _get_fallback_agent():
    """?????? ChatAgent??????"""
    from stockquant.ai.chat_agent import ChatAgent
    from stockquant.api.routers.settings import _settings, _decrypt_value
    model = _settings.get("ai.model", "gpt-4o")
    api_key_raw = _settings.get("ai.api_key", "")
    api_base_raw = _settings.get("ai.api_base", "")
    api_key = _decrypt_value(api_key_raw) if api_key_raw else ""
    api_base = _decrypt_value(api_base_raw) if api_base_raw else ""
    return ChatAgent(model=model, api_key=api_key if api_key else None, base_url=api_base if api_base else None)


# ------------------------------------------------------------------
# ???? app.state ?? AIService
# ------------------------------------------------------------------

def _ai_service():
    from stockquant.api.main import app
    return getattr(app, "state", {}).get("ai_service")


# ====================================================================
# ??
# ====================================================================

@router.get("/sentiment", summary="????????")
async def sentiment_analysis(symbol: str = Query("sh600519", description="????")):
    """????????????"""
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
        stop_words = {"?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "??", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "??", "??", "??", "??", "??", "??", "??", "??", "??", "??", "??", "??", "??", "??", "??", "??", "??", "??", "??", "??", "??", "??"}
        topics = [w for w, _ in word_freq.most_common(10) if len(w) >= 2 and w not in stop_words][:5]

        if sentiment_score >= 70:
            summary = f"??????????{symbol} ????????????"
        elif sentiment_score <= 30:
            summary = f"??????????{symbol} ????????????????????"
        else:
            summary = f"?????????{symbol} ?????????????????????"

        return {
            "symbol": symbol,
            "score": sentiment_score,
            "trend": trend,
            "topics": topics if topics else ["????", "????", "????"],
            "summary": summary,
            "news_count": len(headlines),
            "avg_confidence": round(sum(s.abs() for s in individual_scores) / len(individual_scores), 2) if individual_scores else 0,
        }
    except Exception as exc:
        logger.error("??????: %s", exc)
        return {
            "symbol": symbol,
            "score": 50,
            "trend": [50] * 7,
            "topics": [],
            "summary": "??????",
            "news_count": 0,
            "avg_confidence": 0,
        }


@router.post("/chat/complete", summary="AI ???????")
def chat_complete(payload: ChatRequest) -> Dict[str, Any]:
    """?????? AI ????????"""
    message = payload.message
    conversation_id = payload.conversation_id
    mode = payload.mode

    # ???? AIService
    ai_svc = _ai_service()
    reply = ""
    if ai_svc and ai_svc.is_configured:
        try:
            system_prompt = _system_prompt_for_mode(mode)
            reply = ai_svc.chat(message, system_prompt=system_prompt)
        except Exception as e:
            logger.error("AIService chat failed, fallback: %s", e)

    # ????? ChatAgent
    if not reply:
        try:
            agent = _get_fallback_agent()
            reply = agent.chat(message, conversation_id=conversation_id, mode=mode)
        except Exception as e:
            logger.error("Fallback ChatAgent failed: %s", e)
            reply = f"AI ????: {e}"

    # ???????
    try:
        from stockquant.persistence.repository import save_chat_message
        db_url = None
        try:
            from stockquant.config import get_config
            db_url = get_config().database.url
        except Exception:
            pass
        if db_url:
            save_chat_message(engine_url=db_url, conversation_id=conversation_id, role="user", content=message)
            save_chat_message(engine_url=db_url, conversation_id=conversation_id, role="assistant", content=reply)
    except Exception:
        pass

    # ????
    history = []
    if db_url:
        try:
            from stockquant.persistence.repository import get_chat_messages
            raw = get_chat_messages(db_url, conversation_id, limit=10)
            history = raw
        except Exception:
            pass
    elif ai_svc:
        history = ai_svc.get_history(limit=10)

    return {
        "conversation_id": conversation_id,
        "reply": reply,
        "history": history[-10:],
    }


@router.post("/chat", summary="AI ????")
def chat_stream(payload: ChatRequest) -> StreamingResponse:
    """?????SSE ????"""
    message = payload.message
    conversation_id = payload.conversation_id
    mode = payload.mode
    system_prompt = _system_prompt_for_mode(mode)

    def event_generator():
        reply = ""
        # ???????
        try:
            from stockquant.persistence.repository import save_chat_message
            db_url = None
            try:
                from stockquant.config import get_config
                db_url = get_config().database.url
            except Exception:
                pass
            if db_url:
                save_chat_message(engine_url=db_url, conversation_id=conversation_id, role="user", content=message)
        except Exception:
            pass

        # ???? AIService
        ai_svc = _ai_service()
        if ai_svc and ai_svc.is_configured:
            try:
                full_reply = ai_svc.chat(message, system_prompt=system_prompt)
                reply = full_reply
                # ?? yield SSE ??
                if full_reply:
                    evt = {"type": "token", "content": full_reply}
                    yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
            except Exception as e:
                error_msg = f"AI ????: {e}"
                evt = {"type": "error", "content": error_msg}
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                reply = error_msg
        else:
            # ????? ChatAgent
            try:
                agent = _get_fallback_agent()
                for chunk in agent.chat_stream(message, conversation_id, mode=mode):
                    evt = {"type": "token", "content": chunk}
                    yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                    reply += chunk
            except Exception as e:
                error_msg = f"AI ????: {e}"
                evt = {"type": "error", "content": error_msg}
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                reply = error_msg

        # ???????
        if reply:
            try:
                if db_url:
                    save_chat_message(engine_url=db_url, conversation_id=conversation_id, role="assistant", content=reply)
            except Exception:
                pass

        evt = {"type": "done"}
        yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations", summary="??????")
def list_conversations() -> Dict[str, Any]:
    """???????????????"""
    try:
        from stockquant.persistence.repository import list_chat_sessions
        db_url = None
        try:
            from stockquant.config import get_config
            db_url = get_config().database.url
        except Exception:
            pass
        if db_url:
            sessions = list_chat_sessions(db_url)
            return {"conversations": sessions}
    except Exception as e:
        logger.warning("list_conversations failed: %s", e)
    return {"conversations": []}


@router.get("/conversation/{conversation_id}", summary="??????")
def get_conversation(conversation_id: str, limit: int = 50) -> Dict[str, Any]:
    """???????????????"""
    try:
        from stockquant.persistence.repository import get_chat_messages
        db_url = None
        try:
            from stockquant.config import get_config
            db_url = get_config().database.url
        except Exception:
            pass
        if db_url:
            messages = get_chat_messages(db_url, conversation_id, limit=limit)
            return {"conversation_id": conversation_id, "messages": messages}
    except Exception as e:
        logger.warning("get_conversation failed: %s", e)
    return {"conversation_id": conversation_id, "messages": []}


@router.post("/conversation/{conversation_id}/message", summary="??????")
def save_message(
    conversation_id: str,
    payload: SaveMessageRequest,
) -> Dict[str, Any]:
    """?????????????? AI ????"""
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
            from stockquant.persistence.repository import save_chat_message
            msg_id = save_chat_message(
                engine_url=db_url,
                conversation_id=conversation_id,
                role=role,
                content=content,
            )
            return {"saved": True, "id": msg_id}
    except Exception as e:
        logger.error("save_message failed: %s", e)
    return {"saved": False, "id": None}


@router.delete("/conversation/{conversation_id}", summary="????")
def clear_conversation(conversation_id: str) -> Dict[str, Any]:
    """?????????????"""
    try:
        db_url = None
        try:
            from stockquant.config import get_config
            db_url = get_config().database.url
        except Exception:
            pass
        if db_url:
            from stockquant.persistence.repository import delete_chat_messages
            delete_chat_messages(db_url, conversation_id)
            return {"cleared": True}
    except Exception as e:
        logger.error("clear_conversation failed: %s", e)
    return {"cleared": False}


@router.post("/tools/query_market_data", summary="??????")
def tool_query_market_data(symbol: str, days: int = 30) -> Dict[str, Any]:
    """???????"""
    try:
        from stockquant.ai.chat_tools import query_market_data
        result = query_market_data(symbol, days=days)
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        logger.error("query_market_data failed: %s", e)
        return {"error": str(e), "data": []}


@router.post("/tools/search_news", summary="????")
def tool_search_news(symbol: str, limit: int = 5) -> Dict[str, Any]:
    """?????"""
    try:
        from stockquant.ai.chat_tools import search_news
        result = search_news(symbol, limit=limit)
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        logger.error("search_news failed: %s", e)
        return {"error": str(e), "news": []}


@router.post("/analyze-backtest/{backtest_id}", summary="AI ??????")
async def analyze_backtest(backtest_id: str):
    """AI ?????? ? ???????????? / ????? / Alpha?? / ??????"""
    from stockquant.api.routers.backtest import _tasks

    task = _tasks.get(backtest_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"???? {backtest_id} ???")

    metrics = task.get("metrics", {})
    strategy_name = task.get("strategy_name", "????")

    if task.get("status") == "completed" and metrics:
        # ???? AIService
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
            prompt = f"""?????????????? JSON ???? markdown ????

??: {strategy_name}
????: {json.dumps(key_metrics, ensure_ascii=False, default=str)}

????? JSON:
{{
  "summary": "2-3?????????",
  "overfitRisk": "????????? / ? / ?????",
  "alphaDecomposition": "Alpha???????????????",
  "suggestions": ["??????????1", "????2", "????3"]
}}

?????? JSON????????"""
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
                logger.warning("AI ?????????????: %s", e)

    # Fallback: ????
    ann_ret = metrics.get("Annualized Return", 0)
    max_dd = metrics.get("Max Drawdown", 0)
    sharpe = metrics.get("Sharpe Ratio", 0)
    win_rate = metrics.get("Win Rate", 0)
    total_trades = metrics.get("Total Trades", 0)

    if total_trades and total_trades < 30:
        overfit = "? ? ???????<30?????????????????"
    elif sharpe and sharpe > 3:
        overfit = "? ? ???????????????????????"
    elif total_trades and total_trades > 200 and (sharpe or 0) < 1.5:
        overfit = "? ? ???????????"
    else:
        overfit = "? ? ????????????"

    alpha = metrics.get("Alpha", 0)
    beta = metrics.get("Beta", 0)
    if alpha and alpha > 0:
        alpha_src = f"?? Alpha ? {alpha*100:.1f}%????????????????? Beta ???Beta={beta:.2f}?"
    elif alpha and alpha < 0:
        alpha_src = f"?? Alpha ? {alpha*100:.1f}%??????????????"
    else:
        alpha_src = "Alpha ?????????"

    suggestions = []
    if max_dd and abs(max_dd) > 0.2:
        suggestions.append("????????????????????????")
    if win_rate and win_rate < 0.4 and total_trades and total_trades > 20:
        suggestions.append("?????????????????????????????")
    if sharpe and sharpe < 0.5:
        suggestions.append("????????????????????????")
    if total_trades and total_trades < 30:
        suggestions.append("????????????????????????")
    if not suggestions:
        suggestions = [
            "???????????????????????????",
            "????????????????????",
            "??????????????????????",
        ]

    return {
        "insight": {
            "summary": (
                f"???{strategy_name}?????? {ann_ret*100:.1f}%?"
                f"????{abs(max_dd)*100:.1f}%?????{sharpe:.2f}?"
                f"?? {win_rate*100:.1f}%?? {total_trades} ????"
            ),
            "overfitRisk": overfit,
            "alphaDecomposition": alpha_src,
            "suggestions": suggestions[:5],
        }
    }


@router.post("/strategy/generate", summary="AI ??????")
async def generate_strategy(payload: GenerateStrategyRequest) -> Dict[str, Any]:
    """AI ???????????
    
    ???:
        description: str ? ??????????
        strategy_type: str ? ????????: "trend", "mean_reversion", "momentum", "arbitrage"
    """
    description = payload.description
    strategy_type = payload.strategy_type
    
    if not description.strip():
        raise HTTPException(status_code=400, detail="????????")
    
    # ???? AIService
    ai_svc = _ai_service()
    reply = ""
    if ai_svc and ai_svc.is_configured:
        try:
            prompt = f"""????????????????????????????????????????? Python??? Cerebro ????

????: {description}
????: {strategy_type}

??:
1. ??? CerebroStrategy ??
2. ?? on_bar(candle) ??????K?
3. ????/??????
4. ??????????
5. ????????
6. ????????????

????? Python ??????????"""
            reply = ai_svc.chat(prompt)
        except Exception as e:
            logger.error("Strategy generation failed: %s", e)

    # ????? ChatAgent
    if not reply:
        try:
            agent = _get_fallback_agent()
            prompt = f"""????????????????????????????????????????? Python??? Cerebro ????

????: {description}
????: {strategy_type}

??:
1. ??? CerebroStrategy ??
2. ?? on_bar(candle) ??????K?
3. ????/??????
4. ??????????
5. ????????
6. ????????????

????? Python ??????????"""
            reply = agent.chat(prompt, conversation_id="strategy_gen")
        except Exception as e:
            logger.error("Strategy generation fallback failed: %s", e)
            reply = ""
    
    # ?????
    code = reply
    if "```python" in reply:
        code = reply.split("```python")[1].split("```")[0].strip()
    elif "```" in reply:
        code = reply.split("```")[1].split("```")[0].strip()
    
    strategy_names = {
        "trend": "??????",
        "mean_reversion": "??????", 
        "momentum": "????",
        "arbitrage": "????",
    }
    
    return {
        "code": code,
        "name": strategy_names.get(strategy_type, "?????"),
        "description": description,
    }
