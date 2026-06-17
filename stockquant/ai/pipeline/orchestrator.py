# -*- coding: utf-8 -*-
"""F020 Pipeline Orchestrator — 降噪/总结/升华闭环编排

流水线: Collection → Denoise → Summarize → Elevate
每个阶段之间插入反幻觉检查点
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from stockquant.ai.collectors.base import RawInfoItem
from stockquant.ai.hallucination.pipeline import HallucinationPipeline
from stockquant.ai.hallucination.modes import VerificationMode

from .denoiser import Denoiser
from .summarizer import Summarizer
from .elevator import Elevator

logger = logging.getLogger("stockquant.ai.pipeline.orchestrator")


class PipelineOrchestrator:
    """Pipeline 编排器

    串联四阶段流水线:
    1. Collection — 多源采集
    2. Denoise — 降噪
    3. Summarize — 总结
    4. Elevate — 升华

    每个阶段之间插入反幻觉检查点，确保信息质量。
    """

    def __init__(
        self,
        memory_system: Any = None,
        llm_client: Any = None,
        verification_mode: VerificationMode = VerificationMode.STANDARD,
    ) -> None:
        self._memory = memory_system
        self._hallucination = HallucinationPipeline(strict_mode=False)
        self._verification_mode = verification_mode

        self._denoiser = Denoiser(memory_system=memory_system)
        self._summarizer = Summarizer(memory_system=memory_system, llm_client=llm_client)
        self._elevator = Elevator(
            memory_system=memory_system,
            hallucination_pipeline=self._hallucination,
        )

    def run_full_pipeline(self, symbol: str = "") -> Dict[str, Any]:
        """运行完整流水线: Collection → Denoise → Summarize → Elevate

        Args:
            symbol: 股票代码

        Returns:
            流水线执行结果
        """
        result: Dict[str, Any] = {
            "symbol": symbol,
            "stages": {},
            "checkpoints": {},
            "final": None,
        }

        # Stage 1: Collection
        items = self._collect(symbol)
        result["stages"]["collection"] = {"count": len(items)}

        # Checkpoint: 采集后反幻觉检查
        cp1 = self._anti_hallucination_checkpoint("post_collection", items)
        result["checkpoints"]["post_collection"] = cp1
        if not cp1.get("passed", True):
            logger.warning("采集后检查点未通过: %s", cp1.get("issues", []))

        # Stage 2: Denoise
        denoised = self._denoiser.denoise(items)
        result["stages"]["denoise"] = {"count": len(denoised)}

        # Checkpoint: 降噪后反幻觉检查
        cp2 = self._anti_hallucination_checkpoint("post_denoise", denoised)
        result["checkpoints"]["post_denoise"] = cp2
        if not cp2.get("passed", True):
            logger.warning("降噪后检查点未通过: %s", cp2.get("issues", []))

        # Stage 3: Summarize
        summary = self._summarizer.summarize(denoised)
        result["stages"]["summarize"] = {
            "confidence": summary.get("confidence", 0.0),
            "level": summary.get("level", "session"),
        }

        # Checkpoint: 总结后反幻觉检查
        cp3 = self._anti_hallucination_checkpoint("post_summarize", summary)
        result["checkpoints"]["post_summarize"] = cp3
        if not cp3.get("passed", True):
            logger.warning("总结后检查点未通过: %s", cp3.get("issues", []))

        # Stage 4: Elevate
        elevated = self._elevator.elevate(summary)
        result["stages"]["elevate"] = {
            "insight_count": len(elevated.get("insights", [])),
            "elevated": elevated.get("elevated", False),
        }

        # Checkpoint: 升华后反幻觉检查
        cp4 = self._anti_hallucination_checkpoint("post_elevate", elevated)
        result["checkpoints"]["post_elevate"] = cp4

        # 最终结果
        result["final"] = {
            "summary": elevated.get("summary", summary.get("summary", "")),
            "insights": elevated.get("insights", []),
            "confidence": elevated.get("confidence", summary.get("confidence", 0.0)),
            "elevated": elevated.get("elevated", False),
        }

        logger.info(
            "Pipeline 完成: %s, 采集 %d → 降噪 %d → 置信度 %.2f → 洞察 %d",
            symbol, len(items), len(denoised),
            result["final"]["confidence"],
            len(result["final"]["insights"]),
        )

        return result

    def _collect(self, symbol: str) -> List[RawInfoItem]:
        """执行采集阶段"""
        try:
            from stockquant.ai.orchestrator import get_orchestrator
            import asyncio

            orch = get_orchestrator()
            # 尝试异步采集
            try:
                loop = asyncio.get_running_loop()
                # 已有事件循环，创建任务
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, orch.collect_info(symbol=symbol))
                    return future.result(timeout=30)
            except RuntimeError:
                # 没有事件循环，直接运行
                return asyncio.run(orch.collect_info(symbol=symbol))
        except Exception as exc:
            logger.warning("采集失败，返回空列表: %s", exc)
            return []

    def _anti_hallucination_checkpoint(
        self,
        stage_name: str,
        data: Any,
    ) -> Dict[str, Any]:
        """反幻觉检查点"""
        if isinstance(data, list) and data and isinstance(data[0], RawInfoItem):
            # 对 RawInfoItem 列表进行检查
            items_data = {
                "items": [
                    {
                        "source": it.source,
                        "title": it.title,
                        "content": it.content,
                        "verified": it.verified,
                    }
                    for it in data
                ]
            }
            return self._hallucination.verify(items_data, self._verification_mode)
        elif isinstance(data, dict):
            return self._hallucination.verify(data, self._verification_mode)
        else:
            return {"passed": True, "score": 1.0, "reason": "无可检查数据"}
