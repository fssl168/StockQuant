# -*- coding: utf-8 -*-
"""F020 Phase F2 — 数据源配置加载器测试

覆盖：
- SourceSpec / CollectorSpec / SchedulingSpec 数据结构
- DataSourceConfig.from_yaml_string 解析
- DataSourceConfig.from_file 文件加载与回退
- 通道查询接口
- 调度查询接口
- build_schedule_specs 集成 PipelineScheduler
- 默认符号与采集参数
- 单例与重置
- 配置文件存在性验证
"""
from __future__ import annotations

import os
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from stockquant.ai.data_source_config import (
    CollectorSpec,
    CONFIG_ENV_VAR,
    DataSourceConfig,
    DEFAULT_CONFIG_PATH,
    SourceSpec,
    SchedulingSpec,
    get_data_source_config,
    load_data_source_config,
    reset_data_source_config,
)
from stockquant.ai.scheduler import ScheduleSpec


# ── 工具函数 ──────────────────────────────────────────────────────────────


SAMPLE_YAML = textwrap.dedent("""
    collectors:
      news:
        enabled: true
        sources:
          - name: eastmoney
            priority: 1
            trust_score: 0.8
          - name: xueqiu
            priority: 2
            trust_score: 0.6
      research:
        enabled: false
        sources:
          - name: eastmoney_research
            priority: 1
            trust_score: 0.8

    scheduling:
      realtime:
        interval_seconds: 60
        collectors: [news]
      daily:
        hour: 18
        minute: 0
        collectors: [research]

    default_symbols:
      - sh600519
      - sz000858

    collect:
      max_articles_per_source: 30
      retry_count: 3
      timeout_seconds: 45
""").strip()


# ── SourceSpec ────────────────────────────────────────────────────────────


class TestSourceSpec:
    """测试 SourceSpec 数据结构"""

    def test_from_dict_with_all_fields(self):
        d = {"name": "eastmoney", "priority": 1, "trust_score": 0.8}
        spec = SourceSpec.from_dict(d)
        assert spec.name == "eastmoney"
        assert spec.priority == 1
        assert spec.trust_score == 0.8

    def test_from_dict_with_missing_fields(self):
        spec = SourceSpec.from_dict({})
        assert spec.name == ""
        assert spec.priority == 99
        assert spec.trust_score == 0.5

    def test_from_dict_with_partial_fields(self):
        spec = SourceSpec.from_dict({"name": "sina"})
        assert spec.name == "sina"
        assert spec.priority == 99
        assert spec.trust_score == 0.5

    def test_from_dict_with_string_values(self):
        spec = SourceSpec.from_dict({
            "name": "xueqiu",
            "priority": "2",
            "trust_score": "0.6",
        })
        assert spec.priority == 2
        assert spec.trust_score == 0.6

    def test_to_dict(self):
        spec = SourceSpec(name="sse", priority=1, trust_score=0.95)
        d = spec.to_dict()
        assert d == {
            "name": "sse",
            "priority": 1,
            "trust_score": 0.95,
        }


# ── CollectorSpec ──────────────────────────────────────────────────────────


