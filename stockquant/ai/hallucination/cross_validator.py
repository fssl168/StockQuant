# -*- coding: utf-8 -*-
"""F020 反幻觉增强（Phase E2）— 多模型交叉验证

借鉴 AI.cc 研究（单模型 8.3% → 多模型 3.2% 幻觉率，降低 ~61%）。

设计原则：
- 复用现有 LLMAdapter（litellm 多 Provider 路由），不引入新依赖
- 至少 3 个独立模型并行调用，多数投票 + 分歧标记
- 单模型不可用时不阻塞，标记为 unavailable
- 调用方可在 CrossValidator 构造时注入模型列表（便于测试 mock）
- 默认模型列表：gpt-4o-mini / claude-haiku-3 / deepseek-chat（覆盖 OpenAI / Anthropic / DeepSeek 三家）
- 超时保护：每个模型调用 30s 超时，避免卡死整个验证流程

返回结果包含：
- consensus: 共识结论（agree/disagree/insufficient）
- verified: 多数投票是否通过
- conflict: 模型间是否存在分歧
- needs_human_review: 是否需要人工复核
- per_model_results: 每个模型的独立验证结果
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("stockquant.ai.hallucination.cross_validator")


# ── 数据结构 ──────────────────────────────────────────────────────────────


@dataclass
class ModelVerifyResult:
    """单个模型的验证结果

    Attributes:
        model: 模型名称（如 "gpt-4o-mini"）
        verified: 模型是否判定声明为真
        confidence: 模型置信度 [0, 1]
        reasoning: 模型给出的判断理由
        error: 调用失败时的错误信息（None 表示成功）
        duration_ms: 调用耗时（毫秒）
    """
    model: str = ""
    verified: bool = False
    confidence: float = 0.0
    reasoning: str = ""
    error: Optional[str] = None
    duration_ms: int = 0


@dataclass
class VerifyResult:
    """多模型交叉验证的汇总结果

    Attributes:
        claim: 待验证声明
        consensus: 共识状态 (agree=一致 / disagree=分歧 / insufficient=模型不足)
        verified: 多数投票是否通过
        confidence: 平均置信度
        conflict: 是否存在分歧
        needs_human_review: 是否需要人工复核
        per_model_results: 每个模型的独立结果
        decision_rule: 决策规则描述（如 "2/3 agreed: True"）
    """
    claim: str = ""
    consensus: str = "insufficient"  # agree | disagree | insufficient
    verified: bool = False
    confidence: float = 0.0
    conflict: bool = False
    needs_human_review: bool = False
    per_model_results: List[ModelVerifyResult] = field(default_factory=list)
    decision_rule: str = ""


# ── 验证提示词 ──────────────────────────────────────────────────────────


VERIFICATION_PROMPT_TEMPLATE = """你是金融事实核查助手。请判断以下声明是否真实可信。

声明：{claim}

请按 JSON 格式输出，包含以下字段：
- verified: true/false（声明是否真实）
- confidence: 0.0-1.0（你的置信度）
- reasoning: 简短理由（不超过 50 字）

注意：
1. 只输出 JSON，不要有其他文字
2. 数值型声明请检查数字是否合理
3. 时间型声明请检查日期是否合理
4. 监管型声明请检查监管机构是否真实
5. 如不确定，置信度应低于 0.5

