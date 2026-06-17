# -*- coding: utf-8 -*-
"""F029 设置管理路由 — 配置读写/白名单

已实现 JSON 文件持久化 + .env 环境变量联动 + API Key 加密。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from stockquant.api.deps import get_admin_user, get_current_user

logger = logging.getLogger("stockquant.api.settings")

router = APIRouter()

# ====================================================================
# 持久化配置
# ====================================================================

_SETTINGS_DIR = Path.home() / ".stockquant"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"


def _load_settings_from_file() -> dict:
    """从 JSON 文件加载配置覆盖"""
    if _SETTINGS_FILE.exists():
        try:
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载配置文件失败: {e}")
    return {}


def _save_settings_to_file():
    """保存配置到 JSON 文件"""
    try:
        _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(_settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")


# ====================================================================
# 敏感密钥列表 & 加密（Task 4.5）
# ====================================================================

_SENSITIVE_KEYS = {
    "ai.api_key", "ai.api_base",
    "evolution.api_key", "evolution.api_base",
    "data_provider.api_key",
    "trading.qmt_password", "trading.xtp_password", "trading.ctp_password",
    "trading.admin_token",
    "notifications.smtp_password",
    "openai_api_key", "anthropic_api_key",
    "redis_password",
    "jwt_secret_key",
}

# 加密模块：try/except 兼容未安装 cryptography 的情况
try:
    from cryptography.fernet import Fernet

    def _get_encryption_key() -> bytes:
        """获取加密密钥，从环境变量读取或生成后保存"""
        key_env = os.environ.get("SQ_ENCRYPTION_KEY")
        if key_env:
            return key_env.encode()
        key_file = Path.home() / ".stockquant" / ".encryption_key"
        if key_file.exists():
            return key_file.read_bytes()
        # 生成新密钥
        key = Fernet.generate_key()
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(key)
        return key

    _fernet = Fernet(_get_encryption_key())

    def _encrypt_value(value: str) -> str:
        """加密敏感值"""
        if not value:
            return ""
        return _fernet.encrypt(value.encode()).decode()

    def _decrypt_value(value: str) -> str:
        """解密敏感值，失败时返回原始值（兼容旧明文数据）"""
        if not value:
            return ""
        try:
            return _fernet.decrypt(value.encode()).decode()
        except Exception:
            return value

    def _mask_value(value: str) -> str:
        """掩码处理，保留前后各4位"""
        if len(value) <= 8:
            return "****"
        return value[:4] + "****" + value[-4:]

    _encryption_available = True

except ImportError:
    _encryption_available = False

    def _encrypt_value(value: str) -> str:
        if not value:
            return ""
        logger.warning("cryptography 未安装，跳过加密")
        return value

    def _decrypt_value(value: str) -> str:
        return value

    def _mask_value(value: str) -> str:
        if len(value) <= 8:
            return "****"
        return value[:4] + "****" + value[-4:]


# ====================================================================
# 默认配置（从 .env 环境变量读取，Task 4.9）
# ====================================================================

# .env 环境变量名映射表（Task 4.7 补全）
_ENV_VAR_MAP: Dict[str, str] = {
    # === 交易配置 ===
    "trading.broker": "TRADING_BROKER",
    "trading.admin_token": "TRADING_ADMIN_TOKEN",
    "trading.qmt_path": "QMT_PATH",
    "trading.qmt_account": "QMT_ACCOUNT",
    "trading.qmt_password": "QMT_PASSWORD",
    "trading.xtp_user": "XTP_USER",
    "trading.xtp_password": "XTP_PASSWORD",
    "trading.xtp_app_id": "XTP_APP_ID",
    "trading.ctp_user": "CTP_USER",
    "trading.ctp_password": "CTP_PASSWORD",
    "trading.ctp_broker_id": "CTP_BROKER_ID",
    "trading.auto_confirm": "",  # 无对应环境变量
    
    # === 数据源配置 ===
    "data_provider.source": "DATA_PROVIDER_SOURCE",
    "data_provider.api_key": "DATA_PROVIDER_API_KEY",
    "data_provider.api_url": "DATA_PROVIDER_API_URL",
    "data_provider.alphafeed_key": "ALPHAFEED_KEY",
    "data_provider.tushare_token": "TUSHARE_TOKEN",
    "data_provider.akshare_proxy": "AKSHARE_PROXY",
    "data_provider.jqdata_mobile": "JQDATA_MOBILE",
    "data_provider.jqdata_password": "JQDATA_PASSWORD",
    
    # === 回测配置 ===
    "backtest.default_cash": "BACKTEST_DEFAULT_CASH",
    "backtest.commission_type": "",
    "backtest.slippage_type": "",
    
    # === 风控配置 ===
    "risk.max_position_pct": "RISK_MAX_POSITION_PCT",
    "risk.max_daily_loss_pct": "RISK_MAX_DAILY_LOSS_PCT",
    "risk.max_drawdown_pct": "RISK_MAX_DRAWDOWN_PCT",
    
    # === AI/LLM 配置 ===
    "ai.provider": "AI_PROVIDER",
    "ai.model": "OPENAI_MODEL",
    "ai.api_key": "OPENAI_API_KEY",
    "ai.api_base": "OPENAI_API_BASE",
    "ai.temperature": "OPENAI_TEMPERATURE",
    "ai.max_tokens": "OPENAI_MAX_TOKENS",
    "ai.anthropic_api_key": "ANTHROPIC_API_KEY",
    "ai.anthropic_model": "ANTHROPIC_MODEL",
    "ai.anthropic_api_base": "ANTHROPIC_API_BASE",
    # 本地 LLM 配置（NFR008 Tick 级 <200ms）
    "ai.local_llm.enabled": "LOCAL_LLM_ENABLED",
    "ai.local_llm.backend": "LOCAL_LLM_BACKEND",
    "ai.local_llm.model": "LOCAL_LLM_MODEL",
    "ai.local_llm.base_url": "LOCAL_LLM_BASE_URL",
    
    # === 进化 LLM 配置 ===
    "evolution.enabled": "",
    "evolution.llm_provider": "EVO_LLM_PROVIDER",
    "evolution.llm_model": "EVO_LLM_MODEL",
    "evolution.anthropic_model": "EVO_ANTHROPIC_MODEL",
    "evolution.api_key": "EVO_LLM_API_KEY",
    "evolution.api_base": "EVO_LLM_API_BASE",
    "evolution.llm_temperature": "EVO_LLM_TEMPERATURE",
    "evolution.max_tokens": "EVO_LLM_MAX_TOKENS",
    "evolution.llm_retry": "",
    
    # === 通知配置 ===
    "notification.dingtalk_webhook": "DINGTALK_WEBHOOK_URL",
    "notification.wechat_webhook": "WECHAT_WEBHOOK_URL",
    "notification.email_smtp": "SMTP_HOST",
    "notification.email_smtp_port": "SMTP_PORT",
    "notification.email_user": "SMTP_USER",
    "notification.email_password": "SMTP_PASSWORD",
    "notification.email_from": "EMAIL_FROM",
    "notification.email_to": "EMAIL_TO",
    "notification.telegram_bot_token": "TELEGRAM_BOT_TOKEN",
    "notification.telegram_chat_id": "TELEGRAM_CHAT_ID",
    "notification.discord_webhook": "DISCORD_WEBHOOK_URL",
    "notification.pushplus_token": "PUSHPLUS_TOKEN",
    "notification.feishu_webhook": "FEISHU_WEBHOOK_URL",
    "notification.serverchan_key": "SERVERCHAN_KEY",
    "notification.custom_webhook_url": "CUSTOM_WEBHOOK_URL",
    
    # === 系统配置 ===
    "system.log_level": "LOG_LEVEL",
    "system.data_dir": "CACHE_DIR",
    "system.log_dir": "LOG_DIR",
    "system.host": "HOST",
    "system.port": "PORT",
    "system.debug": "DEBUG",
    "system.workers": "WORKERS",
    
    # === 数据库配置 ===
    "database.url": "DATABASE_URL",
    "database.pool_size": "DATABASE_POOL_SIZE",
    "database.max_overflow": "DATABASE_MAX_OVERFLOW",
    "database.pool_timeout": "DATABASE_POOL_TIMEOUT",
    "database.echo": "DATABASE_ECHO",
    
    # === Redis 配置 ===
    "redis.url": "REDIS_URL",
    "redis.password": "REDIS_PASSWORD",
    "redis.db": "REDIS_DB",
    "redis.pool_size": "REDIS_POOL_SIZE",
    "redis.socket_timeout": "REDIS_SOCKET_TIMEOUT",
    
    # === Kafka 配置 ===
    "kafka.enabled": "KAFKA_ENABLED",
    "kafka.bootstrap_servers": "KAFKA_BOOTSTRAP_SERVERS",
    "kafka.consumer_group": "KAFKA_CONSUMER_GROUP",
    "kafka.signal_topic": "KAFKA_SIGNAL_TOPIC",
    "kafka.alert_topic": "KAFKA_ALERT_TOPIC",
    "kafka.security_protocol": "KAFKA_SECURITY_PROTOCOL",
    
    # === 信号配置 ===
    "signal.dedup_cooldown_sec": "SIGNAL_DEDUP_COOLDOWN_SEC",
    "signal.dedup_db_check_pending": "SIGNAL_DEDUP_DB_CHECK_PENDING",
    "signal.dedup_audit_rejected": "SIGNAL_DEDUP_AUDIT_REJECTED",
    
    # === 调度/决策配置 ===
    "decision.mode": "DECISION_MODE",
    "monitor.scan_interval": "MONITOR_SCAN_INTERVAL",
    "monitor.alert_threshold": "ALERT_THRESHOLD",
    
    # === 缓存配置 ===
    "cache.ttl_hours": "CACHE_TTL_HOURS",
    "cache.max_size_mb": "CACHE_MAX_SIZE_MB",
    
    # === JWT 配置 ===
    "jwt.secret_key": "JWT_SECRET_KEY",
    "jwt.algorithm": "JWT_ALGORITHM",
    "jwt.expire_minutes": "JWT_EXPIRE_MINUTES",
    
    # === 速率限制配置 ===
    "rate_limit.global": "RATE_LIMIT",

    # === AI 信息管线配置 ===
    "ai_pipeline.collect_interval_sec": "AI_PIPELINE_COLLECT_INTERVAL_SEC",
    "ai_pipeline.denoise_source_credit_threshold": "AI_PIPELINE_DENOISE_SOURCE_CREDIT_THRESHOLD",
    "ai_pipeline.denoise_timeliness_hours": "AI_PIPELINE_DENOISE_TIMELINESS_HOURS",
    "ai_pipeline.summarize_period": "AI_PIPELINE_SUMMARIZE_PERIOD",
    "ai_pipeline.elevate_min_articles": "AI_PIPELINE_ELEVATE_MIN_ARTICLES",
    "ai_pipeline.hallucination_mode": "AI_PIPELINE_HALLUCINATION_MODE",
    "ai_pipeline.memory_l2_retention_days": "AI_PIPELINE_MEMORY_L2_RETENTION_DAYS",
    "ai_pipeline.memory_l3_confidence_threshold": "AI_PIPELINE_MEMORY_L3_CONFIDENCE_THRESHOLD",
    "ai_pipeline.local_rule_engine_enabled": "LOCAL_RULE_ENGINE_ENABLED",
    "ai_pipeline.sentiment_method": "SENTIMENT_METHOD",
}

# 类型定义（用于 GET /settings/sources 返回，Task 4.7 补全）
_SCHEMA: Dict[str, type] = {
    # === 交易配置 ===
    "trading.broker": str,
    "trading.admin_token": str,
    "trading.qmt_path": str,
    "trading.qmt_account": str,
    "trading.qmt_password": str,
    "trading.xtp_user": str,
    "trading.xtp_password": str,
    "trading.xtp_app_id": str,
    "trading.ctp_user": str,
    "trading.ctp_password": str,
    "trading.ctp_broker_id": str,
    "trading.auto_confirm": bool,
    
    # === 数据源配置 ===
    "data_provider.source": str,
    "data_provider.api_key": str,
    "data_provider.api_url": str,
    "data_provider.alphafeed_key": str,
    "data_provider.tushare_token": str,
    "data_provider.akshare_proxy": str,
    "data_provider.jqdata_mobile": str,
    "data_provider.jqdata_password": str,
    
    # === 回测配置 ===
    "backtest.default_cash": int,
    "backtest.commission_type": str,
    "backtest.slippage_type": str,
    
    # === 风控配置 ===
    "risk.max_position_pct": float,
    "risk.max_daily_loss_pct": float,
    "risk.max_drawdown_pct": float,
    
    # === AI/LLM 配置 ===
    "ai.provider": str,
    "ai.model": str,
    "ai.api_key": str,
    "ai.api_base": str,
    "ai.temperature": float,
    "ai.max_tokens": int,
    "ai.anthropic_api_key": str,
    "ai.anthropic_model": str,
    "ai.anthropic_api_base": str,
    # 本地 LLM 配置（NFR008）
    "ai.local_llm.enabled": bool,
    "ai.local_llm.backend": str,
    "ai.local_llm.model": str,
    "ai.local_llm.base_url": str,
    
    # === 进化 LLM 配置 ===
    "evolution.enabled": bool,
    "evolution.llm_provider": str,
    "evolution.llm_model": str,
    "evolution.anthropic_model": str,
    "evolution.api_key": str,
    "evolution.api_base": str,
    "evolution.llm_temperature": float,
    "evolution.max_tokens": int,
    "evolution.llm_retry": int,
    
    # === 通知配置 ===
    "notification.dingtalk_webhook": str,
    "notification.wechat_webhook": str,
    "notification.email_smtp": str,
    "notification.email_smtp_port": str,
    "notification.email_user": str,
    "notification.email_password": str,
    "notification.email_from": str,
    "notification.email_to": str,
    "notification.telegram_bot_token": str,
    "notification.telegram_chat_id": str,
    "notification.discord_webhook": str,
    "notification.pushplus_token": str,
    "notification.feishu_webhook": str,
    "notification.serverchan_key": str,
    "notification.custom_webhook_url": str,
    
    # === 系统配置 ===
    "system.log_level": str,
    "system.data_dir": str,
    "system.log_dir": str,
    "system.host": str,
    "system.port": int,
    "system.debug": bool,
    "system.workers": int,
    
    # === 数据库配置 ===
    "database.url": str,
    "database.pool_size": int,
    "database.max_overflow": int,
    "database.pool_timeout": int,
    "database.echo": bool,
    
    # === Redis 配置 ===
    "redis.url": str,
    "redis.password": str,
    "redis.db": int,
    "redis.pool_size": int,
    "redis.socket_timeout": int,
    
    # === Kafka 配置 ===
    "kafka.enabled": bool,
    "kafka.bootstrap_servers": str,
    "kafka.consumer_group": str,
    "kafka.signal_topic": str,
    "kafka.alert_topic": str,
    "kafka.security_protocol": str,
    
    # === 信号配置 ===
    "signal.dedup_cooldown_sec": int,
    "signal.dedup_db_check_pending": bool,
    "signal.dedup_audit_rejected": bool,
    
    # === 调度/决策配置 ===
    "decision.mode": str,
    "monitor.scan_interval": int,
    "monitor.alert_threshold": float,
    
    # === 缓存配置 ===
    "cache.ttl_hours": int,
    "cache.max_size_mb": int,
    
    # === JWT 配置 ===
    "jwt.secret_key": str,
    "jwt.algorithm": str,
    "jwt.expire_minutes": int,
    
    # === 速率限制配置 ===
    "rate_limit.global": str,

    # === AI 信息管线配置 ===
    "ai_pipeline.collect_interval_sec": int,
    "ai_pipeline.denoise_source_credit_threshold": float,
    "ai_pipeline.denoise_timeliness_hours": int,
    "ai_pipeline.summarize_period": str,
    "ai_pipeline.elevate_min_articles": int,
    "ai_pipeline.hallucination_mode": str,
    "ai_pipeline.memory_l2_retention_days": int,
    "ai_pipeline.memory_l3_confidence_threshold": float,
    "ai_pipeline.local_rule_engine_enabled": bool,
    "ai_pipeline.sentiment_method": str,
}


def _env_key_for_setting(key: str) -> str:
    """将配置 key 映射到 .env 环境变量名"""
    return _ENV_VAR_MAP.get(key, "")


# 从 .env 和代码默认值构建默认配置（Task 4.7 补全）
def _build_default_settings() -> Dict[str, Any]:
    defaults: Dict[str, Any] = {}
    
    # === 交易配置 ===
    defaults["trading.broker"] = os.environ.get("TRADING_BROKER", "paper")
    defaults["trading.admin_token"] = os.environ.get("TRADING_ADMIN_TOKEN", "")
    defaults["trading.qmt_path"] = os.environ.get("QMT_PATH", "")
    defaults["trading.qmt_account"] = os.environ.get("QMT_ACCOUNT", "")
    defaults["trading.qmt_password"] = os.environ.get("QMT_PASSWORD", "")
    defaults["trading.xtp_user"] = os.environ.get("XTP_USER", "")
    defaults["trading.xtp_password"] = os.environ.get("XTP_PASSWORD", "")
    defaults["trading.xtp_app_id"] = os.environ.get("XTP_APP_ID", "")
    defaults["trading.ctp_user"] = os.environ.get("CTP_USER", "")
    defaults["trading.ctp_password"] = os.environ.get("CTP_PASSWORD", "")
    defaults["trading.ctp_broker_id"] = os.environ.get("CTP_BROKER_ID", "")
    defaults["trading.auto_confirm"] = False
    
    # === 数据源配置 ===
    defaults["data_provider.source"] = os.environ.get("DATA_PROVIDER_SOURCE", "alphafeed")
    defaults["data_provider.api_key"] = os.environ.get("DATA_PROVIDER_API_KEY", "")
    defaults["data_provider.api_url"] = os.environ.get("DATA_PROVIDER_API_URL", "")
    defaults["data_provider.alphafeed_key"] = os.environ.get("ALPHAFEED_KEY", "")
    defaults["data_provider.tushare_token"] = os.environ.get("TUSHARE_TOKEN", "")
    defaults["data_provider.akshare_proxy"] = os.environ.get("AKSHARE_PROXY", "")
    defaults["data_provider.jqdata_mobile"] = os.environ.get("JQDATA_MOBILE", "")
    defaults["data_provider.jqdata_password"] = os.environ.get("JQDATA_PASSWORD", "")
    
    # === 回测配置 ===
    defaults["backtest.default_cash"] = int(os.environ.get("BACKTEST_DEFAULT_CASH", "1000000"))
    defaults["backtest.commission_type"] = "ashare"
    defaults["backtest.slippage_type"] = "none"
    
    # === 风控配置 ===
    defaults["risk.max_position_pct"] = float(os.environ.get("RISK_MAX_POSITION_PCT", "0.3"))
    defaults["risk.max_daily_loss_pct"] = float(os.environ.get("RISK_MAX_DAILY_LOSS_PCT", "0.05"))
    defaults["risk.max_drawdown_pct"] = float(os.environ.get("RISK_MAX_DRAWDOWN_PCT", "0.15"))
    
    # === AI/LLM 配置 ===
    defaults["ai.provider"] = os.environ.get("OPENAI_PROVIDER", "openai")
    defaults["ai.model"] = os.environ.get("OPENAI_MODEL", "gpt-4o")
    defaults["ai.api_key"] = os.environ.get("OPENAI_API_KEY", "")
    defaults["ai.api_base"] = os.environ.get("OPENAI_API_BASE", "")
    defaults["ai.temperature"] = float(os.environ.get("OPENAI_TEMPERATURE", "0.7"))
    defaults["ai.max_tokens"] = int(os.environ.get("OPENAI_MAX_TOKENS", "4096"))
    defaults["ai.anthropic_api_key"] = os.environ.get("ANTHROPIC_API_KEY", "")
    defaults["ai.anthropic_model"] = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    defaults["ai.anthropic_api_base"] = os.environ.get("ANTHROPIC_API_BASE", "")
    # 本地 LLM 配置（NFR008）
    defaults["ai.local_llm.enabled"] = os.environ.get("LOCAL_LLM_ENABLED", "false").lower() in ("true", "1", "yes")
    defaults["ai.local_llm.backend"] = os.environ.get("LOCAL_LLM_BACKEND", "ollama")
    defaults["ai.local_llm.model"] = os.environ.get("LOCAL_LLM_MODEL", "qwen2.5-7b-instruct")
    defaults["ai.local_llm.base_url"] = os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434")
    
    # === 进化 LLM 配置 ===
    defaults["evolution.enabled"] = False
    defaults["evolution.llm_provider"] = os.environ.get("EVO_LLM_PROVIDER", "openai")
    defaults["evolution.llm_model"] = os.environ.get("EVO_LLM_MODEL", "gpt-4o")
    defaults["evolution.anthropic_model"] = os.environ.get("EVO_ANTHROPIC_MODEL", "claude-3-opus")
    defaults["evolution.api_key"] = os.environ.get("EVO_LLM_API_KEY", "")
    defaults["evolution.api_base"] = os.environ.get("EVO_LLM_API_BASE", "")
    defaults["evolution.llm_temperature"] = float(os.environ.get("EVO_LLM_TEMPERATURE", "0.5"))
    defaults["evolution.max_tokens"] = int(os.environ.get("EVO_LLM_MAX_TOKENS", "4096"))
    defaults["evolution.llm_retry"] = int(os.environ.get("EVO_LLM_RETRY", "3"))
    
    # === 通知配置 ===
    defaults["notification.dingtalk_webhook"] = os.environ.get("DINGTALK_WEBHOOK_URL", "")
    defaults["notification.wechat_webhook"] = os.environ.get("WECHAT_WEBHOOK_URL", "")
    defaults["notification.email_smtp"] = os.environ.get("SMTP_HOST", "")
    defaults["notification.email_smtp_port"] = os.environ.get("SMTP_PORT", "465")
    defaults["notification.email_user"] = os.environ.get("SMTP_USER", "")
    defaults["notification.email_password"] = os.environ.get("SMTP_PASSWORD", "")
    defaults["notification.email_from"] = os.environ.get("EMAIL_FROM", "")
    defaults["notification.email_to"] = os.environ.get("EMAIL_TO", "")
    defaults["notification.telegram_bot_token"] = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    defaults["notification.telegram_chat_id"] = os.environ.get("TELEGRAM_CHAT_ID", "")
    defaults["notification.discord_webhook"] = os.environ.get("DISCORD_WEBHOOK_URL", "")
    defaults["notification.pushplus_token"] = os.environ.get("PUSHPLUS_TOKEN", "")
    defaults["notification.feishu_webhook"] = os.environ.get("FEISHU_WEBHOOK_URL", "")
    defaults["notification.serverchan_key"] = os.environ.get("SERVERCHAN_KEY", "")
    defaults["notification.custom_webhook_url"] = os.environ.get("CUSTOM_WEBHOOK_URL", "")
    
    # === 系统配置 ===
    defaults["system.log_level"] = os.environ.get("LOG_LEVEL", "INFO")
    defaults["system.data_dir"] = os.environ.get("CACHE_DIR", os.environ.get("DATA_DIR", "~/.stockquant/data"))
    defaults["system.log_dir"] = os.environ.get("LOG_DIR", "./log")
    defaults["system.host"] = os.environ.get("HOST", "0.0.0.0")
    defaults["system.port"] = int(os.environ.get("PORT", "8000"))
    defaults["system.debug"] = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")
    defaults["system.workers"] = int(os.environ.get("WORKERS", "4"))
    
    # === 数据库配置 ===
    defaults["database.url"] = os.environ.get("DATABASE_URL", "sqlite:///./stockquant.db")
    defaults["database.pool_size"] = int(os.environ.get("DATABASE_POOL_SIZE", "10"))
    defaults["database.max_overflow"] = int(os.environ.get("DATABASE_MAX_OVERFLOW", "20"))
    defaults["database.pool_timeout"] = int(os.environ.get("DATABASE_POOL_TIMEOUT", "30"))
    defaults["database.echo"] = os.environ.get("DATABASE_ECHO", "false").lower() in ("true", "1", "yes")
    
    # === Redis 配置 ===
    defaults["redis.url"] = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    defaults["redis.password"] = os.environ.get("REDIS_PASSWORD", "")
    defaults["redis.db"] = int(os.environ.get("REDIS_DB", "0"))
    defaults["redis.pool_size"] = int(os.environ.get("REDIS_POOL_SIZE", "10"))
    defaults["redis.socket_timeout"] = int(os.environ.get("REDIS_SOCKET_TIMEOUT", "5"))
    
    # === Kafka 配置 ===
    defaults["kafka.enabled"] = os.environ.get("KAFKA_ENABLED", "false").lower() in ("true", "1", "yes")
    defaults["kafka.bootstrap_servers"] = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    defaults["kafka.consumer_group"] = os.environ.get("KAFKA_CONSUMER_GROUP", "stockquant-consumers")
    defaults["kafka.signal_topic"] = os.environ.get("KAFKA_SIGNAL_TOPIC", "stock-signal")
    defaults["kafka.alert_topic"] = os.environ.get("KAFKA_ALERT_TOPIC", "stock-alert")
    defaults["kafka.security_protocol"] = os.environ.get("KAFKA_SECURITY_PROTOCOL", "plaintext")
    
    # === 信号配置 ===
    defaults["signal.dedup_cooldown_sec"] = int(os.environ.get("SIGNAL_DEDUP_COOLDOWN_SEC", "14400"))
    defaults["signal.dedup_db_check_pending"] = os.environ.get("SIGNAL_DEDUP_DB_CHECK_PENDING", "true").lower() in ("true", "1", "yes")
    defaults["signal.dedup_audit_rejected"] = os.environ.get("SIGNAL_DEDUP_AUDIT_REJECTED", "true").lower() in ("true", "1", "yes")
    
    # === 调度/决策配置 ===
    defaults["decision.mode"] = os.environ.get("DECISION_MODE", "manual")
    defaults["monitor.scan_interval"] = int(os.environ.get("MONITOR_SCAN_INTERVAL", "30"))
    defaults["monitor.alert_threshold"] = float(os.environ.get("ALERT_THRESHOLD", "3.0"))
    
    # === 缓存配置 ===
    defaults["cache.ttl_hours"] = int(os.environ.get("CACHE_TTL_HOURS", "24"))
    defaults["cache.max_size_mb"] = int(os.environ.get("CACHE_MAX_SIZE_MB", "1024"))
    
    # === JWT 配置 ===
    defaults["jwt.secret_key"] = os.environ.get("JWT_SECRET_KEY", "stockquant-dev-secret-change-in-prod")
    defaults["jwt.algorithm"] = os.environ.get("JWT_ALGORITHM", "HS256")
    defaults["jwt.expire_minutes"] = int(os.environ.get("JWT_EXPIRE_MINUTES", "1440"))
    
    # === 速率限制配置 ===
    defaults["rate_limit.global"] = os.environ.get("RATE_LIMIT", "100 per minute")

    # === AI 信息管线配置 ===
    defaults["ai_pipeline.collect_interval_sec"] = int(os.environ.get("AI_PIPELINE_COLLECT_INTERVAL_SEC", "300"))
    defaults["ai_pipeline.denoise_source_credit_threshold"] = float(os.environ.get("AI_PIPELINE_DENOISE_SOURCE_CREDIT_THRESHOLD", "0.5"))
    defaults["ai_pipeline.denoise_timeliness_hours"] = int(os.environ.get("AI_PIPELINE_DENOISE_TIMELINESS_HOURS", "24"))
    defaults["ai_pipeline.summarize_period"] = os.environ.get("AI_PIPELINE_SUMMARIZE_PERIOD", "daily")
    defaults["ai_pipeline.elevate_min_articles"] = int(os.environ.get("AI_PIPELINE_ELEVATE_MIN_ARTICLES", "3"))
    defaults["ai_pipeline.hallucination_mode"] = os.environ.get("AI_PIPELINE_HALLUCINATION_MODE", "standard")
    defaults["ai_pipeline.memory_l2_retention_days"] = int(os.environ.get("AI_PIPELINE_MEMORY_L2_RETENTION_DAYS", "30"))
    defaults["ai_pipeline.memory_l3_confidence_threshold"] = float(os.environ.get("AI_PIPELINE_MEMORY_L3_CONFIDENCE_THRESHOLD", "0.15"))
    defaults["ai_pipeline.local_rule_engine_enabled"] = os.environ.get("LOCAL_RULE_ENGINE_ENABLED", "true").lower() in ("true", "1", "yes")
    defaults["ai_pipeline.sentiment_method"] = os.environ.get("SENTIMENT_METHOD", "auto")

    return defaults


# 记录每个配置项的来源（default / env / saved）
_settings_sources: Dict[str, str] = {}


def _track_sources():
    """追踪每个配置项的来源"""
    defaults = _build_default_settings()
    file_settings = _load_settings_from_file()
    for key in defaults:
        env_var = _env_key_for_setting(key)
        env_val = os.environ.get(env_var) if env_var else None
        if env_val is not None and str(env_val) != str(defaults.get(key, "")):
            _settings_sources[key] = "env"
        elif key in file_settings:
            _settings_sources[key] = "saved"
        else:
            _settings_sources[key] = "default"


_DEFAULT_SETTINGS = _build_default_settings()

# 合并：默认值 + 文件覆盖
_raw_file = _load_settings_from_file()
_settings: Dict[str, Any] = {**_DEFAULT_SETTINGS, **_raw_file}
_admin_whitelist: list[str] = ["admin"]

# 初始化来源追踪
_track_sources()


# ====================================================================
# 辅助函数
# ====================================================================

def _safe_value(key: str, value: Any) -> Any:
    """安全取值：对敏感 key 做掩码处理"""
    if key in _SENSITIVE_KEYS and isinstance(value, str) and len(value) > 8:
        return _mask_value(value)
    return value


# ====================================================================
# 端点
# ====================================================================

@router.get("/settings", response_model=dict, summary="获取全部配置")
async def get_settings():
    """获取所有配置项，敏感值掩码显示，附带来源信息"""
    result = {}
    for key, value in _settings.items():
        result[key] = {
            "value": _safe_value(key, value),
            "source": _settings_sources.get(key, "default"),
        }
    return {"settings": result}


@router.post("/settings/save", response_model=dict, summary="保存配置")
async def save_settings(payload: dict, _user=Depends(get_admin_user)):
    """批量保存配置 — 持久化到 JSON 文件，敏感值自动加密"""
    updates = payload.get("settings", {})
    if not isinstance(updates, dict):
        raise HTTPException(status_code=400, detail="settings 必须是字典")

    for key, value in updates.items():
        # 敏感值加密
        if key in _SENSITIVE_KEYS and isinstance(value, str) and value and _encryption_available:
            value = _encrypt_value(value)
        _settings[key] = value
        _settings_sources[key] = "saved"

    _save_settings_to_file()
    logger.info(f"配置已更新并持久化: {list(updates.keys())}")
    return {"success": True, "updated_keys": list(updates.keys())}


@router.delete("/settings/{key:path}", response_model=dict, summary="恢复配置默认值")
async def reset_setting(key: str, _user=Depends(get_admin_user)):
    """恢复单个配置项为 .env 值（优先）或代码默认值"""
    if key not in _DEFAULT_SETTINGS:
        raise HTTPException(status_code=404, detail=f"配置项 {key} 不存在")

    # 优先使用 .env 中的值，其次使用代码默认值
    env_var = _env_key_for_setting(key)
    env_val = os.environ.get(env_var) if env_var else None
    if env_val is not None:
        # 敏感值在存储时需要加密
        if key in _SENSITIVE_KEYS and _encryption_available:
            _settings[key] = _encrypt_value(env_val)
        else:
            _settings[key] = env_val
        _settings_sources[key] = "env"
    else:
        _settings[key] = _DEFAULT_SETTINGS[key]
        _settings_sources[key] = "default"

    _save_settings_to_file()
    return {"success": True, "key": key, "value": _safe_value(key, _settings[key])}


@router.get("/settings/sources", response_model=dict, summary="获取所有可配置项")
async def get_settings_sources(_user=Depends(get_current_user)):
    """获取所有可配置项及其默认值和来源"""
    defaults = _build_default_settings()
    return {
        "sources": {
            key: {
                "default": defaults.get(key, _DEFAULT_SETTINGS.get(key, "")),
                "type": _SCHEMA.get(key, type(defaults.get(key, ""))),
            }
            for key in _SCHEMA
        }
    }


@router.get("/settings/whitelist", summary="获取管理员白名单")
async def get_whitelist():
    """获取管理员白名单"""
    return {"whitelist": _admin_whitelist}


@router.get("/settings/health", summary="配置健康状态")
async def get_settings_health(_user=Depends(get_current_user)):
    """获取配置健康状态"""
    overridden_keys = set(_settings.keys()) - set(_DEFAULT_SETTINGS.keys())
    env_sourced = []
    for key in _DEFAULT_SETTINGS:
        env_var = _env_key_for_setting(key)
        if env_var and os.environ.get(env_var):
            env_sourced.append(key)

    return {
        "total_keys": len(_settings),
        "default_keys": len(_DEFAULT_SETTINGS),
        "overridden_keys": list(overridden_keys),
        "env_sourced_keys": env_sourced,
        "settings_file": str(_SETTINGS_FILE),
        "settings_file_exists": _SETTINGS_FILE.exists(),
        "encryption_available": _encryption_available,
    }