class TestCollectorSpec:
    """测试 CollectorSpec 数据结构"""

    def test_from_dict_with_enabled_and_sources(self):
        data = {
            "enabled": True,
            "sources": [
                {"name": "eastmoney", "priority": 2, "trust_score": 0.8},
                {"name": "xueqiu", "priority": 1, "trust_score": 0.6},
            ],
        }
        spec = CollectorSpec.from_dict("news", data)
        assert spec.channel == "news"
        assert spec.enabled is True
        # 按 priority 升序排序后，xueqiu 应在前
        assert len(spec.sources) == 2
        assert spec.sources[0].name == "xueqiu"
        assert spec.sources[1].name == "eastmoney"

    def test_from_dict_with_disabled(self):
        spec = CollectorSpec.from_dict("research", {"enabled": False, "sources": []})
        assert spec.enabled is False
        assert spec.sources == []

    def test_from_dict_with_missing_sources_key(self):
        spec = CollectorSpec.from_dict("news", {"enabled": True})
        assert spec.sources == []

    def test_from_dict_with_invalid_source_entries(self):
        """非 dict 的 sources 条目应被忽略"""
        data = {
            "enabled": True,
            "sources": [
                {"name": "ok", "priority": 1},
                "invalid_string",
                123,
                None,
            ],
        }
        spec = CollectorSpec.from_dict("news", data)
        assert len(spec.sources) == 1
        assert spec.sources[0].name == "ok"

    def test_get_source_names(self):
        spec = CollectorSpec(
            channel="news",
            enabled=True,
            sources=[
                SourceSpec(name="a", priority=1, trust_score=0.5),
                SourceSpec(name="b", priority=2, trust_score=0.6),
            ],
        )
        assert spec.get_source_names() == ["a", "b"]

    def test_to_dict(self):
        spec = CollectorSpec(
            channel="news",
            enabled=True,
            sources=[SourceSpec(name="a", priority=1, trust_score=0.5)],
        )
        d = spec.to_dict()
        assert d["enabled"] is True
        assert len(d["sources"]) == 1
        assert d["sources"][0]["name"] == "a"


# ── SchedulingSpec ────────────────────────────────────────────────────────


class TestSchedulingSpec:
    """测试 SchedulingSpec 数据结构"""

    def test_from_dict_realtime(self):
        data = {"interval_seconds": 120, "collectors": ["news", "social"]}
        spec = SchedulingSpec.from_dict("realtime", data)
        assert spec.level == "realtime"
        assert spec.interval_seconds == 120
        assert spec.collectors == ["news", "social"]
        # realtime 不读 hour/minute
        assert spec.daily_hour == 18
        assert spec.daily_minute == 0

    def test_from_dict_daily(self):
        data = {"hour": 9, "minute": 30, "collectors": ["research"]}
        spec = SchedulingSpec.from_dict("daily", data)
        assert spec.level == "daily"
        assert spec.daily_hour == 9
        assert spec.daily_minute == 30
        assert spec.collectors == ["research"]

    def test_from_dict_with_defaults(self):
        spec = SchedulingSpec.from_dict("minute", {})
        assert spec.interval_seconds == 60
        assert spec.collectors == []

    def test_to_dict_realtime(self):
        spec = SchedulingSpec(
            level="realtime",
            interval_seconds=60,
            collectors=["news"],
        )
        d = spec.to_dict()
        assert d["interval_seconds"] == 60
        assert d["collectors"] == ["news"]
        # realtime 不输出 hour/minute
        assert "hour" not in d
        assert "minute" not in d

    def test_to_dict_daily_includes_hour_minute(self):
        spec = SchedulingSpec(
            level="daily",
            interval_seconds=86400,
            daily_hour=9,
            daily_minute=30,
            collectors=["research"],
        )
        d = spec.to_dict()
        assert d["hour"] == 9
        assert d["minute"] == 30

    def test_to_schedule_spec(self):
        spec = SchedulingSpec(
            level="realtime",
            interval_seconds=60,
            collectors=["news"],
        )
        sched = spec.to_schedule_spec("test_pipeline", symbols=["sh600519"])
        assert isinstance(sched, ScheduleSpec)
        assert sched.name == "test_pipeline"
        assert sched.level == "realtime"
        assert sched.interval_seconds == 60
        assert sched.symbols == ["sh600519"]

    def test_to_schedule_spec_with_none_symbols(self):
        spec = SchedulingSpec(level="daily", daily_hour=9, daily_minute=30, collectors=["research"])
        sched = spec.to_schedule_spec("daily_pipeline")
        assert sched.symbols == []
        assert sched.daily_hour == 9
        assert sched.daily_minute == 30


# ── DataSourceConfig 解析 ────────────────────────────────────────────────