输出 JSON 示例：
{{"verified": true, "confidence": 0.8, "reasoning": "声明合理且符合事实"}}
"""


# ── CrossValidator 主类 ──────────────────────────────────────────────────


class CrossValidator:
    """多模型交叉验证器

    用法::

        validator = CrossValidator()
        result = await validator.verify("贵州茅台 2024 年营收同比增长 15%")
        if result.conflict:
            logger.warning("模型分歧，需人工复核")
        if result.verified:
            ...

    可注入模型适配器以便测试::

        mock_openai = MagicMock()
        mock_openai.call.return_value = LLMResponse(content='{"verified": true, ...}')
        validator = CrossValidator(
            model_adapters=[("openai", mock_openai), ("anthropic", mock_anthropic)]
        )
    """

    # 默认模型列表（litellm 路由）
    DEFAULT_MODELS: List[str] = [
        "gpt-4o-mini",       # OpenAI
        "claude-haiku-3-20250307",  # Anthropic
        "deepseek-chat",     # DeepSeek
    ]

    DEFAULT_TIMEOUT_SECONDS: float = 30.0

    def __init__(
        self,
        model_adapters: Optional[List[Tuple[str, Any]]] = None,
        models: Optional[List[str]] = None,
        timeout_seconds: Optional[float] = None,
        min_models_for_consensus: int = 2,
    ) -> None:
        """
        Args:
            model_adapters: 显式注入 (model_name, adapter) 列表（测试用）；
                           不提供时使用 models 列表自动构造 LLMAdapter
            models: 自动构造 LLMAdapter 时使用的模型名列表；
                    不提供时使用 DEFAULT_MODELS
            timeout_seconds: 单次 LLM 调用超时
            min_models_for_consensus: 形成共识所需的最少模型数（默认 2）
        """
        if model_adapters:
            self._adapters: List[Tuple[str, Any]] = list(model_adapters)
        else:
            # 延迟导入避免循环依赖
            from stockquant.agent.llm_adapter import LLMAdapter
            model_list = models or self.DEFAULT_MODELS
            self._adapters = [(name, LLMAdapter(model=name)) for name in model_list]

        self._timeout = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS
        self._min_for_consensus = max(2, min_models_for_consensus)

    async def verify(self, claim: str) -> VerifyResult:
        """多模型交叉验证单个声明

        Args:
            claim: 待验证声明文本

        Returns:
            VerifyResult 汇总结果
        """
        if not claim or not claim.strip():
            return VerifyResult(claim=claim, consensus="insufficient",
                                decision_rule="声明为空")

        # 并行调用所有模型
        tasks = [
            self._verify_with_model(claim, name, adapter)
            for name, adapter in self._adapters
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        return self._aggregate(claim, results)

    async def verify_batch(self, claims: List[str]) -> List[VerifyResult]:
        """批量验证多个声明（串行，避免触发 LLM 限流）

        Args:
            claims: 声明列表

        Returns:
            验证结果列表，顺序与输入一致
        """
        out: List[VerifyResult] = []
        for c in claims:
            r = await self.verify(c)
            out.append(r)
        return out

    # ── 单模型调用 ──────────────────────────────────────────────────────

    async def _verify_with_model(
        self,
        claim: str,
        model_name: str,
        adapter: Any,
    ) -> ModelVerifyResult:
        """使用单个模型验证声明

        Args:
            claim: 待验证声明
            model_name: 模型名（用于结果标注）
            adapter: LLMAdapter 实例或 mock（必须有 .call(messages) 方法）

        Returns:
            ModelVerifyResult
        """
        import time
        t_start = time.monotonic()

        try:
            prompt = VERIFICATION_PROMPT_TEMPLATE.format(claim=claim)
            messages = [
                {"role": "system", "content": "你是金融事实核查助手，只输出 JSON。"},
                {"role": "user", "content": prompt},
            ]

            # 调用 adapter.call — LLMAdapter.call 是同步方法，需要 to_thread
            # 但 mock 可能直接返回，await 对非协程会抛 TypeError
            # 用 try/except 兼容两种调用方式
            response = await self._invoke_adapter(adapter, messages)

            duration_ms = int((time.monotonic() - t_start) * 1000)
            content = getattr(response, "content", "") or str(response)

            # 解析 JSON
            parsed = self._parse_json_response(content)
            if parsed is None:
                return ModelVerifyResult(
                    model=model_name,
                    verified=False,
                    confidence=0.0,
                    error=f"无法解析 JSON 响应: {content[:100]}",
                    duration_ms=duration_ms,
                )

            return ModelVerifyResult(
                model=model_name,
                verified=bool(parsed.get("verified", False)),
                confidence=float(parsed.get("confidence", 0.0)),
                reasoning=str(parsed.get("reasoning", "")),
                duration_ms=duration_ms,
            )

        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - t_start) * 1000)
            return ModelVerifyResult(
                model=model_name,
                verified=False,
                confidence=0.0,
                error=f"调用超时 ({self._timeout}s)",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - t_start) * 1000)
            logger.warning("模型 %s 验证异常: %s", model_name, exc)
            return ModelVerifyResult(
                model=model_name,
                verified=False,
                confidence=0.0,
                error=f"异常: {exc}",
                duration_ms=duration_ms,
            )

    async def _invoke_adapter(self, adapter: Any, messages: List[Dict[str, str]]) -> Any:
        """兼容调用 adapter — LLMAdapter.call 是同步方法，mock 可能是协程

        - 若 adapter.call 是协程函数，直接 await
        - 否则用 asyncio.to_thread 包装为协程
        """
        import asyncio as _asyncio
        import inspect

        call_fn = getattr(adapter, "call", None)
        if call_fn is None:
            raise AttributeError("adapter 缺少 call 方法")

        if inspect.iscoroutinefunction(call_fn):
            # 协程函数直接 await
            return await _asyncio.wait_for(
                call_fn(messages), timeout=self._timeout
            )

        # 同步方法用 to_thread 包装
        return await _asyncio.wait_for(
            _asyncio.to_thread(call_fn, messages), timeout=self._timeout
        )

    # ── JSON 解析 ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_json_response(content: str) -> Optional[Dict[str, Any]]:
        """从 LLM 响应中解析 JSON

        LLM 可能输出 ```json ... ``` 或前后带文字的 JSON。
        """
        if not content:
            return None

        # 直接尝试
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            pass

        # 提取 ```json ... ``` 块
        import re
        m = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', content)
        if m:
            try:
                return json.loads(m.group(1))
            except (json.JSONDecodeError, TypeError):
                pass

        # 提取第一个 { ... } 块
        m = re.search(r'\{[\s\S]+\}', content)
        if m:
            try:
                return json.loads(m.group(0))
            except (json.JSONDecodeError, TypeError):
                pass

        return None

    # ── 聚合策略 ────────────────────────────────────────────────────────

    def _aggregate(
        self,
        claim: str,
        results: List[ModelVerifyResult],
    ) -> VerifyResult:
        """汇总多个模型结果，按多数投票决策

        决策规则：
        - 有效模型（无 error）少于 min_for_consensus → insufficient
        - 多数（>50%）verified=True → verified=True, consensus=agree
        - 多数 verified=False → verified=False, consensus=agree
        - 平票或分歧较大 → consensus=disagree, needs_human_review=True
        """
        valid = [r for r in results if r.error is None]
        n_valid = len(valid)
        n_total = len(results)

        if n_valid < self._min_for_consensus:
            return VerifyResult(
                claim=claim,
                consensus="insufficient",
                verified=False,
                confidence=0.0,
                needs_human_review=True,
                per_model_results=results,
                decision_rule=(
                    f"有效模型 {n_valid}/{n_total} 不足 {self._min_for_consensus}"
                ),
            )

        # 多数投票
        votes_true = sum(1 for r in valid if r.verified)
        votes_false = n_valid - votes_true
        majority_threshold = n_valid / 2  # 严格大于半数

        if votes_true > majority_threshold:
            consensus = "agree"
            verified = True
            conflict = votes_false > 0  # 仍有少数反对
            rule = f"{votes_true}/{n_valid} 同意: True"
        elif votes_false > majority_threshold:
            consensus = "agree"
            verified = False
            conflict = votes_true > 0
            rule = f"{votes_false}/{n_valid} 同意: False"
        else:
            # 平票
            consensus = "disagree"
            verified = False
            conflict = True
            rule = f"平票: {votes_true} vs {votes_false}"

        avg_conf = sum(r.confidence for r in valid) / n_valid
        needs_human = conflict or consensus == "disagree"

        return VerifyResult(
            claim=claim,
            consensus=consensus,
            verified=verified,
            confidence=round(avg_conf, 3),
            conflict=conflict,
            needs_human_review=needs_human,
            per_model_results=results,
            decision_rule=rule,
        )


# ── 模块级便捷函数 ──────────────────────────────────────────────────────


_default_validator: Optional[CrossValidator] = None


async def multi_model_verify(
    claim: str,
    model_adapters: Optional[List[Tuple[str, Any]]] = None,
) -> VerifyResult:
    """多模型交叉验证（模块级便捷函数）

    用法::

        from stockquant.ai.hallucination.cross_validator import multi_model_verify
        result = await multi_model_verify("贵州茅台 2024 年营收同比增长 15%")
        assert result.conflict is False or result.needs_human_review

    Args:
        claim: 待验证声明
        model_adapters: 可选，注入适配器列表用于测试

    Returns:
        VerifyResult 汇总结果
    """
    global _default_validator
    if model_adapters:
        validator = CrossValidator(model_adapters=model_adapters)
        return await validator.verify(claim)

    if _default_validator is None:
        _default_validator = CrossValidator()
    return await _default_validator.verify(claim)


def reset_default_validator() -> None:
    """重置模块级默认验证器（测试用）"""
    global _default_validator
    _default_validator = None
