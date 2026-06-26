# -*- coding: utf-8 -*-
"""NLP 情感分析模块 — 增强版关键词规则 + 可选 HuggingFace 模型

三级降级:
1. HuggingFace transformers 模型（可选，需安装 transformers）
2. 增强版关键词规则（金融词典扩展 + 否定词处理 + 程度词加权）
3. 基础关键词匹配（兜底）
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("stockquant.ai.sentiment")


@dataclass
class SentimentResult:
    """情感分析结果"""
    score: float = 0.0  # -1.0 ~ 1.0
    confidence: float = 0.0  # 0.0 ~ 1.0
    key_phrases: List[str] = field(default_factory=list)
    distribution: Dict[str, int] = field(default_factory=lambda: {"positive": 0, "negative": 0, "neutral": 0})
    method: str = "keyword"  # keyword / enhanced_keyword / huggingface


class SentimentAnalyzer:
    """情感分析器 — 增强版关键词规则 + 可选 HuggingFace

    使用方式:
        analyzer = SentimentAnalyzer()
        result = analyzer.analyze("利好消息推动股价大涨")

    降级策略:
        1. 尝试 HuggingFace pipeline（如果 transformers 已安装且模型可用）
        2. 使用增强版关键词规则（金融词典 + 否定词 + 程度词）
        3. 基础关键词匹配（兜底）
    """

    # ── 金融正向词典 ──
    POSITIVE_WORDS = {
        # 基础
        "利好", "上涨", "突破", "新高", "涨停", "大涨", "反弹", "回升", "走强",
        "增长", "盈利", "收益", "分红", "回购", "增持", "买入", "推荐", "看好",
        "超预期", "景气", "繁荣", "牛市", "强势", "领涨", "翻红", "回暖",
        # 扩展
        "业绩大增", "营收增长", "利润飙升", "订单饱满", "产能扩张", "市占率提升",
        "技术突破", "创新高", "量价齐升", "资金流入", "机构增持", "北向流入",
        "政策利好", "行业回暖", "需求旺盛", "供不应求", "景气度上行",
    }

    # ── 金融负向词典 ──
    NEGATIVE_WORDS = {
        # 基础
        "利空", "下跌", "跌破", "新低", "跌停", "大跌", "下挫", "回落", "走弱",
        "亏损", "减值", "减持", "卖出", "规避", "看空", "风险", "暴跌", "崩盘",
        "违约", "退市", "暴雷", "熊市", "弱势", "领跌", "翻绿", "低迷",
        # 扩展
        "业绩下滑", "营收下降", "利润暴跌", "订单萎缩", "产能过剩", "市占率下降",
        "技术破位", "创新低", "量价齐跌", "资金流出", "机构减持", "北向流出",
        "政策收紧", "行业下行", "需求疲软", "供过于求", "景气度下行",
    }

    # ── 否定词 ──
    NEGATION_WORDS = {"不", "未", "没", "无", "非", "别", "莫", "勿", "反", "难以", "无法", "不会"}

    # ── 程度词（加权） ──
    INTENSIFIERS = {
        "大幅": 1.5, "暴涨": 1.8, "暴跌": 1.8, "猛涨": 1.7, "猛跌": 1.7,
        "急剧": 1.6, "显著": 1.4, "明显": 1.3, "略微": 0.7, "小幅": 0.8,
        "微幅": 0.6, "轻微": 0.6, "强烈": 1.5, "极度": 1.8, "严重": 1.6,
        "持续": 1.3, "连续": 1.3, "反复": 1.2, "不断": 1.3,
    }

    # ── HuggingFace 模型配置（备选链：金融专用 → 中文专用 → 多语言）──
    _HF_MODEL_NAME = "ProsusAI/finbert-tone"  # 金融领域专用 FinBERT
    _HF_FALLBACK_MODEL = "uer/roberta-base-finetuned-jd-binary-chinese"  # 中文情感专用
    _HF_FALLBACK_MODEL_2 = "lxyuan/distilbert-base-multilingual-cased-sentiments-student"  # 多语言备选
    _hf_pipeline = None
    _hf_model_loaded: Optional[str] = None

    def __init__(self, method: str = "auto") -> None:
        """初始化情感分析器

        Args:
            method: 分析方法 "auto"(自动降级) / "keyword" / "huggingface"
        """
        self._method = method
        if method in ("auto", "huggingface"):
            self._try_load_hf_model()

    def _try_load_hf_model(self) -> None:
        """尝试加载 HuggingFace 模型（带备选链）

        依次尝试:
        1. 金融领域专用 FinBERT (ProsusAI/finbert-tone) — 英文金融文本最佳
        2. 中文专用模型 (uer/roberta-base-finetuned-jd-binary-chinese)
        3. 多语言备选模型 (lxyuan/distilbert-base-multilingual-cased-sentiments-student)
        4. 全部失败则降级为关键词规则
        """
        candidates = [self._HF_MODEL_NAME, self._HF_FALLBACK_MODEL, self._HF_FALLBACK_MODEL_2]
        for model_name in candidates:
            try:
                from transformers import pipeline
                self._hf_pipeline = pipeline(
                    "sentiment-analysis",
                    model=model_name,
                    top_k=None,
                    device=-1,  # CPU
                )
                self._hf_model_loaded = model_name
                logger.info("HuggingFace 情感模型加载成功: %s", model_name)
                return
            except ImportError:
                logger.info("transformers 未安装，使用增强版关键词规则")
                return
            except Exception as exc:
                logger.warning("HuggingFace 模型 %s 加载失败: %s，尝试备选", model_name, exc)
                continue
        logger.warning("所有 HuggingFace 模型加载失败，降级为关键词规则")

    def analyze(self, texts: List[str]) -> SentimentResult:
        """分析文本列表的情感

        Args:
            texts: 文本列表

        Returns:
            SentimentResult
        """
        if not texts:
            return SentimentResult()

        # 尝试 HuggingFace
        if self._hf_pipeline is not None and self._method != "keyword":
            try:
                return self._analyze_hf(texts)
            except Exception as exc:
                logger.debug("HuggingFace 分析失败: %s，降级为关键词规则", exc)

        # 增强版关键词规则
        return self._analyze_enhanced_keyword(texts)

    def _analyze_hf(self, texts: List[str]) -> SentimentResult:
        """HuggingFace 模型分析

        兼容两种模型输出:
        1. 三分类模型 (positive/negative/neutral) — 多语言备选模型
        2. 二分类模型 (positive/negative) — 中文专用模型
        """
        combined = "。".join(texts[:10])  # 限制长度
        results = self._hf_pipeline(combined[:512])

        # 解析结果（兼容三分类和二分类）
        scores = {}
        raw_results = results[0] if isinstance(results[0], list) else results
        for item in raw_results:
            label = item["label"].lower()
            scores[label] = item["score"]

        pos_score = scores.get("positive", scores.get("pos", 0))
        neg_score = scores.get("negative", scores.get("neg", 0))
        # 二分类模型无 neutral，剩余概率为 neutral
        neu_score = scores.get("neutral", scores.get("neu", max(0, 1 - pos_score - neg_score)))

        sentiment_score = pos_score - neg_score  # -1 ~ 1
        confidence = max(pos_score, neg_score, neu_score)

        return SentimentResult(
            score=round(sentiment_score, 4),
            confidence=round(confidence, 4),
            key_phrases=texts[:5],
            distribution={
                "positive": int(pos_score * 100),
                "negative": int(neg_score * 100),
                "neutral": int(neu_score * 100),
            },
            method=f"huggingface:{self._hf_model_loaded}",
        )

    def _analyze_enhanced_keyword(self, texts: List[str]) -> SentimentResult:
        """增强版关键词规则分析

        改进点:
        1. 金融词典扩展（50+ 正向/负向词）
        2. 否定词处理（"不看好" → 负向）
        3. 程度词加权（"大幅上涨" 权重 > "小幅上涨"）
        4. 短语匹配（"业绩大增" 作为整体匹配）
        """
        total_positive = 0.0
        total_negative = 0.0
        key_phrases = []

        for text in texts:
            if not text:
                continue

            # 按句号/逗号分割
            sentences = re.split(r"[。！？，；\n]", text)

            for sentence in sentences:
                if not sentence.strip():
                    continue

                # 检测程度词
                intensity = 1.0
                for word, weight in self.INTENSIFIERS.items():
                    if word in sentence:
                        intensity = max(intensity, weight)

                # 检测否定词
                has_negation = any(neg in sentence for neg in self.NEGATION_WORDS)

                # 匹配正向词
                for word in self.POSITIVE_WORDS:
                    if word in sentence:
                        if has_negation:
                            total_negative += intensity * 0.8
                            key_phrases.append(f"不{word}")
                        else:
                            total_positive += intensity
                            key_phrases.append(word)

                # 匹配负向词
                for word in self.NEGATIVE_WORDS:
                    if word in sentence:
                        if has_negation:
                            total_positive += intensity * 0.5  # 否定负向 → 弱正向
                            key_phrases.append(f"不{word}")
                        else:
                            total_negative += intensity
                            key_phrases.append(word)

        # 计算综合得分
        total = total_positive + total_negative
        if total == 0:
            return SentimentResult(
                score=0.0,
                confidence=0.0,
                key_phrases=[],
                distribution={"positive": 0, "negative": 0, "neutral": len(texts)},
                method="enhanced_keyword",
            )

        score = (total_positive - total_negative) / total
        confidence = min(total / len(texts), 1.0)

        # 分布
        pos_count = int(total_positive)
        neg_count = int(total_negative)
        neutral_count = max(0, len(texts) - pos_count - neg_count)

        return SentimentResult(
            score=round(max(-1.0, min(1.0, score)), 4),
            confidence=round(confidence, 4),
            key_phrases=list(dict.fromkeys(key_phrases))[:10],  # 去重保留顺序
            distribution={"positive": pos_count, "negative": neg_count, "neutral": neutral_count},
            method="enhanced_keyword",
        )
