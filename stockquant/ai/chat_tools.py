# -*- coding: utf-8 -*-
"""F028 对话专用工具 — 图表生成、数据查询、策略执行触发、回测解读、盯盘管理"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import numpy as np

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
        if df is None or len(df) == 0:
            return json.dumps({"error": f"未找到 {symbol} 的数据"}, ensure_ascii=False)

        closes = df["close"].iloc[-days:] if len(df) > days else df["close"]
        volumes = df["volume"].iloc[-days:] if len(df) > days else df["volume"]

        stats: Dict[str, Any] = {
            "symbol": symbol,
            "days": days,
            "latest_close": float(closes.iloc[-1]) if len(closes) > 0 else None,
            "high": float(closes.max()) if len(closes) > 0 else None,
            "low": float(closes.min()) if len(closes) > 0 else None,
            "avg_volume": int(volumes.mean()) if len(volumes) > 0 else None,
            "data_points": len(closes),
        }
        if len(closes) >= 2:
            first_close = float(closes.iloc[0])
            last_close = float(closes.iloc[-1])
            stats["period_return"] = round((last_close - first_close) / first_close * 100, 2)

        return json.dumps(stats, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@tool
def generate_chart_json(
    symbol: str,
    chart_type: str = "line",
    title: str = "",
) -> str:
    """生成图表配置 JSON（供前端渲染）。

    Parameters
    ----------
    symbol : str
        股票代码
    chart_type : str
        图表类型: line/bar/ema
    title : str
        图表标题
    """
    try:
        from stockquant.data import DataFetcherManager
        fetcher = DataFetcherManager()
        df = fetcher.fetch(symbol, days=60)
        if df is None or len(df) == 0:
            return json.dumps({"error": f"未找到 {symbol} 的数据"}, ensure_ascii=False)

        closes = df["close"].values
        n = len(closes)

        data_points = []
        for i in range(n):
            data_points.append({
                "index": i,
                "value": float(closes[i]),
                "date": i,  # placeholder
            })

        # 添加 EMA 线
        ema10 = []
        if n >= 10:
            result = np.zeros(n)
            result[0] = closes[0]
            mult = 2.0 / 11
            for i in range(1, n):
                result[i] = (closes[i] - result[i-1]) * mult + result[i-1]
            for i in range(n):
                data_points[i]["ema10"] = float(result[i])

        return json.dumps({
            "type": chart_type,
            "symbol": symbol,
            "title": title or f"{symbol} 图表",
            "data": data_points,
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
        策略 Python 代码
    """
    try:
        import ast
        import tempfile
        import os

        # 语法检查
        try:
            ast.parse(strategy_code)
        except SyntaxError as e:
            return json.dumps({
                "error": f"策略代码语法错误: {e}",
                "status": "rejected",
            }, ensure_ascii=False)

        # 写入临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(strategy_code)
            temp_path = f.name

        try:
            # 执行回测
            from stockquant.engine.cerebro import Cerebro
            from stockquant.data.providers.csv_feed import CSVFeed

            cerebro = Cerebro()
            try:
                cerebro.add_data(CSVFeed())
            except Exception:
                pass  # CSV 无数据是预期行为

            # 加载临时策略模块
            import importlib.util
            spec = importlib.util.spec_from_file_location("strategy_module", temp_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            # 查找策略类
            for name, obj in mod.__dict__.items():
                if isinstance(obj, type) and name != "BaseStrategy":
                    try:
                        cerebro.add_strategy(obj)
                    except Exception:
                        pass

            results = cerebro.run()

            return json.dumps({
                "status": "completed",
                "symbol": symbol,
                "results_count": len(results),
                "message": f"回测完成，{len(results)} 个策略结果",
            }, ensure_ascii=False)
        finally:
            os.unlink(temp_path)

    except Exception as exc:
        return json.dumps({
            "error": str(exc),
            "status": "failed",
        }, ensure_ascii=False)


@tool
def interpret_backtest(backtest_id: str) -> str:
    """解读历史回测结果。

    Parameters
    ----------
    backtest_id : str
        回测任务 ID
    """
    try:
        from stockquant.ai.backtest_agent import BacktestAgent
        from stockquant.persistence.repository import get_backtest

        result = get_backtest(backtest_id)
        if result is None:
            return json.dumps({"error": f"未找到回测任务 {backtest_id}"}, ensure_ascii=False)

        agent = BacktestAgent()
        analysis = agent.analyze(result)

        return json.dumps({
            "summary": analysis.summary if hasattr(analysis, 'summary') else str(analysis),
            "issues": analysis.issues if hasattr(analysis, 'issues') else [],
            "suggestions": analysis.suggestions if hasattr(analysis, 'suggestions') else [],
        }, ensure_ascii=False)
    except ImportError:
        return json.dumps({"error": "BacktestAgent 或 persistence 模块未安装"}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@tool
def start_monitoring(symbol: str, alert_conditions: Optional[List[str]] = None) -> str:
    """启动盯盘监控 — 将股票加入自选监控列表。

    Parameters
    ----------
    symbol : str
        要监控的股票代码，如 "sh600519"
    alert_conditions : list[str] | None
        可选的告警条件列表，如 ["RSI>70", "MACD金叉"]
    """
    try:
        from stockquant.api.routers.monitor import _watchlist, add_to_watchlist

        # 注册到自选监控列表
        if symbol not in _watchlist:
            add_to_watchlist([symbol])

        # 获取当前股票数据
        stock_data: Dict[str, Any] = {}
        try:
            from stockquant.data import DataFetcherManager
            fetcher = DataFetcherManager()
            df = fetcher.fetch(symbol, days=5)
            if df is not None and len(df) > 0:
                closes = df["close"]
                volumes = df["volume"]
                stock_data = {
                    "latest_close": float(closes.iloc[-1]),
                    "high_5d": float(closes.max()),
                    "low_5d": float(closes.min()),
                    "avg_volume": int(volumes.mean()),
                }
                if len(closes) >= 2:
                    stock_data["change_pct"] = round(
                        (float(closes.iloc[-1]) - float(closes.iloc[-2])) / float(closes.iloc[-2]) * 100, 2
                    )
        except Exception:
            logger.debug("Failed to fetch stock data for %s", symbol)

        result: Dict[str, Any] = {
            "status": "monitoring_started",
            "symbol": symbol,
            "watchlist": list(_watchlist),
            "alert_conditions": alert_conditions or [],
            "stock_data": stock_data,
            "message": f"已将 {symbol} 加入监控列表",
        }
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@tool
def check_monitor_status(symbol: Optional[str] = None) -> str:
    """查询盯盘监控状态。

    Parameters
    ----------
    symbol : str | None
        股票代码。若提供则返回该股票的监控状态；否则返回整体监控摘要。
    """
    try:
        from stockquant.api.routers.monitor import _watchlist, _alerts, _get_agent

        if symbol is not None:
            # 单只股票监控状态
            in_watchlist = symbol in _watchlist
            symbol_alerts = [a for a in _alerts if a.symbol == symbol] if _alerts else []

            # 获取最新价格
            price_data: Dict[str, Any] = {}
            try:
                from stockquant.data import DataFetcherManager
                fetcher = DataFetcherManager()
                df = fetcher.fetch(symbol, days=5)
                if df is not None and len(df) > 0:
                    closes = df["close"]
                    price_data = {
                        "latest_close": float(closes.iloc[-1]),
                        "change_pct": round(
                            (float(closes.iloc[-1]) - float(closes.iloc[-2])) / float(closes.iloc[-2]) * 100, 2
                        ) if len(closes) >= 2 else None,
                    }
            except Exception:
                logger.debug("Failed to fetch price for %s", symbol)

            # 获取情绪数据
            sentiment_data: Dict[str, Any] = {}
            try:
                agent = _get_agent()
                if agent._news_searcher:
                    news_items = agent._news_searcher.search(symbol, days=3, max_results=5)
                    if news_items:
                        import numpy as np
                        sentiments = [n.sentiment for n in news_items]
                        sentiment_data = {
                            "avg_sentiment": round(float(np.mean(sentiments)), 3),
                            "news_count": len(news_items),
                        }
            except Exception:
                logger.debug("Failed to fetch sentiment for %s", symbol)

            result: Dict[str, Any] = {
                "symbol": symbol,
                "in_watchlist": in_watchlist,
                "alerts": [
                    {
                        "direction": a.direction,
                        "reason": a.reason,
                        "confidence": a.confidence,
                        "signal_type": a.signal_type,
                        "timestamp": a.timestamp.isoformat() if hasattr(a.timestamp, "isoformat") else str(a.timestamp),
                    }
                    for a in symbol_alerts[-10:]
                ],
                "price": price_data,
                "sentiment": sentiment_data,
            }
            return json.dumps(result, ensure_ascii=False)
        else:
            # 整体监控摘要
            agent = _get_agent()
            result = {
                "watchlist": list(_watchlist),
                "watchlist_count": len(_watchlist),
                "total_alerts": len(_alerts) if _alerts else 0,
                "running": getattr(agent, "_running", False),
                "recent_alerts": [
                    {
                        "symbol": a.symbol,
                        "direction": a.direction,
                        "reason": a.reason,
                        "confidence": a.confidence,
                        "timestamp": a.timestamp.isoformat() if hasattr(a.timestamp, "isoformat") else str(a.timestamp),
                    }
                    for a in (_alerts[-5:] if _alerts else [])
                ],
            }
            return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@tool
def stop_monitoring(symbol: str) -> str:
    """停止盯盘监控 — 将股票从自选监控列表移除。

    Parameters
    ----------
    symbol : str
        要移除监控的股票代码
    """
    try:
        from stockquant.api.routers.monitor import _watchlist, remove_from_watchlist

        if symbol in _watchlist:
            remove_from_watchlist([symbol])
            return json.dumps({
                "status": "monitoring_stopped",
                "symbol": symbol,
                "watchlist": list(_watchlist),
                "message": f"已将 {symbol} 从监控列表移除",
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "status": "not_in_watchlist",
                "symbol": symbol,
                "watchlist": list(_watchlist),
                "message": f"{symbol} 不在监控列表中",
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
                "published_at": item.published_at.isoformat() if hasattr(item, 'published_at') and item.published_at else None,
            })
        return json.dumps({"news": results, "count": len(results)}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