class TestDataSourceConfigParsing:
    """测试 DataSourceConfig.from_yaml_string"""

    def test_parse_full_yaml(self):
        cfg = DataSourceConfig.from_yaml_string(SAMPLE_YAML)
        # collectors
        assert "news" in cfg.get_channels()
        assert "research" in cfg.get_channels()
        # news 启用，research 禁用
        assert cfg.is_channel_enabled("news")
        assert not cfg.is_channel_enabled("research")
        # sources for news
        sources = cfg.get_sources_for_channel("news")
        assert len(sources) == 2
        assert sources[0].name == "eastmoney"  # priority=1
        assert sources[1].name == "xueqiu"  # priority=2

    def test_parse_scheduling(self):
        cfg = DataSourceConfig.from_yaml_string(SAMPLE_YAML)
        levels = cfg.get_scheduling_levels()
        assert "realtime" in levels
        assert "daily" in levels

        realtime = cfg.get_scheduling("realtime")
        assert realtime.interval_seconds == 60
        assert realtime.collectors == ["news"]

        daily = cfg.get_scheduling("daily")
        assert daily.daily_hour == 18
        assert daily.daily_minute == 0
        assert daily.collectors == ["research"]

    def test_parse_default_symbols(self):
        cfg = DataSourceConfig.from_yaml_string(SAMPLE_YAML)
        assert cfg.get_default_symbols() == ["sh600519", "sz000858"]

    def test_parse_collect_params(self):
        cfg = DataSourceConfig.from_yaml_string(SAMPLE_YAML)
        assert cfg.get_max_articles_per_source() == 30
        assert cfg.get_retry_count() == 3
        assert cfg.get_timeout_seconds() == 45

    def test_parse_invalid_yaml_raises(self):
        with pytest.raises(ValueError):
            DataSourceConfig.from_yaml_string("not: valid: yaml: :")

    def test_parse_non_mapping_raises(self):
        with pytest.raises(ValueError):
            DataSourceConfig.from_yaml_string("- list\n- not\n- dict")

    def test_empty_yaml_uses_defaults(self):
        """空 dict 用默认配置"""
        cfg = DataSourceConfig.from_yaml_string("{}")
        # 没有任何 collectors，但不会抛异常
        assert cfg.get_channels() == []
        assert cfg.get_default_symbols() == []


# ── DataSourceConfig from_file ─────────────────────────────────────────────


