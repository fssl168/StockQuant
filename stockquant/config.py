# -*- coding: utf-8 -*-
"""配置加载模块 — 支持 YAML + .env + Settings API 三级配置优先级"""

from __future__ import annotations

import os
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

import logging

logger = logging.getLogger("stockquant.config")

# 配置文件路径
_CONFIG_FILE = Path.home() / ".stockquant" / "stockquant_config.yaml"

# 默认配置（Task 4.7 补全）
DEFAULT_CONFIG = {
    "ai": {
        "model": "gpt-4o",
        "api_key": "",
        "api_base": "",
        "lightweight_model": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 12000,
        "anthropic_model": "claude-sonnet-4-20250514",
        "anthropic_api_key": "",
        "anthropic_api_base": "",
    },
    "data": {
        "provider": "alphafeed",
        "cache_dir": str(Path.home() / ".stockquant" / "cache"),
        "alphafeed_key": "sk_00e405e9c9864062a7f9c0516b18b079",
    },
    "trading": {
        "broker": "paper",
        "commission_rate": 0.0003,
    },
    "monitor": {
        "scan_interval": 30,
        "alert_threshold": 3.0,
    },
    "notification": {
        "enabled_channels": ["websocket"],
    },
    "database": {
        #"url": "sqlite:///./stockquant.db",
        "url": "postgresql+asyncpg://fileclaw:fileclaw_secret@192.168.88.251:54322/autoquant",
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "echo": False,
    },
    "redis": {
        "url": "redis://192.168.88.251:6379/0",
        "password": "",
        "db": 0,
        "pool_size": 10,
        "socket_timeout": 5,
    },
    "kafka": {
        "enabled": False,
        "bootstrap_servers": "localhost:9092",
        "consumer_group": "stockquant-consumers",
        "signal_topic": "stock-signal",
        "alert_topic": "stock-alert",
        "security_protocol": "plaintext",
    },
    "signal": {
        "dedup_cooldown_sec": 14400,
        "dedup_db_check_pending": True,
        "dedup_audit_rejected": True,
    },
    "decision": {
        "mode": "manual",
    },
    "cache": {
        "ttl_hours": 24,
        "max_size_mb": 1024,
    },
    "jwt": {
        "secret_key": "stockquant-dev-secret-change-in-prod",
        "algorithm": "HS256",
        "expire_minutes": 1440,
    },
    "rate_limit": {
        "global": "100 per minute",
    },
    "ai_pipeline": {
        "collect_interval_sec": 300,
        "denoise_source_credit_threshold": 0.5,
        "denoise_timeliness_hours": 24,
        "summarize_period": "daily",
        "elevate_min_articles": 3,
        "hallucination_mode": "standard",
        "memory_l2_retention_days": 30,
        "memory_l3_confidence_threshold": 0.15,
        "local_rule_engine_enabled": True,
        "sentiment_method": "auto",
    },
    "system": {
        "log_level": "INFO",
        "data_dir": str(Path.home() / ".stockquant" / "data"),
        "log_dir": "./log",
        "host": "0.0.0.0",
        "port": 8000,
        "debug": False,
        "workers": 4,
    },
    "xtp": {
        "user": "",
        "password": "",
        "app_id": 0,
        "client_id": 0,
        "server_addr": "",
        "software_key": "",
    },
    "ctp": {
        "user": "",
        "password": "",
        "broker_id": "",
        "front_addr": "",
        "app_id": "",
    },
}


def load_config() -> dict:
    """加载 YAML 配置文件。

    如果 YAML 文件不存在或解析失败，返回空字典。
    YAML 配置会合并到默认配置中（覆盖默认值）。
    """
    if not _CONFIG_FILE.exists():
        logger.info("配置文件不存在: %s", _CONFIG_FILE)
        return {}

    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            if yaml:
                user_config = yaml.safe_load(f) or {}
            else:
                # 如果没安装 PyYAML，返回空配置
                logger.warning("PyYAML 未安装，跳过 YAML 配置加载")
                return {}

        # 递归合并
        merged = _merge_config(DEFAULT_CONFIG, user_config)
        logger.info("YAML 配置加载成功: %s", _CONFIG_FILE)
        return merged
    except Exception as exc:
        logger.warning("YAML 配置加载失败: %s", exc)
        return {}


