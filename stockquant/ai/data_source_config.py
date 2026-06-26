# -*- coding: utf-8 -*-
"""F020 Phase F2 — 数据源配置加载器

从 config/data_sources.yaml 读取采集器与调度配置，提供类型化访问。

主要导出：
    - DataSourceConfig: 配置加载器单例
    - CollectorSpec: 单个采集通道规格
    - SourceSpec: 单个数据源规格
    - SchedulingSpec: 单个调度级别规格
    - get_data_source_config(): 获取全局单例
    - reset_data_source_config(): 测试重置

设计原则：
    1. 文件缺失/解析失败时回退到内置默认值（不抛异常）
    2. 支持环境变量 DATA_SOURCES_CONFIG_PATH 覆盖默认路径
    3. 提供 build_schedule_specs() 与 PipelineScheduler.add_task() 集成
    4. 提供 get_enabled_channels() / get_sources_for_channel() 便于采集器初始化
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from stockquant.ai.scheduler import ScheduleSpec

logger = logging.getLogger("stockquant.ai.data_source_config")


# ── 默认配置路径 ───────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config" / "data_sources.yaml"
CONFIG_ENV_VAR = "DATA_SOURCES_CONFIG_PATH"


# ── 内置默认值（文件缺失时回退） ────────────────────────────────────────────

_BUILTIN_DEFAULTS: Dict[str, Any] = {
    "collectors": {
        "news": {
            "enabled": True,
            "sources": [
                {"name": "eastmoney", "priority": 1, "trust_score": 0.8},
                {"name": "xueqiu", "priority": 2, "trust_score": 0.6},
            ],
        },
    },
    "scheduling": {
        "realtime": {
            "interval_seconds": 60,
            "collectors": ["news"],
        },
        "daily": {
            "hour": 18,
            "minute": 0,
            "collectors": [],
        },
    },
    "default_symbols": ["sh600519", "sz000858"],
    "collect": {
        "max_articles_per_source": 20,
        "retry_count": 2,
        "timeout_seconds": 30,
    },
}


# ── 数据结构 ──────────────────────────────────────────────────────────────


@dataclass
class SourceSpec:
    """单个数据源规格

    Attributes:
        name: 数据源标识（需与 SourceVerifier.TRUSTED_SOURCES 对齐）
        priority: 优先级（1=最高，越小越优先）
        trust_score: 信任分（0.0~1.0）
    """
    name: str = ""
    priority: int = 99
    trust_score: float = 0.5

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceSpec":
        return cls(
            name=str(data.get("name", "")),
            priority=int(data.get("priority", 99)),
            trust_score=float(data.get("trust_score", 0.5)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "priority": self.priority,
            "trust_score": self.trust_score,
        }


@dataclass
class CollectorSpec:
    """单个采集通道规格

    Attributes:
        channel: 通道名（如 news / social / research / financial / exchange / announcement）
        enabled: 是否启用
        sources: 数据源列表
    """
    channel: str = ""
    enabled: bool = True
    sources: List[SourceSpec] = field(default_factory=list)

    @classmethod
    def from_dict(cls, channel: str, data: Dict[str, Any]) -> "CollectorSpec":
        raw_sources = data.get("sources") or []
        sources = [SourceSpec.from_dict(s) for s in raw_sources if isinstance(s, dict)]
        # 按 priority 升序排序（1 在前）
        sources.sort(key=lambda s: (s.priority, s.name))
        return cls(
            channel=channel,
            enabled=bool(data.get("enabled", True)),
            sources=sources,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "sources": [s.to_dict() for s in self.sources],
        }

    def get_source_names(self) -> List[str]:
        """返回数据源名称列表（按 priority 排序）"""
        return [s.name for s in self.sources]


@dataclass
class SchedulingSpec:
    """单个调度级别规格

    Attributes:
        level: 调度级别 realtime|minute|hourly|daily
        interval_seconds: 间隔秒数（realtime/minute/hourly 用）
        daily_hour: 日级任务执行小时
        daily_minute: 日级任务执行分钟
        collectors: 该级别下要执行的采集通道列表
    """
    level: str = "realtime"
    interval_seconds: int = 60
    daily_hour: int = 18
    daily_minute: int = 0
    collectors: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, level: str, data: Dict[str, Any]) -> "SchedulingSpec":
        # daily 级别特有字段
        daily_hour = int(data.get("hour", 18))
        daily_minute = int(data.get("minute", 0))
        return cls(
            level=level,
            interval_seconds=int(data.get("interval_seconds", 60)),
            daily_hour=daily_hour,
            daily_minute=daily_minute,
            collectors=list(data.get("collectors") or []),
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "interval_seconds": self.interval_seconds,
            "collectors": list(self.collectors),
        }
        if self.level == "daily":
            result["hour"] = self.daily_hour
            result["minute"] = self.daily_minute
        return result

    def to_schedule_spec(self, name: str, symbols: Optional[List[str]] = None) -> ScheduleSpec:
        """转换为 PipelineScheduler 使用的 ScheduleSpec

        Args:
            name: 任务名（如 "realtime_news"）
            symbols: 采集目标符号列表（None 时使用空列表）
        """
        return ScheduleSpec(
            name=name,
            level=self.level,
            interval_seconds=self.interval_seconds,
            daily_hour=self.daily_hour,
            daily_minute=self.daily_minute,
            symbols=list(symbols or []),
            enabled=True,
        )


# ── 主配置类 ──────────────────────────────────────────────────────────────


class DataSourceConfig:
    """数据源配置加载器

    用法::

        from stockquant.ai.data_source_config import get_data_source_config

        cfg = get_data_source_config()
        for channel in cfg.get_enabled_channels():
            print(channel.channel, channel.get_source_names())

        for spec in cfg.build_schedule_specs():
            scheduler.add_task(spec)

    测试注入::

        from stockquant.ai.data_source_config import DataSourceConfig
        cfg = DataSourceConfig.from_yaml_string(yaml_text)
    """

    def __init__(self, raw: Optional[Dict[str, Any]] = None) -> None:
        # None → 内置默认值；空 dict {} → 显式空配置（不回退）
        self._raw: Dict[str, Any] = dict(_BUILTIN_DEFAULTS) if raw is None else raw
        self._collectors: Dict[str, CollectorSpec] = {}
        self._scheduling: Dict[str, SchedulingSpec] = {}
        self._default_symbols: List[str] = []
        self._collect_params: Dict[str, Any] = {}
        self._parse()

    # ── 加载入口 ────────────────────────────────────────────────────────

    @classmethod
    def from_file(cls, path: str) -> "DataSourceConfig":
        """从 YAML 文件加载

        若文件缺失或解析失败，回退到内置默认值。
        """
        path_obj = Path(path)
        if not path_obj.exists():
            logger.warning("数据源配置文件不存在: %s，使用内置默认值", path)
            return cls()
        try:
            with open(path_obj, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            if not isinstance(raw, dict):
                logger.warning("配置文件根节点不是 mapping，使用默认值: %s", path)
                return cls()
            return cls(raw=raw)
        except yaml.YAMLError as e:
            logger.error("YAML 解析失败 (%s): %s，使用默认值", path, e)
            return cls()
        except OSError as e:
            logger.error("读取配置文件失败 (%s): %s，使用默认值", path, e)
            return cls()

    @classmethod
    def from_yaml_string(cls, yaml_text: str) -> "DataSourceConfig":
        """从 YAML 字符串加载（用于测试）"""
        try:
            raw = yaml.safe_load(yaml_text)
            if not isinstance(raw, dict):
                raise ValueError("YAML 根节点必须是 mapping")
            return cls(raw=raw)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 解析失败: {e}") from e

    @classmethod
    def load_default(cls) -> "DataSourceConfig":
        """从默认路径加载（受环境变量覆盖）

        优先级：环境变量 DATA_SOURCES_CONFIG_PATH > config/data_sources.yaml > 内置默认值
        """
        env_path = os.getenv(CONFIG_ENV_VAR)
        if env_path:
            logger.info("从环境变量加载配置: %s=%s", CONFIG_ENV_VAR, env_path)
            return cls.from_file(env_path)
        return cls.from_file(str(DEFAULT_CONFIG_PATH))

    # ── 解析 ────────────────────────────────────────────────────────────

    def _parse(self) -> None:
        """解析原始字典为类型化数据结构"""
        # collectors
        self._collectors = {}
        raw_collectors = self._raw.get("collectors") or {}
        if isinstance(raw_collectors, dict):
            for channel, data in raw_collectors.items():
                if not isinstance(data, dict):
                    continue
                self._collectors[channel] = CollectorSpec.from_dict(channel, data)

        # scheduling
        self._scheduling = {}
        raw_scheduling = self._raw.get("scheduling") or {}
        if isinstance(raw_scheduling, dict):
            for level, data in raw_scheduling.items():
                if not isinstance(data, dict):
                    continue
                self._scheduling[level] = SchedulingSpec.from_dict(level, data)

        # default_symbols
        raw_symbols = self._raw.get("default_symbols") or []
        if isinstance(raw_symbols, list):
            self._default_symbols = [str(s) for s in raw_symbols]
        else:
            self._default_symbols = []

        # collect params
        raw_collect = self._raw.get("collect") or {}
        if isinstance(raw_collect, dict):
            self._collect_params = dict(raw_collect)
        else:
            self._collect_params = {}

    # ── 查询接口 ────────────────────────────────────────────────────────

    def get_channels(self) -> List[str]:
        """返回所有通道名"""
        return list(self._collectors.keys())

    def get_collector(self, channel: str) -> Optional[CollectorSpec]:
        """获取指定通道规格"""
        return self._collectors.get(channel)

    def get_enabled_channels(self) -> List[CollectorSpec]:
        """获取所有已启用的通道"""
        return [c for c in self._collectors.values() if c.enabled]

    def get_disabled_channels(self) -> List[CollectorSpec]:
        """获取所有已禁用的通道"""
        return [c for c in self._collectors.values() if not c.enabled]

    def is_channel_enabled(self, channel: str) -> bool:
        """检查通道是否启用"""
        spec = self._collectors.get(channel)
        return spec.enabled if spec else False

    def get_sources_for_channel(self, channel: str) -> List[SourceSpec]:
        """获取通道下的数据源列表（已按 priority 排序）"""
        spec = self._collectors.get(channel)
        if spec is None:
            return []
        return list(spec.sources)

    def get_source_names_for_channel(self, channel: str) -> List[str]:
        """获取通道下的数据源名称列表"""
        return [s.name for s in self.get_sources_for_channel(channel)]

    def get_all_source_names(self) -> List[str]:
        """获取所有通道的全部数据源名称"""
        names: List[str] = []
        for spec in self._collectors.values():
            for src in spec.sources:
                if src.name and src.name not in names:
                    names.append(src.name)
        return names

    # ── 调度查询 ────────────────────────────────────────────────────────

    def get_scheduling_levels(self) -> List[str]:
        """返回所有调度级别"""
        return list(self._scheduling.keys())

    def get_scheduling(self, level: str) -> Optional[SchedulingSpec]:
        """获取指定级别的调度规格"""
        return self._scheduling.get(level)

    def get_channels_for_level(self, level: str) -> List[str]:
        """获取某级别下要执行的通道列表"""
        spec = self._scheduling.get(level)
        return list(spec.collectors) if spec else []

    def build_schedule_specs(
        self,
        symbols: Optional[List[str]] = None,
    ) -> List[ScheduleSpec]:
        """构建调度规格列表（用于 PipelineScheduler.add_task）

        Args:
            symbols: 采集目标符号（None 时使用配置文件中的 default_symbols）

        Returns:
            ScheduleSpec 列表，每个调度级别一个
        """
        syms = symbols if symbols is not None else list(self._default_symbols)
        specs: List[ScheduleSpec] = []
        for level, sched in self._scheduling.items():
            if not sched.collectors:
                # 该级别未配置任何通道，跳过
                continue
            name = f"{level}_pipeline"
            spec = sched.to_schedule_spec(name=name, symbols=syms)
            specs.append(spec)
        return specs

    # ── 默认符号与采集参数 ────────────────────────────────────────────────

    def get_default_symbols(self) -> List[str]:
        """获取默认采集目标符号"""
        return list(self._default_symbols)

    def get_max_articles_per_source(self) -> int:
        """获取每个数据源的最大文章数"""
        return int(self._collect_params.get("max_articles_per_source", 20))

    def get_retry_count(self) -> int:
        """获取采集失败重试次数"""
        return int(self._collect_params.get("retry_count", 2))

    def get_timeout_seconds(self) -> int:
        """获取单次采集超时秒数"""
        return int(self._collect_params.get("timeout_seconds", 30))

    # ── 序列化 ──────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """导出为原始字典"""
        return {
            "collectors": {
                ch: spec.to_dict() for ch, spec in self._collectors.items()
            },
            "scheduling": {
                lvl: spec.to_dict() for lvl, spec in self._scheduling.items()
            },
            "default_symbols": list(self._default_symbols),
            "collect": dict(self._collect_params),
        }

    def __repr__(self) -> str:
        return (
            f"DataSourceConfig(channels={len(self._collectors)}, "
            f"levels={len(self._scheduling)}, "
            f"symbols={len(self._default_symbols)})"
        )


# ── 单例 ─────────────────────────────────────────────────────────────────


_config_instance: Optional[DataSourceConfig] = None


def get_data_source_config() -> DataSourceConfig:
    """获取全局数据源配置单例

    首次调用时从默认路径加载，后续调用返回缓存。
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = DataSourceConfig.load_default()
    return _config_instance


def reset_data_source_config() -> None:
    """重置单例（测试用）"""
    global _config_instance
    _config_instance = None


def load_data_source_config(path: Optional[str] = None) -> DataSourceConfig:
    """显式加载配置文件，更新单例

    Args:
        path: 配置文件路径（None 时使用默认路径）
    """
    global _config_instance
    if path:
        _config_instance = DataSourceConfig.from_file(path)
    else:
        _config_instance = DataSourceConfig.load_default()
    return _config_instance
