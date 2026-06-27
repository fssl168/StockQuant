# -*- coding: utf-8 -*-
"""F020 FinMem Memory 模块 — 三层分层记忆 + 多因子召回 + Working Memory 三组件

公共接口：
- RecallScorer: FinMem 多因子召回评分器（relevance + recency + importance）
- RecallWeights: 三因子权重配置
- WorkingMemory: Working Memory 三组件（Summarization / Observation / Reflection）
- MemorySystem: 三层记忆系统统一接口（L1/L2/L3）
- L2Store: L2 短期记忆（Shallow 浅层）
- L3Store: L3 长期记忆（Intermediate 中层 + Deep 深层，含 pgvector 向量召回）
- MemoryCompressor: 记忆压缩器（接入 LLM 生成摘要）
- ForgettingMechanism: 遗忘机制
- MemoryManager: 跨层记忆管理器
"""
from .recall_scorer import RecallScorer, RecallWeights, ScoreBreakdown
from .working import WorkingMemory
from .system import MemorySystem
from .l2_store import L2Store
from .l3_store import L3Store
from .compressor import MemoryCompressor
from .forgetting import ForgettingMechanism
from .manager import MemoryManager

__all__ = [
    # RecallScorer (Phase B2)
    "RecallScorer", "RecallWeights", "ScoreBreakdown",
    # Working Memory 三组件 (Phase B4)
    "WorkingMemory",
    # Memory System
    "MemorySystem",
    # Stores
    "L2Store", "L3Store",
    # Compressor / Forgetting / Manager
    "MemoryCompressor", "ForgettingMechanism", "MemoryManager",
]
