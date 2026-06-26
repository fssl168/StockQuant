# -*- coding: utf-8 -*-
"""新闻采集器 — AlphaFeed 优先 / AkShare 降级 / 直连 API 增强（东方财富/雪球/财联社）"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseCollector, RawInfoItem

logger = logging.getLogger("stockquant.ai.collectors.news")

# AlphaFeed SDK 可选导入
_ALPHAFEED_AVAILABLE = False
try:
    from alphafeed import AlphaFeed as _AlphaFeedClient
    _ALPHAFEED_AVAILABLE = True
except ImportError:
    pass

# HTTP 客户端 + 重试库可选导入（用于直连数据源反爬）
_HTTP_AVAILABLE = False
try:
    import httpx
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )
    _HTTP_AVAILABLE = True
except ImportError:
    pass


class NewsCollector(BaseCollector):
    """新闻采集器 — AlphaFeed 优先，AkShare 降级"""

    def __init__(self, api_key: str = "") -> None:
        super().__init__(name="news")
        self._api_key = api_key or os.environ.get("ALPHAFEED_KEY", "")
        self._client = None
        if _ALPHAFEED_AVAILABLE and self._api_key:
            try:
                self._client = _AlphaFeedClient(api_key=self._api_key)
            except Exception as e:
                logger.warning("AlphaFeed 客户端初始化失败: %s", e)

        # 反爬配置 — 请求头伪装 / 频率限制 / 超时
        self._ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        self._min_interval: float = 1.5  # 同一数据源最小请求间隔(秒)
        self._http_timeout: float = 12.0
        self._last_request: Dict[str, float] = {}
        # 雪球 token（可选，从环境变量读取；缺失时自动获取匿名 token）
        self._xq_token: str = os.environ.get("XQ_A_TOKEN", "")

    async def collect(self, symbol: str = "", limit: int = 20) -> List[RawInfoItem]:
        """采集新闻信息

        优先使用 AlphaFeed，不可用时降级为多源聚合（AkShare + 东方财富快讯 /
        雪球热帖 / 财联社电报直连 API）。
        """
        if self._client:
            items = await self._collect_alphafeed(symbol, limit)
            if items:
                return items
            # C4: AlphaFeed 无数据时记录降级原因
            logger.info(
                "AlphaFeed 无数据（symbol=%s），降级为 AkShare 多源聚合",
                symbol or "<market>",
            )
        else:
            # C4: SDK 未启用，记录原因
            if not _ALPHAFEED_AVAILABLE:
                logger.debug("AlphaFeed SDK 未安装，使用 AkShare 多源聚合")
            elif not self._api_key:
                logger.debug("AlphaFeed API Key 未配置，使用 AkShare 多源聚合")

        return await self._collect_akshare(symbol, limit)

    async def _collect_alphafeed(self, symbol: str, limit: int) -> List[RawInfoItem]:
        """从 AlphaFeed 采集新闻（C4: 真实 SDK 调用）

        调用 AlphaFeed SDK 的新闻接口：
        - 如果 SDK 可用且 API Key 配置正确，返回结构化新闻列表
        - 如果 SDK 接口签名与预期不符，捕获异常后降级
        """
        if not self._client:
            return []
        try:
            # AlphaFeed SDK 调用尝试：
            # 新版 SDK：client.get_news(symbol=..., limit=...)
            # 旧版 SDK：client.news(symbol, limit)
            try:
                result = self._client.get_news(symbol=symbol, limit=limit)
            except (AttributeError, TypeError):
                # 尝试旧版 API
                result = self._client.news(symbol, limit)

            # 解析结果
            if not result:
                return []
            items: List[RawInfoItem] = []
            # 兼容 dict 列表 / 对象列表
            iterable = result.get("data", result) if isinstance(result, dict) else result
            for entry in iterable[:limit] if hasattr(iterable, '__iter__') else []:
                if isinstance(entry, dict):
                    title = str(entry.get("title", ""))
                    content = str(entry.get("content", entry.get("summary", "")))
                    url = str(entry.get("url", ""))
                    source = str(entry.get("source", "alphafeed"))
                    ts = entry.get("published_at") or entry.get("timestamp")
                    published = datetime.fromisoformat(str(ts)) if ts else datetime.now()
                    items.append(RawInfoItem(
                        url=url, source=source, title=title,
                        content=content, symbol=symbol,
                        timestamp=published,
                    ))
            logger.info("AlphaFeed 采集: %d 条", len(items))
            return items
        except Exception as exc:
            logger.warning("AlphaFeed 新闻采集失败: %s", exc)
            return []

    async def _collect_akshare(self, symbol: str, limit: int) -> List[RawInfoItem]:
        """从 AkShare 采集新闻（降级路径）"""
        all_items: List[RawInfoItem] = []
        seen_titles: set = set()
        source_status: Dict[str, str] = {}

        # 数据源 1: 东方财富个股新闻
        em_items = await self._collect_eastmoney(symbol, limit)
        if em_items:
            source_status["stock_news_em"] = f"ok({len(em_items)})"
        else:
            source_status["stock_news_em"] = "empty/failed"
        for item in em_items:
            if item.title not in seen_titles:
                seen_titles.add(item.title)
                all_items.append(item)

        # 数据源 2: CCTV 新闻
        if len(all_items) < limit:
            cctv_items = await self._collect_cctv(limit - len(all_items))
            if cctv_items:
                source_status["news_cctv"] = f"ok({len(cctv_items)})"
            else:
                source_status["news_cctv"] = "empty/failed"
            for item in cctv_items:
                if item.title not in seen_titles:
                    seen_titles.add(item.title)
                    all_items.append(item)

        # 数据源 3: 全球财经快讯
        if len(all_items) < limit:
            global_items = await self._collect_global(limit - len(all_items))
            if global_items:
                source_status["stock_info_global_em"] = f"ok({len(global_items)})"
            else:
                source_status["stock_info_global_em"] = "empty/failed"
            for item in global_items:
                if item.title not in seen_titles:
                    seen_titles.add(item.title)
                    all_items.append(item)

        # 数据源 4: 东方财富 7x24 快讯（直连 API）
        if len(all_items) < limit:
            em_express_items = await self._collect_eastmoney_express(limit - len(all_items))
            if em_express_items:
                source_status["eastmoney_express"] = f"ok({len(em_express_items)})"
            else:
                source_status["eastmoney_express"] = "empty/failed"
            for item in em_express_items:
                if item.title not in seen_titles:
                    seen_titles.add(item.title)
                    all_items.append(item)

        # 数据源 5: 雪球热帖（直连 API）
        if len(all_items) < limit:
            xq_items = await self._collect_xueqiu(limit - len(all_items))
            if xq_items:
                source_status["xueqiu_hot"] = f"ok({len(xq_items)})"
            else:
                source_status["xueqiu_hot"] = "empty/failed"
            for item in xq_items:
                if item.title not in seen_titles:
                    seen_titles.add(item.title)
                    all_items.append(item)

        # 数据源 6: 财联社电报（直连 API）
        if len(all_items) < limit:
            cls_items = await self._collect_cls(limit - len(all_items))
            if cls_items:
                source_status["cls_telegraph"] = f"ok({len(cls_items)})"
            else:
                source_status["cls_telegraph"] = "empty/failed"
            for item in cls_items:
                if item.title not in seen_titles:
                    seen_titles.add(item.title)
                    all_items.append(item)

        logger.info("新闻采集完成: %s, 去重后 %d 条", source_status, len(all_items))
        if not all_items:
            failed_sources = [k for k, v in source_status.items() if "failed" in v or "empty" in v]
            if failed_sources:
                logger.warning("所有数据源采集失败: %s", failed_sources)
            else:
                logger.debug("新闻采集完成但无匹配结果（数据源返回空）: %s", source_status)
        return all_items[:limit]

    async def _collect_eastmoney(self, symbol: str, limit: int) -> List[RawInfoItem]:
        """从东方财富采集个股新闻"""
        try:
            import akshare as ak

            df = ak.stock_news_em(symbol=symbol) if symbol else ak.stock_news_em(symbol="sh600519")
            items = []
            for _, row in df.head(limit).iterrows():
                title = str(row.get("新闻标题", row.get("title", "")))
                content = str(row.get("新闻内容", row.get("content", "")))
                url = str(row.get("新闻链接", row.get("url", "")))
                items.append(self._create_item(
                    url=url, source="eastmoney", title=title,
                    content=content, symbol=symbol,
                ))
            logger.debug("东方财富新闻采集: %d 条", len(items))
            return items
        except ImportError:
            logger.warning("akshare 未安装，跳过东方财富新闻采集")
            return []
        except Exception as exc:
            logger.warning("东方财富新闻采集失败: %s", exc)
            return []

    async def _collect_cctv(self, limit: int) -> List[RawInfoItem]:
        """从 CCTV 采集新闻"""
        try:
            import akshare as ak

            df = ak.news_cctv(date="")
            items = []
            for _, row in df.head(limit).iterrows():
                title = str(row.get("标题", row.get("title", "")))
                content = str(row.get("内容", row.get("content", "")))
                url = str(row.get("链接", row.get("url", "")))
                items.append(self._create_item(
                    url=url, source="cctv", title=title,
                    content=content,
                ))
            logger.debug("CCTV 新闻采集: %d 条", len(items))
            return items
        except ImportError:
            logger.warning("akshare 未安装，跳过 CCTV 新闻采集")
            return []
        except Exception as exc:
            logger.warning("CCTV 新闻采集失败: %s", exc)
            return []

    async def _collect_global(self, limit: int) -> List[RawInfoItem]:
        """从全球财经快讯采集新闻"""
        try:
            import akshare as ak

            df = ak.stock_info_global_em()
            items = []
            for _, row in df.head(limit).iterrows():
                title = str(row.get("标题", row.get("新闻标题", "")))
                content = str(row.get("内容", row.get("新闻内容", "")))
                url = str(row.get("链接", row.get("新闻链接", "")))
                items.append(self._create_item(
                    url=url, source="global_em", title=title,
                    content=content,
                ))
            logger.debug("全球财经快讯采集: %d 条", len(items))
            return items
        except ImportError:
            logger.warning("akshare 未安装，跳过全球财经快讯采集")
            return []
        except Exception as exc:
            logger.warning("全球财经快讯采集失败: %s", exc)
            return []

    # ------------------------------------------------------------------
    # 直连 API 数据源 — 东方财富快讯 / 雪球热帖 / 财联社电报
    # 反爬：请求头伪装 + 频率限制 + 指数退避重试
    # ------------------------------------------------------------------

    async def _rate_limit(self, source: str) -> None:
        """频率限制：同一数据源两次请求间保持最小间隔。"""
        if self._min_interval <= 0:
            return
        last = self._last_request.get(source, 0.0)
        elapsed = time.monotonic() - last
        if 0.0 < elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_request[source] = time.monotonic()

    async def _http_get(
        self,
        url: str,
        *,
        source: str = "default",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        cookies: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
    ) -> Optional[Any]:
        """带反爬处理的 HTTP GET：频率限制 + 指数退避重试 + 请求头伪装。

        失败时记录日志并返回 ``None``，不抛出异常。
        """
        if not _HTTP_AVAILABLE:
            logger.warning("httpx/tenacity 未安装，跳过直连 HTTP 采集")
            return None

        merged: Dict[str, str] = {
            "User-Agent": self._ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        merged.update(headers or {})

        @retry(
            retry=retry_if_exception_type(
                (httpx.HTTPError, asyncio.TimeoutError, OSError)
            ),
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=1, max=8),
            reraise=True,
        )
        async def _do() -> Any:
            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                resp = await client.get(
                    url, headers=merged, params=params, cookies=cookies,
                )
                resp.raise_for_status()
                return resp

        await self._rate_limit(source)
        try:
            return await _do()
        except Exception as exc:
            logger.warning("HTTP 采集失败 [%s]: %s", source, exc)
            return None

    @staticmethod
    def _parse_jsonp(text: str) -> Any:
        """从 JSONP / var 包装响应中提取 JSON 对象；纯 JSON 直接解析。"""
        text = text.strip()
        # 纯 JSON
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        # callback({...}) / jQuery...({...})
        m = re.search(r"\((\{.*\})\)\s*;?\s*$", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # var name = {...};
        m = re.search(r"=\s*(\{.*\})\s*;?\s*$", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # 兜底：首个 {...}
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return None

    async def _collect_eastmoney_express(self, limit: int) -> List[RawInfoItem]:
        """从东方财富 7x24 快讯采集（直连 eastmoney API）。"""
        if not _HTTP_AVAILABLE:
            return []
        url = "https://np-listapi.eastmoney.com/comm/web/getFastNewsList"
        params = {
            "client": "web",
            "biz": "web_724",
            "fastColumn": "102",
            "sortEnd": "",
            "pageSize": str(limit),
            "pageNo": "1",
        }
        resp = await self._http_get(
            url,
            source="eastmoney_express",
            params=params,
            headers={"Referer": "https://kuaixun.eastmoney.com/"},
        )
        if resp is None:
            return []
        data = self._parse_jsonp(resp.text)
        if not isinstance(data, dict):
            logger.warning("东方财富快讯响应解析失败")
            return []
        container = data.get("data") if isinstance(data.get("data"), dict) else data
        rows = (
            container.get("list")
            or container.get("List")
            or data.get("list")
            or []
        )
        items: List[RawInfoItem] = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            title = str(
                row.get("Art_Title") or row.get("title")
                or row.get("ArtTitle") or row.get("Title") or ""
            )
            content = str(
                row.get("Art_Content") or row.get("content")
                or row.get("Content") or row.get("digest") or ""
            )
            show_time = str(row.get("Art_ShowTime") or row.get("showTime") or "")
            art_code = str(row.get("Art_Code") or row.get("art_code") or "")
            link = (
                f"https://kuaixun.eastmoney.com/news/{art_code}.html"
                if art_code else ""
            )
            full_title = title or "东方财富快讯"
            if show_time:
                full_title = f"[{show_time}] {full_title}"
            items.append(self._create_item(
                url=link, source="eastmoney_express",
                title=full_title, content=content,
            ))
        logger.debug("东方财富快讯采集: %d 条", len(items))
        return items

    async def _collect_xueqiu(self, limit: int) -> List[RawInfoItem]:
        """从雪球热帖采集（直连 xqapi）。

        雪球接口需要 ``xq_a_token`` cookie，缺失时自动访问首页获取匿名 token。
        """
        if not _HTTP_AVAILABLE:
            return []
        token = self._xq_token
        if not token:
            # 访问首页获取匿名 xq_a_token
            try:
                await self._rate_limit("xueqiu")
                async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                    home = await client.get(
                        "https://xueqiu.com/",
                        headers={
                            "User-Agent": self._ua,
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
                            "Accept-Language": "zh-CN,zh;q=0.9",
                        },
                    )
                    token = home.cookies.get("xq_a_token", "")
                    if token:
                        self._xq_token = token
            except Exception as exc:
                logger.warning("雪球 token 获取失败: %s", exc)

        cookies = {"xq_a_token": token} if token else None
        url = "https://xueqiu.com/v4/statuses/hot/listV2.json"
        params = {"since_id": "-1", "max_id": "-1", "size": str(limit)}
        resp = await self._http_get(
            url,
            source="xueqiu",
            params=params,
            cookies=cookies,
            headers={
                "Referer": "https://xueqiu.com/",
                "Origin": "https://xueqiu.com",
            },
        )
        if resp is None:
            return []
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            data = self._parse_jsonp(resp.text)
        if not isinstance(data, dict):
            logger.warning("雪球热帖响应解析失败")
            return []
        statuses = (
            data.get("statuses")
            or (data.get("data") or {}).get("statuses")
            or []
        )
        items: List[RawInfoItem] = []
        for st in statuses[:limit]:
            if not isinstance(st, dict):
                continue
            title = str(st.get("title") or st.get("description") or "")
            content = str(st.get("description") or st.get("text") or "")
            sid = st.get("id", "")
            user = st.get("user") or {}
            screen = user.get("screen_name", "")
            link = (
                f"https://xueqiu.com/{screen}/{sid}"
                if sid and screen else ""
            )
            # 雪球时间戳为毫秒
            ts_str = self._fmt_timestamp(st.get("created_at"), divisor=1000.0)
            full_title = title or "雪球热帖"
            if ts_str:
                full_title = f"[{ts_str}] {full_title}"
            items.append(self._create_item(
                url=link, source="xueqiu_hot",
                title=full_title, content=content,
            ))
        logger.debug("雪球热帖采集: %d 条", len(items))
        return items

    async def _collect_cls(self, limit: int) -> List[RawInfoItem]:
        """从财联社电报采集（直连 cls API）。"""
        if not _HTTP_AVAILABLE:
            return []
        url = "https://www.cls.cn/nodeapi/updateTelegraphList"
        params = {
            "app": "CailianpressWeb",
            "os": "web",
            "sv": "7.7.5",
            "rn": str(limit),
            "lastTime": "",
        }
        resp = await self._http_get(
            url,
            source="cls_telegraph",
            params=params,
            headers={
                "Referer": "https://www.cls.cn/telegraph",
                "Origin": "https://www.cls.cn",
            },
        )
        if resp is None:
            return []
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            data = self._parse_jsonp(resp.text)
        if not isinstance(data, dict):
            logger.warning("财联社电报响应解析失败")
            return []
        roll_data = (
            (data.get("data") or {}).get("roll_data")
            or data.get("roll_data")
            or []
        )
        items: List[RawInfoItem] = []
        for row in roll_data[:limit]:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "")
            content = str(row.get("content") or "")
            # 财联社电报正文可能含 HTML，简单清洗
            if content:
                content = re.sub(r"<[^>]+>", "", content)
            ts_str = self._fmt_timestamp(row.get("ctime"))
            link = str(row.get("shareurl") or row.get("url") or "")
            if not link and row.get("id"):
                link = f"https://www.cls.cn/detail/{row.get('id')}"
            full_title = title or "财联社电报"
            if ts_str:
                full_title = f"[{ts_str}] {full_title}"
            items.append(self._create_item(
                url=link, source="cls_telegraph",
                title=full_title, content=content,
            ))
        logger.debug("财联社电报采集: %d 条", len(items))
        return items

    @staticmethod
    def _fmt_timestamp(value: Any, divisor: float = 1.0) -> str:
        """将 Unix 时间戳格式化为 ``%Y-%m-%d %H:%M`` 字符串，失败返回空串。"""
        if not isinstance(value, (int, float)) or value <= 0:
            return ""
        try:
            return datetime.fromtimestamp(value / divisor).strftime("%Y-%m-%d %H:%M")
        except (OSError, ValueError, OverflowError):
            return ""
