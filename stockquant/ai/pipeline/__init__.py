# -*- coding: utf-8 -*-
"""F020 AI 信息处理全流程 — 4 阶段流水线 + 记忆系统 + 反幻觉系统

公共接口：
- CollectionStage: 采集阶段（多源并行采集 + 来源验证 + 去重）
- RawArticle: 原始文章数据结构
- DenoiseStage: 降噪阶段（5 步：时序过滤 + 去重 + 信源排序 + L3 噪音过滤 + 已证伪过滤）
- SummarizeStage: 总结阶段（6 步：记忆检索 + Prompt 约束 + LLM 总结 + 多级摘要 + 五步验证 + 回写）
- ElevateStage: 升华阶段（5 步：L3 检索 + 多源融合 + 推理链验证 + 交叉验证 + L3 回写）

注意：InformationProcessingPipeline 位于 stockquant.ai.pipeline_orchestrator，
不在本目录内，使用时请直接从该路径导入。
"""
from .collection import CollectionStage, RawArticle, CollectionEvent
from .denoise import DenoiseStage
from .summarize import SummarizeStage
from .elevate import ElevateStage

__all__ = [
    # Collection
    "CollectionStage", "RawArticle", "CollectionEvent",
    # Stages
    "DenoiseStage",
    "SummarizeStage",
    "ElevateStage",
]
