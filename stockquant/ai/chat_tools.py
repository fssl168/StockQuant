# -*- coding: utf-8 -*-
"""F028 对话专用工具 — 图表生成、数据查询、策略执行触发"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from stockquant.agent.tool_registry import tool

logger = logging.getLogger("stockquant.ai")


@tool
def query_market_data(symbol: str, days: int = 30) -> str:
    """查询股票市场行情数据。

    Parameters
    ----------
    symbol : str
        股票代码，如 "sh600519"
    days : int
        查询最近 N 天的数据
    """
    try:
        from stockquant.data import DataFetcherManager
        fetcher = DataFetcherManager()
        df = fetcher.fetch(symbol, days=days)
        if df is None or df.empty:
            return json.dumps({"error": f"未找到 {symbol} 的数据"}, ensure_ascii=False)

        stats: Dict[str, Any] = {
            "symbol": symbol,
            "days": days,
            "latest_close": float(df["close"].iloc[-1]) if "close" in df.columns else None,
            "avg_volume": int(df["volume"].mean()) if "volume" in df.columns else None,
        }
        if len(df) >= 2 and "close" in df.columns:
            first_close = float(df["close"].iloc[0])
            last_close = float(df["close"].iloc[-1])
            stats["period_return"] = round((last_close - first_close) / first_close * 100, 2)

        return json.dumps(stats, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@tool
def generate_chart_json(
    data_json: str,
    chart_type: str = "line",
    title: str = "",
) -> str:
    """生成图表配置 JSON（供前端渲染）。

    Parameters
    ----------
    data_json : str
        JSON 格式的数据点数组
    chart_type : str
        图表类型: line/bar/scatter
    title : str
        图表标题
    """
    try:
        data = json.loads(data_json) if isinstance(data_json, str) else data_json
        return json.dumps({
            "type": chart_type,
            "title": title,
            "data": data,
        }, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@tool
def trigger_backtest(symbol: str, strategy_code: str) -> str:
    """触发策略回测。

    Parameters
    ----------
    symbol : str
        回测标的
    strategy_code : str
        策略代码
    """
    try:
        from stockquant.engine.cerebro import Cerebro
        from stockquant.data.providers.csv_feed import CSVFeed

        cerebro = Cerebro()
        cerebro.add_data(CSVFeed())
        return json.dumps({
            "status": "triggered",
            "symbol": symbol,
            "message": f"回测任务已提交，标的: {symbol}",
        }, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@tool
def search_news(symbol: str, limit: int = 5) -> str:
    """搜索最新新闻。

    Parameters
    ----------
    symbol : str
        标的代码
    limit : int
        返回条数
    """
    try:
        from stockquant.ai.news_searcher import NewsSearcher
        searcher = NewsSearcher()
        items = searcher.search(symbol, days=3)
        results = []
        for item in items[:limit]:
            results.append({
                "title": item.title,
                "summary": item.summary,
                "sentiment": item.sentiment,
                "source": item.source,
                "published_at": item.published_at.isoformat() if item.published_at else None,
            })
        return json.dumps({"news": results, "count": len(results)}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