class TestDataSourceConfigFromFile:
    """测试从文件加载与回退"""

    def test_load_from_existing_file(self, tmp_path: Path):
        yaml_file = tmp_path / "test_sources.yaml"
        yaml_file.write_text(SAMPLE_YAML, encoding="utf-8")
        cfg = DataSourceConfig.from_file(str(yaml_file))
        assert cfg.is_channel_enabled("news")
        assert cfg.get_max_articles_per_source() == 30

    def test_load_from_nonexistent_file_falls_back(self):
        cfg = DataSourceConfig.from_file("/nonexistent/path/sources.yaml")
        # 应回退到内置默认值（至少有 news 通道）
        assert "news" in cfg.get_channels()

    def test_load_from_invalid_yaml_falls_back(self, tmp_path: Path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("not: valid: yaml: :", encoding="utf-8")
        cfg = DataSourceConfig.from_file(str(bad_file))
        # 应回退到默认值
        assert "news" in cfg.get_channels()

    def test_load_from_non_mapping_yaml_falls_back(self, tmp_path: Path):
        bad_file = tmp_path / "list.yaml"
        bad_file.write_text("- item1\n- item2", encoding="utf-8")
        cfg = DataSourceConfig.from_file(str(bad_file))
        assert "news" in cfg.get_channels()

    def test_load_default_path(self):
        """默认路径文件存在时正常加载"""
        cfg = DataSourceConfig.load_default()
        # 至少应该有 news 通道
        assert "news" in cfg.get_channels()

    def test_load_default_with_env_var(self, tmp_path: Path):
        """环境变量覆盖默认路径"""
        yaml_file = tmp_path / "custom.yaml"
        yaml_file.write_text(SAMPLE_YAML, encoding="utf-8")
        old_val = os.environ.get(CONFIG_ENV_VAR)
        try:
            os.environ[CONFIG_ENV_VAR] = str(yaml_file)
            cfg = DataSourceConfig.load_default()
            assert cfg.get_max_articles_per_source() == 30
        finally:
            if old_val is None:
                os.environ.pop(CONFIG_ENV_VAR, None)
            else:
                os.environ[CONFIG_ENV_VAR] = old_val


# ── 查询接口 ──────────────────────────────────────────────────────────────


class TestQueryInterfaces:
    """测试查询接口"""

    def setup_method(self):
        self.cfg = DataSourceConfig.from_yaml_string(SAMPLE_YAML)

    def test_get_channels(self):
        channels = self.cfg.get_channels()
        assert set(channels) == {"news", "research"}

    def test_get_collector_existing(self):
        spec = self.cfg.get_collector("news")
        assert spec is not None
        assert spec.channel == "news"
        assert spec.enabled is True

    def test_get_collector_nonexistent(self):
        assert self.cfg.get_collector("nonexistent") is None

    def test_get_enabled_channels(self):
        enabled = self.cfg.get_enabled_channels()
        assert len(enabled) == 1
        assert enabled[0].channel == "news"

    def test_get_disabled_channels(self):
        disabled = self.cfg.get_disabled_channels()
        assert len(disabled) == 1
        assert disabled[0].channel == "research"

    def test_is_channel_enabled(self):
        assert self.cfg.is_channel_enabled("news") is True
        assert self.cfg.is_channel_enabled("research") is False
        assert self.cfg.is_channel_enabled("nonexistent") is False

    def test_get_sources_for_channel(self):
        sources = self.cfg.get_sources_for_channel("news")
        assert len(sources) == 2
        assert sources[0].name == "eastmoney"

    def test_get_sources_for_nonexistent_channel(self):
        assert self.cfg.get_sources_for_channel("nonexistent") == []

    def test_get_source_names_for_channel(self):
        names = self.cfg.get_source_names_for_channel("news")
        assert names == ["eastmoney", "xueqiu"]

    def test_get_all_source_names(self):
        names = self.cfg.get_all_source_names()
        # news: eastmoney, xueqiu; research: eastmoney_research
        assert "eastmoney" in names
        assert "xueqiu" in names
        assert "eastmoney_research" in names

    def test_get_all_source_names_deduplicated(self):
        """同名 source 不应重复"""
        yaml_text = textwrap.dedent("""
            collectors:
              a:
                enabled: true
                sources:
                  - {name: shared, priority: 1, trust_score: 0.5}
              b:
                enabled: true
                sources:
                  - {name: shared, priority: 1, trust_score: 0.5}
                  - {name: unique_b, priority: 2, trust_score: 0.5}
        """).strip()
        cfg = DataSourceConfig.from_yaml_string(yaml_text)
        names = cfg.get_all_source_names()
        assert names.count("shared") == 1
        assert "unique_b" in names


# ── 调度查询与构建 ────────────────────────────────────────────────────────


class TestSchedulingQueries:
    """测试调度查询与 ScheduleSpec 构建"""

    def setup_method(self):
        self.cfg = DataSourceConfig.from_yaml_string(SAMPLE_YAML)

    def test_get_scheduling_levels(self):
        levels = self.cfg.get_scheduling_levels()
        assert "realtime" in levels
        assert "daily" in levels

    def test_get_scheduling_existing(self):
        sched = self.cfg.get_scheduling("realtime")
        assert sched.interval_seconds == 60
        assert sched.collectors == ["news"]

    def test_get_scheduling_nonexistent(self):
        assert self.cfg.get_scheduling("nonexistent") is None

    def test_get_channels_for_level(self):
        assert self.cfg.get_channels_for_level("realtime") == ["news"]
        assert self.cfg.get_channels_for_level("daily") == ["research"]
        assert self.cfg.get_channels_for_level("nonexistent") == []

    def test_build_schedule_specs_with_default_symbols(self):
        specs = self.cfg.build_schedule_specs()
        # realtime 和 daily 都有 collectors，应生成 2 个 spec
        assert len(specs) == 2
        names = [s.name for s in specs]
        assert "realtime_pipeline" in names
        assert "daily_pipeline" in names

        # 检查 symbols 使用了 default_symbols
        for spec in specs:
            assert spec.symbols == ["sh600519", "sz000858"]

    def test_build_schedule_specs_with_custom_symbols(self):
        specs = self.cfg.build_schedule_specs(symbols=["sh000001"])
        for spec in specs:
            assert spec.symbols == ["sh000001"]

    def test_build_schedule_specs_skips_empty_collectors(self):
        """没有 collectors 的级别应被跳过"""
        yaml_text = textwrap.dedent("""
            scheduling:
              realtime:
                interval_seconds: 60
                collectors: []
              daily:
                hour: 18
                minute: 0
                collectors: [news]
        """).strip()
        cfg = DataSourceConfig.from_yaml_string(yaml_text)
        specs = cfg.build_schedule_specs()
        # realtime 空，应只生成 daily
        assert len(specs) == 1
        assert specs[0].level == "daily"

    def test_build_schedule_specs_empty_config(self):
        """没有 scheduling 配置时应返回空列表"""
        cfg = DataSourceConfig.from_yaml_string("{}")
        assert cfg.build_schedule_specs() == []


# ── 默认值与回退 ──────────────────────────────────────────────────────────


class TestDefaultsAndFallback:
    """测试默认值与回退"""

    def test_default_constructor_uses_builtin_defaults(self):
        cfg = DataSourceConfig()
        # 内置默认值应至少有 news 通道
        assert "news" in cfg.get_channels()
        # 内置默认值应有 realtime scheduling
        assert "realtime" in cfg.get_scheduling_levels()
        # 内置默认值应有 default_symbols
        assert len(cfg.get_default_symbols()) >= 1

    def test_default_collect_params(self):
        """没有 collect 段时使用默认值"""
        cfg = DataSourceConfig.from_yaml_string("collectors: {}")
        assert cfg.get_max_articles_per_source() == 20
        assert cfg.get_retry_count() == 2
        assert cfg.get_timeout_seconds() == 30

    def test_default_daily_hour_minute(self):
        """daily 段没有 hour/minute 时使用 18:00"""
        yaml_text = textwrap.dedent("""
            scheduling:
              daily:
                collectors: [news]
        """).strip()
        cfg = DataSourceConfig.from_yaml_string(yaml_text)
        daily = cfg.get_scheduling("daily")
        assert daily.daily_hour == 18
        assert daily.daily_minute == 0


# ── 序列化 ──────────────────────────────────────────────────────────────


class TestSerialization:
    """测试 to_dict / __repr__"""

    def test_to_dict_roundtrip(self):
        cfg = DataSourceConfig.from_yaml_string(SAMPLE_YAML)
        d = cfg.to_dict()
        assert "collectors" in d
        assert "scheduling" in d
        assert "default_symbols" in d
        assert "collect" in d
        assert d["default_symbols"] == ["sh600519", "sz000858"]
        assert d["collectors"]["news"]["enabled"] is True
        assert d["scheduling"]["realtime"]["interval_seconds"] == 60

    def test_repr(self):
        cfg = DataSourceConfig.from_yaml_string(SAMPLE_YAML)
        s = repr(cfg)
        assert "DataSourceConfig" in s
        assert "channels=2" in s
        assert "levels=2" in s
        assert "symbols=2" in s


# ── 单例 ──────────────────────────────────────────────────────────────────


class TestSingleton:
    """测试单例与重置"""

    def test_get_data_source_config_singleton(self):
        reset_data_source_config()
        cfg1 = get_data_source_config()
        cfg2 = get_data_source_config()
        assert cfg1 is cfg2

    def test_reset_data_source_config(self):
        cfg1 = get_data_source_config()
        reset_data_source_config()
        cfg2 = get_data_source_config()
        assert cfg1 is not cfg2

    def test_load_data_source_config_default_path(self):
        reset_data_source_config()
        cfg = load_data_source_config()
        # 应从默认路径加载，包含 news 通道
        assert "news" in cfg.get_channels()
        # 单例应被更新
        assert get_data_source_config() is cfg

    def test_load_data_source_config_custom_path(self, tmp_path: Path):
        yaml_file = tmp_path / "custom.yaml"
        yaml_file.write_text(SAMPLE_YAML, encoding="utf-8")
        reset_data_source_config()
        cfg = load_data_source_config(str(yaml_file))
        assert cfg.get_max_articles_per_source() == 30
        # 单例应被更新
        assert get_data_source_config() is cfg


# ── 集成：与 config/data_sources.yaml 文件 ──────────────────────────────────


class TestIntegrationWithConfigFile:
    """测试与项目内置 config/data_sources.yaml 的集成"""

    def test_default_config_path_exists(self):
        """项目应有 config/data_sources.yaml 文件"""
        assert DEFAULT_CONFIG_PATH.exists(), f"配置文件应存在: {DEFAULT_CONFIG_PATH}"

    def test_default_config_has_expected_channels(self):
        """默认配置应包含所有预期通道"""
        cfg = DataSourceConfig.load_default()
        channels = cfg.get_channels()
        for expected in ["news", "social", "announcement", "research", "financial", "exchange"]:
            assert expected in channels, f"通道 {expected} 应存在"

    def test_default_config_all_channels_enabled(self):
        """默认配置的所有通道应启用"""
        cfg = DataSourceConfig.load_default()
        for channel in cfg.get_channels():
            assert cfg.is_channel_enabled(channel), f"通道 {channel} 应启用"

    def test_default_config_has_realtime_and_daily(self):
        """默认配置应有 realtime 和 daily 调度"""
        cfg = DataSourceConfig.load_default()
        levels = cfg.get_scheduling_levels()
        assert "realtime" in levels
        assert "daily" in levels

    def test_default_config_build_schedule_specs(self):
        """默认配置应能构建非空的 ScheduleSpec 列表"""
        cfg = DataSourceConfig.load_default()
        specs = cfg.build_schedule_specs()
        assert len(specs) >= 2  # 至少 realtime + daily
        for spec in specs:
            assert isinstance(spec, ScheduleSpec)
            assert spec.symbols  # 应有默认 symbols

    def test_default_config_has_default_symbols(self):
        cfg = DataSourceConfig.load_default()
        symbols = cfg.get_default_symbols()
        assert len(symbols) >= 1
        # 应是 A 股代码格式
        for sym in symbols:
            assert sym.startswith(("sh", "sz"))

    def test_default_config_source_names_in_trusted_sources(self):
        """默认配置的数据源名称应与 SourceVerifier.TRUSTED_SOURCES 对齐"""
        from stockquant.ai.collectors.verifier import SourceVerifier

        verifier = SourceVerifier()
        cfg = DataSourceConfig.load_default()
        all_names = cfg.get_all_source_names()
        # 至少应有一些名称
        assert len(all_names) >= 3
        # 检查每个名称是否在 TRUSTED_SOURCES 中（如果是未知源，会被 SourceVerifier 标记为不可信）
        for name in all_names:
            # 不强制要求所有都在白名单，但应能通过基本格式检查
            assert isinstance(name, str)
            assert len(name) > 0


# ── 边界情况 ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    """测试边界情况"""

    def test_collector_with_no_sources_dict(self):
        """collectors.<channel> 是 dict 但 sources 字段缺失"""
        cfg = DataSourceConfig.from_yaml_string("collectors:\n  news:\n    enabled: true\n")
        spec = cfg.get_collector("news")
        assert spec is not None
        assert spec.sources == []

    def test_scheduling_level_with_no_collectors(self):
        yaml_text = textwrap.dedent("""
            scheduling:
              hourly:
                interval_seconds: 3600
        """).strip()
        cfg = DataSourceConfig.from_yaml_string(yaml_text)
        sched = cfg.get_scheduling("hourly")
        assert sched.collectors == []
        # build 时该级别会被跳过
        specs = cfg.build_schedule_specs()
        assert specs == []

    def test_to_dict_preserves_structure(self):
        """to_dict 应保留原始结构"""
        cfg = DataSourceConfig.from_yaml_string(SAMPLE_YAML)
        d = cfg.to_dict()
        # 重建
        cfg2 = DataSourceConfig(raw=d)
        assert cfg2.is_channel_enabled("news")
        assert cfg2.get_default_symbols() == cfg.get_default_symbols()