def _merge_config(default: dict, override: dict) -> dict:
    """递归合并两个字典，override 优先"""
    result = default.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value
    return result


_config_cache: dict | None = None


def get_config() -> dict:
    """获取缓存的配置（合并 YAML + .env + 默认值）"""
    global _config_cache
    if _config_cache is None:
        # 始终以 DEFAULT_CONFIG 为基础，YAML 覆盖默认值
        config = _merge_config(DEFAULT_CONFIG, load_config())
        # .env 环境变量优先级高于 YAML 但低于 Settings API
        _apply_env_overrides(config)
        _config_cache = config
    return _config_cache


def reload_config():
    """重新加载配置（热更新）"""
    global _config_cache
    _config_cache = get_config()
    logger.info("配置已热更新")


def _apply_env_overrides(config: dict):
    """将环境变量合并到配置中（.env 优先级高于 YAML）"""
    env_mappings = {
        # AI 配置
        "OPENAI_MODEL": ("ai", "model"),
        "OPENAI_API_KEY": ("ai", "api_key"),
        "OPENAI_API_BASE": ("ai", "api_base"),
        "OPENAI_TEMPERATURE": ("ai", "temperature"),
        "OPENAI_MAX_TOKENS": ("ai", "max_tokens"),
        "AI_LIGHTWEIGHT_MODEL": ("ai", "lightweight_model"),
        "ANTHROPIC_MODEL": ("ai", "anthropic_model"),
        "ANTHROPIC_API_KEY": ("ai", "anthropic_api_key"),
        "ANTHROPIC_API_BASE": ("ai", "anthropic_api_base"),
        # 数据配置
        "DATA_PROVIDER_SOURCE": ("data", "provider"),
        "CACHE_DIR": ("data", "cache_dir"),
        # 交易配置
        "TRADING_BROKER": ("trading", "broker"),
        # 系统配置
        "LOG_LEVEL": ("system", "log_level"),
        "LOG_DIR": ("system", "log_dir"),
        "HOST": ("system", "host"),
        "PORT": ("system", "port"),
        "DEBUG": ("system", "debug"),
        "WORKERS": ("system", "workers"),
        # 数据库
        "DATABASE_URL": ("database", "url"),
        "DATABASE_POOL_SIZE": ("database", "pool_size"),
        "DATABASE_MAX_OVERFLOW": ("database", "max_overflow"),
        "DATABASE_POOL_TIMEOUT": ("database", "pool_timeout"),
        "DATABASE_ECHO": ("database", "echo"),
        # Redis
        "REDIS_URL": ("redis", "url"),
        "REDIS_PASSWORD": ("redis", "password"),
        "REDIS_DB": ("redis", "db"),
        "REDIS_POOL_SIZE": ("redis", "pool_size"),
        "REDIS_SOCKET_TIMEOUT": ("redis", "socket_timeout"),
        # Kafka
        "KAFKA_ENABLED": ("kafka", "false"),
        "KAFKA_BOOTSTRAP_SERVERS": ("kafka", "bootstrap_servers"),
        "KAFKA_CONSUMER_GROUP": ("kafka", "consumer_group"),
        "KAFKA_SIGNAL_TOPIC": ("kafka", "signal_topic"),
        "KAFKA_ALERT_TOPIC": ("kafka", "alert_topic"),
        "KAFKA_SECURITY_PROTOCOL": ("kafka", "security_protocol"),
        # 信号配置
        "SIGNAL_DEDUP_COOLDOWN_SEC": ("signal", "dedup_cooldown_sec"),
        "SIGNAL_DEDUP_DB_CHECK_PENDING": ("signal", "dedup_db_check_pending"),
        "SIGNAL_DEDUP_AUDIT_REJECTED": ("signal", "dedup_audit_rejected"),
        # 决策配置
        "DECISION_MODE": ("decision", "mode"),
        # 监控配置
        "MONITOR_SCAN_INTERVAL": ("monitor", "scan_interval"),
        "ALERT_THRESHOLD": ("monitor", "alert_threshold"),
        # 缓存配置
        "CACHE_TTL_HOURS": ("cache", "ttl_hours"),
        "CACHE_MAX_SIZE_MB": ("cache", "max_size_mb"),
        # JWT 配置
        "JWT_SECRET_KEY": ("jwt", "secret_key"),
        "JWT_ALGORITHM": ("jwt", "algorithm"),
        "JWT_EXPIRE_MINUTES": ("jwt", "expire_minutes"),
        # 速率限制
        "RATE_LIMIT": ("rate_limit", "global"),
        # AI 管线配置
        "AI_PIPELINE_COLLECT_INTERVAL_SEC": ("ai_pipeline", "collect_interval_sec"),
        "AI_PIPELINE_DENOISE_SOURCE_CREDIT_THRESHOLD": ("ai_pipeline", "denoise_source_credit_threshold"),
        "AI_PIPELINE_DENOISE_TIMELINESS_HOURS": ("ai_pipeline", "denoise_timeliness_hours"),
        "AI_PIPELINE_SUMMARIZE_PERIOD": ("ai_pipeline", "summarize_period"),
        "AI_PIPELINE_ELEVATE_MIN_ARTICLES": ("ai_pipeline", "elevate_min_articles"),
        "AI_PIPELINE_HALLUCINATION_MODE": ("ai_pipeline", "hallucination_mode"),
        "AI_PIPELINE_MEMORY_L2_RETENTION_DAYS": ("ai_pipeline", "memory_l2_retention_days"),
        "AI_PIPELINE_MEMORY_L3_CONFIDENCE_THRESHOLD": ("ai_pipeline", "memory_l3_confidence_threshold"),
        "LOCAL_RULE_ENGINE_ENABLED": ("ai_pipeline", "local_rule_engine_enabled"),
        "SENTIMENT_METHOD": ("ai_pipeline", "sentiment_method"),
        # XTP 券商配置
        "XTP_USER": ("xtp", "user"),
        "XTP_PASSWORD": ("xtp", "password"),
        "XTP_APP_ID": ("xtp", "app_id"),
        "XTP_CLIENT_ID": ("xtp", "client_id"),
        "XTP_SERVER_ADDR": ("xtp", "server_addr"),
        "XTP_SOFTWARE_KEY": ("xtp", "software_key"),
        # CTP 券商配置
        "CTP_USER": ("ctp", "user"),
        "CTP_PASSWORD": ("ctp", "password"),
        "CTP_BROKER_ID": ("ctp", "broker_id"),
        "CTP_FRONT_ADDR": ("ctp", "front_addr"),
        "CTP_APP_ID": ("ctp", "app_id"),
        # AlphaFeed 数据源配置
        "ALPHAFEED_KEY": ("data", "alphafeed_key"),
        "DATA_PROVIDER": ("data", "provider"),
    }
    for env_key, (section, key) in env_mappings.items():
        value = os.environ.get(env_key)
        if value is not None and section in config and key in config[section]:
            # 尝试类型转换
            original = config[section][key]
            if isinstance(original, bool):
                config[section][key] = value.lower() in ("true", "1", "yes")
            elif isinstance(original, int):
                try:
                    config[section][key] = int(value)
                except ValueError:
                    pass
            elif isinstance(original, float):
                try:
                    config[section][key] = float(value)
                except ValueError:
                    pass
            else:
                config[section][key] = value


# 启动时自动加载
get_config()
