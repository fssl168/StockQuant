# -*- coding: utf-8 -*-
"""F020 Memory 模块 — 日报/月报/年报三级报告体系

改造自原有 FinMem 三层分层记忆系统（L1/L2/L3），现采用日报(daily)/月报(monthly)/
年报(annual) 三级报告体系。

新公共接口：
- ReportSystem: 报告系统编排层（替代 MemorySystem，主入口）
- ReportStore: 报告存储层（另个任务实现）
- ReportGenerator: 报告生成器（另个任务实现）

保留的旧接口（向后兼容，标注 deprecated）：
- MemorySystem: 旧三层记忆系统（现已别名为 ReportSystem）
- WorkingMemory: L1 工作记忆
- L2Store: L2 短期记忆
- L3Store: L3 长期记忆
- MemoryCompressor: 旧记忆压缩器
- ForgettingMechanism: 旧遗忘机制
- MemoryManager: 旧记忆管理器

通用组件（新旧共用）：
- RecallScorer: 多因子召回评分器
- RecallWeights: 三因子权重配置
- ScoreBreakdown: 评分明细数据类
"""

# ─── 新体系导出 ──────────────────────────────────────────────────
from .system import ReportSystem
from .report_store import ReportStore
from .report_generator import ReportGenerator

# ─── 旧体系导出（向后兼容） ────────────────────────────────────
from .recall_scorer import RecallScorer, RecallWeights, ScoreBreakdown
from .working import WorkingMemory

# MemorySystem 是 ReportSystem 的别名
from .system import MemorySystem  # noqa: F401 — 向后兼容

from .l2_store import L2Store
from .l3_store import L3Store
from .compressor import MemoryCompressor
from .forgetting import ForgettingMechanism
from .manager import MemoryManager

__all__ = [
    # ReportSystem (新体系主入口)
    "ReportSystem",
    # RecallScorer (Phase B2)
    "RecallScorer", "RecallWeights", "ScoreBreakdown",
    # Working Memory 三组件 (Phase B4)
    "WorkingMemory",
    # Memory System (向后兼容别名)
    "MemorySystem",
    # Stores
    "L2Store", "L3Store", "ReportStore",
    # Compressor / Forgetting / Manager
    "MemoryCompressor", "ForgettingMechanism", "MemoryManager",
    # Report Generator
    "ReportGenerator",
]
