# -*- coding: utf-8 -*-
"""本地模型管理器 — 基于 HuggingFace transformers 的轻量推理

用于 < 200ms 延迟要求的轻量决策场景（NFR008），例如：
- 情感分析（sentiment-analysis）
- 简单文本分类（text-classification）

与 LocalLLMAdapter（text-generation 生成式任务）和 LocalRuleEngine（纯数学指标）
形成三级本地推理体系：

    1. LocalRuleEngine      — 纯数学，< 50ms，Tick 级信号
    2. LocalModelManager    — transformers 分类，< 200ms，文本级情感/分类
    3. LocalLLMAdapter      — transformers/Ollama 生成，> 200ms，复杂推理
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger("stockquant.ai.local_model")

# 默认模型 — DistilBERT 微调于 SST-2 情感分析任务，模型小、推理快
_DEFAULT_MODEL = "distilbert-base-uncased-finetuned-sst-2-english"

# 轻量决策延迟阈值（毫秒）
_LIGHTWEIGHT_LATENCY_THRESHOLD_MS = 200


class LocalModelManager:
    """本地模型管理器 — 管理 HuggingFace transformers pipeline 的加载与推理

    特性：
    - 懒加载：``__init__`` 不立即加载模型，首次 ``classify`` 时按需加载
    - 线程安全：使用 ``threading.Lock`` 保护模型加载与推理过程
    - 优雅降级：transformers 未安装时 ``is_available()`` 返回 False，
      ``classify`` 返回 None，不影响上层调用链
    - 多模型缓存：不同 ``model_name`` 的 pipeline 缓存复用，避免重复加载

    典型用法::

        mgr = LocalModelManager()
        if mgr.is_available():
            result = mgr.classify("市场情绪乐观，板块普涨")
            # result = {"label": "POSITIVE", "score": 0.98}
    """

    def __init__(self, default_model: str = _DEFAULT_MODEL) -> None:
        """初始化本地模型管理器（不立即加载模型）。

        Parameters
        ----------
        default_model : str
            默认模型名称，首次调用 ``classify`` 时懒加载。
        """
        self._default_model = default_model
        # pipeline 缓存：{model_name: pipeline_object}
        self._pipelines: Dict[str, Any] = {}
        # 线程锁：保护 _pipelines 的读写及推理过程
        self._lock = threading.Lock()
        # transformers 是否可用（惰性检查，首次调用 is_available 时确定）
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """检查 transformers 是否可用。

        Returns
        -------
        bool
            True 表示 transformers 已安装且可导入；False 表示不可用。
            结果会缓存，避免重复导入检查。
        """
        if self._available is None:
            try:
                import transformers  # noqa: F401
                self._available = True
            except ImportError:
                self._available = False
                logger.warning(
                    "transformers 未安装，LocalModelManager 将优雅降级。"
                    "Install with: pip install transformers torch"
                )
        return self._available

    def load_model(self, model_name: Optional[str] = None) -> Optional[Any]:
        """懒加载指定模型的 pipeline（线程安全）。

        若模型已加载则直接返回缓存；否则从 HuggingFace 加载并缓存。

        Parameters
        ----------
        model_name : str, optional
            模型名称，为 None 时使用默认模型。

        Returns
        -------
        pipeline 或 None
            成功返回 transformers pipeline 对象；
            transformers 不可用或加载失败时返回 None。
        """
        if not self.is_available():
            return None

        target = model_name or self._default_model

        # 双重检查锁：先无锁读缓存，未命中再加锁加载
        if target in self._pipelines:
            return self._pipelines[target]

        with self._lock:
            if target in self._pipelines:
                return self._pipelines[target]

            try:
                from transformers import pipeline
                # 情感分析 / 文本分类任务
                pipe = pipeline(
                    "sentiment-analysis",
                    model=target,
                    device=-1,  # CPU 推理，避免 GPU 依赖
                )
                self._pipelines[target] = pipe
                logger.info("本地模型加载成功: %s", target)
                return pipe
            except Exception as exc:
                logger.error("本地模型加载失败: %s — %s", target, exc)
                return None

    def classify(
        self,
        text: str,
        model_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """文本分类（情感分析），返回 ``{label, score}``。

        适用于轻量决策场景（< 200ms），如新闻标题情感分析、市场舆情分类。

        Parameters
        ----------
        text : str
            待分类的文本。
        model_name : str, optional
            指定模型名称，为 None 时使用默认模型。

        Returns
        -------
        dict 或 None
            成功返回 ``{"label": str, "score": float}``；
            transformers 不可用、文本为空或推理失败时返回 None（优雅降级）。
        """
        if not self.is_available():
            return None

        if not text or not text.strip():
            logger.debug("classify 收到空文本，返回 None")
            return None

        pipe = self.load_model(model_name)
        if pipe is None:
            return None

        try:
            # 加锁保护推理过程（transformers pipeline 非线程安全）
            with self._lock:
                result = pipe(text)

            # pipeline 通常返回 [{"label": "POSITIVE", "score": 0.999}]
            if isinstance(result, list) and result:
                item = result[0]
                if isinstance(item, dict):
                    return {
                        "label": item.get("label", "UNKNOWN"),
                        "score": float(item.get("score", 0.0)),
                    }
            # 某些 pipeline 版本直接返回 dict
            if isinstance(result, dict):
                return {
                    "label": result.get("label", "UNKNOWN"),
                    "score": float(result.get("score", 0.0)),
                }
            logger.warning("classify 返回非预期格式: %r", result)
            return None
        except Exception as exc:
            logger.error("classify 推理失败: text=%s — %s", text[:50], exc)
            return None
