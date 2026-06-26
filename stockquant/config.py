# -*- coding: utf-8 -*-
"""StockQuant Config Management - unified layer

Config priority: env vars > .env file > defaults
Supports AI providers, Redis, multi-source structured config
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings
import logging

logger = logging.getLogger("stockquant.config")


# ====================================================================
# Enum
# ====================================================================

class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    QWEN = "qwen"


class DataProvider(str, Enum):
    ALPHAFeed = "alphafeed"
    BAOSTOCK = "baostock"
    TUSHARE = "tushare"
    TDAXYZ = "tdx"
    CSV = "csv"
    SQLITE = "sqlite"


# ====================================================================
# Sub-settings
# ====================================================================

class DatabaseSettings(BaseModel):
    url: str = Field(default="sqlite:///./stockquant.db")
    pool_size: int = Field(default=10, ge=1, le=100)
    max_overflow: int = Field(default=20, ge=0, le=100)
    pool_timeout: int = Field(default=30, ge=1, le=300)
    echo: bool = Field(default=False)


class JWTSettings(BaseModel):
    secret_key: str = Field(default="dev-secret-key-change-in-production")
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=120)
    refresh_token_expire_days: int = Field(default=7)


class SystemSettings(BaseModel):
    log_level: str = Field(default="INFO")
    web_port: int = Field(default=8000, ge=1, le=65535)
    initial_capital: float = Field(default=1_000_000, ge=10000)
    commission_rate: float = Field(default=0.00025, ge=0, le=0.003)
    min_commission: float = Field(default=5, ge=0)
    stamp_tax_rate: float = Field(default=0.0005, ge=0, le=0.01)
    slippage: float = Field(default=0, ge=0)
    lot_size: int = Field(default=100, ge=100)
    price_limit_ratio: float = Field(default=0.1, ge=0.05, le=0.3)


class BaoStockSettings(BaseModel):
    enabled: bool = Field(default=True)


class TushareSettings(BaseModel):
    api_key: str = Field(default="")


class TdxSettings(BaseModel):
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=7709)


class CsvSettings(BaseModel):
    directory: str = Field(default="./data/csv")


class DuckDbSettings(BaseModel):
    path: str = Field(default="")


class DataProviderSettings(BaseModel):
    source: DataProvider = Field(default=DataProvider.ALPHAFeed)
    alphafeed_key: str = Field(default="")
    api_key: str = Field(default="")
    api_url: str = Field(default="")
    baostock: BaoStockSettings = Field(default_factory=BaoStockSettings)
    tushare: TushareSettings = Field(default_factory=TushareSettings)
    tdx: TdxSettings = Field(default_factory=TdxSettings)
    csv: CsvSettings = Field(default_factory=CsvSettings)
    duckdb: DuckDbSettings = Field(default_factory=DuckDbSettings)

    @model_validator(mode="before")
    @classmethod
    def _coerce_source(cls, data: Any) -> Any:
        if isinstance(data, dict):
            src = data.get("source")
            if isinstance(src, str):
                try:
                    data["source"] = DataProvider(src)
                except ValueError:
                    data["source"] = DataProvider.ALPHAFeed
        return data


class TradingSettings(BaseModel):
    mode: str = Field(default="simulator")


class AISettings(BaseModel):
    enabled: bool = Field(default=True)
    default_provider: LLMProvider = Field(default=LLMProvider.OPENAI)

    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o")
    openai_base_url: str = Field(default="")

    anthropic_api_key: str = Field(default="")
    anthropic_model: str = Field(default="claude-sonnet-4-20250514")
    anthropic_base_url: str = Field(default="")

    ollama_base_url: str = Field(default="http://127.0.0.1:11434")
    ollama_model: str = Field(default="llama3")

    qwen_api_key: str = Field(default="")
    qwen_model: str = Field(default="qwen-max")
    qwen_base_url: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1")

    max_tokens: int = Field(default=4096)
    temperature: float = Field(default=0.0)

    embedding_provider: str = Field(default="openai")
    embedding_model: str = Field(default="text-embedding-3-small")
    embedding_dim: int = Field(default=1536)

    def provider_config(self, provider: LLMProvider) -> Dict[str, Any]:
        cfg = {"provider": provider.value}
        if provider == LLMProvider.OPENAI:
            cfg["model"] = self.openai_model
            cfg["base_url"] = self.openai_base_url or None
        elif provider == LLMProvider.ANTHROPIC:
            cfg["model"] = self.anthropic_model
            cfg["base_url"] = self.anthropic_base_url or None
        elif provider == LLMProvider.OLLAMA:
            cfg["model"] = self.ollama_model
            cfg["base_url"] = self.ollama_base_url
        elif provider == LLMProvider.QWEN:
            cfg["model"] = self.qwen_model
            cfg["base_url"] = self.qwen_base_url
        cfg["max_tokens"] = self.max_tokens
        cfg["temperature"] = self.temperature
        return cfg

    def has_api_key(self, provider: LLMProvider) -> bool:
        keys = {
            LLMProvider.OPENAI: self.openai_api_key,
            LLMProvider.ANTHROPIC: self.anthropic_api_key,
            LLMProvider.QWEN: self.qwen_api_key,
        }
        return bool(keys.get(provider, ""))


class RedisSettings(BaseModel):
    url: str = Field(default="redis://localhost:6379/0")
    enabled: bool = Field(default=False)
    max_connections: int = Field(default=20)


# ====================================================================
# Root Settings
# ====================================================================

class Settings(BaseSettings):
    app_name: str = Field(default="StockQuant")
    env: str = Field(default="development")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    system: SystemSettings = Field(default_factory=SystemSettings)
    data_provider: DataProviderSettings = Field(default_factory=DataProviderSettings)
    trading: TradingSettings = Field(default_factory=TradingSettings)
    ai: AISettings = Field(default_factory=AISettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)

    model_config = {
        "extra": "allow",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_nested_delimiter": "__",
    }

    def get_jwt_secret(self) -> str:
        if self.env == "production" and self.jwt.secret_key == "dev-secret-key-change-in-production":
            raise ValueError("生产环境必须设置 JWT_SECRET_KEY")
        return self.jwt.secret_key

    def ai_enabled(self) -> bool:
        return self.ai.enabled

    def get_ai_model(self) -> str:
        p = self.ai.default_provider
        return {
            LLMProvider.OPENAI: self.ai.openai_model,
            LLMProvider.ANTHROPIC: self.ai.anthropic_model,
            LLMProvider.OLLAMA: self.ai.ollama_model,
            LLMProvider.QWEN: self.ai.qwen_model,
        }[p]

    def has_llm_key(self, provider: Optional[LLMProvider] = None) -> bool:
        p = provider or self.ai.default_provider
        return self.ai.has_api_key(p)

    def to_dict(self) -> Dict[str, Any]:
        data = self.model_dump()
        for section in ("jwt", "data_provider", "ai"):
            if section in data:
                sec = data[section]
                if isinstance(sec, dict):
                    for key in ("secret_key", "api_key", "alphafeed_key",
                                "openai_api_key", "anthropic_api_key", "qwen_api_key"):
                        if sec.get(key):
                            sec[key] = "***"
        return data


# ====================================================================
# Loaders / singleton
# ====================================================================

_settings: Optional[Settings] = None


def _load_settings() -> Settings:
    try:
        settings = Settings(
            app_name=os.getenv("APP_NAME", "StockQuant"),
            env=os.getenv("APP_ENV", "development"),
        )

        db_url = os.getenv("DATABASE_URL")
        if db_url:
            settings.database.url = db_url

        jwt_secret = os.getenv("JWT_SECRET_KEY")
        if jwt_secret:
            settings.jwt.secret_key = jwt_secret

        log_level = os.getenv("LOG_LEVEL")
        if log_level:
            settings.system.log_level = log_level

        dp_source = os.getenv("DATA_PROVIDER_SOURCE")
        if dp_source:
            settings.data_provider.source = dp_source
        settings.data_provider.alphafeed_key = os.getenv("ALPHAFEEED_API_KEY", settings.data_provider.alphafeed_key)
        settings.data_provider.api_key = os.getenv("DATA_API_KEY", settings.data_provider.api_key)
        settings.data_provider.api_url = os.getenv("DATA_API_URL", settings.data_provider.api_url)
        settings.data_provider.baostock.enabled = os.getenv("BAOSTOCK_ENABLED", "true").lower() == "true"
        settings.data_provider.tushare.api_key = os.getenv("TUSHARE_API_KEY", settings.data_provider.tushare.api_key)
        settings.data_provider.tdx.host = os.getenv("TDX_HOST", settings.data_provider.tdx.host)
        settings.data_provider.tdx.port = int(os.getenv("TDX_PORT", str(settings.data_provider.tdx.port)))
        settings.data_provider.csv.directory = os.getenv("CSV_DIR", settings.data_provider.csv.directory)
        settings.data_provider.duckdb.path = os.getenv("DUCKDB_PATH", settings.data_provider.duckdb.path)

        settings.ai.enabled = os.getenv("AI_ENABLED", "true").lower() == "true"
        ai_prov = os.getenv("AI_DEFAULT_PROVIDER")
        if ai_prov:
            try:
                settings.ai.default_provider = LLMProvider(ai_prov)
            except ValueError:
                pass
        settings.ai.openai_api_key = os.getenv("AI_OPENAI_API_KEY", settings.ai.openai_api_key)
        settings.ai.openai_model = os.getenv("AI_OPENAI_MODEL", settings.ai.openai_model)
        settings.ai.openai_base_url = os.getenv("AI_OPENAI_BASE_URL", settings.ai.openai_base_url)
        settings.ai.anthropic_api_key = os.getenv("AI_ANTHROPIC_API_KEY", settings.ai.anthropic_api_key)
        settings.ai.anthropic_model = os.getenv("AI_ANTHROPIC_MODEL", settings.ai.anthropic_model)
        settings.ai.anthropic_base_url = os.getenv("AI_ANTHROPIC_BASE_URL", settings.ai.anthropic_base_url)
        settings.ai.ollama_base_url = os.getenv("AI_OLLAMA_BASE_URL", settings.ai.ollama_base_url)
        settings.ai.ollama_model = os.getenv("AI_OLLAMA_MODEL", settings.ai.ollama_model)
        settings.ai.qwen_api_key = os.getenv("AI_QWEN_API_KEY", settings.ai.qwen_api_key)
        settings.ai.qwen_model = os.getenv("AI_QWEN_MODEL", settings.ai.qwen_model)
        settings.ai.qwen_base_url = os.getenv("AI_QWEN_BASE_URL", settings.ai.qwen_base_url)

        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            settings.redis.url = redis_url
        settings.redis.enabled = os.getenv("REDIS_ENABLED", "false").lower() == "true"

        return settings
    except Exception as e:
        logger.error("Config load failed: %s, using defaults", e)
        return Settings()


def get_config() -> Settings:
    global _settings
    if _settings is None:
        _settings = _load_settings()
    return _settings


def reload_config() -> Settings:
    global _settings
    _settings = _load_settings()
    return _settings


# ====================================================================
# Legacy compatibility
# ====================================================================

def load_config() -> dict:
    return get_config().to_dict()


def get_config_value(key: str, default: Any = None) -> Any:
    config = get_config()
    keys = key.split(".")
    value = config.model_dump()
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k, default)
        else:
            return default
    return value


def _merge_config(default: dict, override: dict) -> dict:
    result = default.copy()
    for key, value in override.items():
        if isinstance(value, dict) and key in result:
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(config: dict) -> dict:
    for key, value in os.environ.items():
        if key.startswith("SQ_"):
            config_key = key[3:].lower()
            config[config_key] = value
    return config
