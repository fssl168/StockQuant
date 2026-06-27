# -*- coding: utf-8 -*-
"""F020 多源采集器 — 新闻 / 公告 / 社交 / 研报 / 财报 / 交易所直连

公共接口：
- BaseCollector: 采集器抽象基类
- NewsCollector: 新闻采集器（东方财富/雪球/财联社/CCTV/AlphaFeed）
- AnnouncementCollector: 公告采集器（巨潮资讯）
- SocialCollector: 社交媒体采集器（雪球/东财评论）
- ResearchCollector: 券商研报采集器（东方财富研报，写入 L3-Intermediate）
- FinancialCollector: 财务报表采集器（AkShare 财务指标，写入 L3-Deep）
- ExchangeCollector: 交易所直连采集器（上交所/深交所披露）
- SourceVerifier: 来源验证器（FAKE_SOURCES 黑名单 + 变更检测）
- CollectorAuditLog: 采集审计日志（操作可追溯）
- AuditEntry: 审计日志条目数据结构
"""
from .base import BaseCollector, RawInfoItem
from .news_collector import NewsCollector
from .announcement_collector import AnnouncementCollector
from .social_collector import SocialCollector
from .research_collector import ResearchCollector
from .financial_collector import FinancialCollector
from .exchange_collector import ExchangeCollector
from .verifier import SourceVerifier
from .audit_log import CollectorAuditLog, AuditEntry

__all__ = [
    # Base
    "BaseCollector", "RawInfoItem",
    # Collectors
    "NewsCollector", "AnnouncementCollector", "SocialCollector",
    "ResearchCollector", "FinancialCollector", "ExchangeCollector",
    # Verifier / Audit
    "SourceVerifier", "CollectorAuditLog", "AuditEntry",
]
