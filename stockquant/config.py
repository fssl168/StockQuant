# -*- coding: utf-8 -*-
"""StockQuant 配置管理 - 统一配置层使用 Pydantic BaseSettings"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import logging

logger = logging.getLogger("stockquant.config")


# ============ Pydantic 配置模型 ============

class DatabaseSettings(BaseModel):
    """数据库配置"""
    url: str = Field(default="sqlite:///./stockquant.db", description="数据库连接URL")
    pool_size: int = Field(default=10, ge=1, le=100)
    max_overflow: int = Field(default=20, ge=0, le=100)
    pool_timeout: int = Field(default=30, ge=1, le=300)
    echo: bool = Field(default=False, description="是否打印SQL日志")


class JWTSettings(BaseModel):
    """JWT 配置"""
    secret_key: str = Field(default="dev-secret-key-change-in-production", description="JWT密钥")
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=120, description="Access token 过期时间(分钟)")
    refresh_token_expire_days: int = Field(default=7, description="Refresh token 过期时间(天)")


class SystemSettings(BaseModel):
    """系统配置"""
    log_level: str = Field(default="INFO", description="日志级别")
    web_port: int = Field(default=8000, ge=1, le=65535)
    initial_capital: float = Field(default=1_000_000, ge=10000)
    commission_rate: float = Field(default=0.00025, ge=0, le=0.003)
    min_commission: float = Field(default=5, ge=0)
    stamp_tax_rate: float = Field(default=0.0005, ge=0, le=0.01)
    slippage: float = Field(default=0, ge=0)
    lot_size: int = Field(default=100, ge=100)
    price_limit_ratio: float = Field(default=0.1, ge=0.05, le=0.3)


class DataProviderSettings(BaseModel):
    """数据源配置"""
    source: str = Field(default="alphafeed", description="默认数据源")
    alphafeed_key: str = Field(default="", description="AlphaFeed API 密钥")
    api_key: str = Field(default="", description="数据源认证密钥")
    api_url: str = Field(default="", description="数据源接口地址")
    baostock_enabled: bool = Field(default=True)
    duckdb_path: str = Field(default="")


class TradingSettings(BaseModel):
    """交易配置"""
    mode: str = Field(default="simulator", description="交易模式: backtest/simulator/live")


class Settings(BaseSettings):
    """统一配置类 - 优先级: 环境变量 > YAML > 默认值"""
    
    # 基础配置
    app_name: str = Field(default="StockQuant", description="应用名称")
    env: str = Field(default="development", description="运行环境")
    
    # 子配置
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    system: SystemSettings = Field(default_factory=SystemSettings)
    data_provider: DataProviderSettings = Field(default_factory=DataProviderSettings)
    trading: TradingSettings = Field(default_factory=TradingSettings)
    
    model_config = {
        "extra": "allow",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_nested_delimiter": "__",
    }

    
    def get_jwt_secret(self) -> str:
        """获取 JWT 密钥，生产环境必须修改"""
        if self.env == "production" and self.jwt.secret_key == "dev-secret-key-change-in-production":
            raise ValueError("生产环境必须设置 JWT_SECRET_KEY 环境变量")
        return self.jwt.secret_key
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（敏感信息掩码）"""
        data = self.model_dump()
        # 掩码敏感信息
        if data.get("jwt", {}).get("secret_key"):
            data["jwt"]["secret_key"] = "***"
        if data.get("data_provider", {}).get("alphafeed_key"):
            data["data_provider"]["alphafeed_key"] = "***"
        if data.get("data_provider", {}).get("api_key"):
            data["data_provider"]["api_key"] = "***"
        return data


# ============ 兼容层 ============

# 全局配置实例
_settings: Optional[Settings] = None


def _load_settings() -> Settings:
    """加载配置"""
    try:
        # 从环境变量加载
        settings = Settings(
            app_name=os.getenv("APP_NAME", "StockQuant"),
            env=os.getenv("APP_ENV", "development"),
        )
        
        # 数据库配置从环境变量
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            settings.database.url = db_url
        
        # JWT 密钥必须从环境变量读取
        jwt_secret = os.getenv("JWT_SECRET_KEY")
        if jwt_secret:
            settings.jwt.secret_key = jwt_secret
        
        # 日志级别
        log_level = os.getenv("LOG_LEVEL")
        if log_level:
            settings.system.log_level = log_level
        
        return settings
        
    except Exception as e:
        logger.error(f"配置加载失败: {e}, 使用默认配置")
        return Settings()


def get_config() -> Settings:
    """获取配置单例"""
    global _settings
    if _settings is None:
        _settings = _load_settings()
    return _settings


def reload_config() -> Settings:
    """重新加载配置"""
    global _settings
    _settings = _load_settings()
    return _settings


# ============ 旧版兼容函数 ============

def load_config() -> dict:
    """旧版接口：返回字典格式配置"""
    return get_config().to_dict()


def get_config_value(key: str, default: Any = None) -> Any:
    """获取配置值"""
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
    """合并配置"""
    result = default.copy()
    for key, value in override.items():
        if isinstance(value, dict) and key in result:
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(config: dict) -> dict:
    """应用环境变量覆盖"""
    # 环境变量优先级高于配置文件
    for key, value in os.environ.items():
        if key.startswith("SQ_"):
            config_key = key[3:].lower()
            config[config_key] = value
    return config
