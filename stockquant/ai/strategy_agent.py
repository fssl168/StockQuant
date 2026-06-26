# -*- coding: utf-8 -*-
"""F022 AI 策略生成与配置 Agent — 自然语言 → 可执行策略代码"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from stockquant.agent.llm_adapter import LLMAdapter
from stockquant.agent.react_agent import ReActAgent, ReActResult
from stockquant.agent.strategy_tools import (
    _make_backtest_strategy,
    _make_generate_strategy_code,
    _make_parse_strategy_intent,
    _make_suggest_improvements,
    score_strategy,
    validate_strategy_code,
)
from stockquant.ai.models import (
    ImprovementSuggestion,
    StrategyGenerationResult,
    StrategyIntent,
    StrategyScore,
    ValidationResult,
)

logger = logging.getLogger("stockquant.ai")


class StrategyAgent:
    """F022 AI 策略生成与配置 Agent。

    用户用自然语言描述策略意图，AI 自动生成可执行的 BaseStrategy 子类代码，
    自动回测验证，评分 + 优化建议。

    用法::

        agent = StrategyAgent(model="deepseek/deepseek-chat", api_key="...")
        result = agent.generate("当MACD金叉且RSI<30时买入，仓位20%，止损5%")
        print(result.code)         # 生成的策略代码
        print(result.score)        # 评分
        print(result.suggestions)  # 优化建议

    Parameters
    ----------
    model : str
        LLM 模型名称（litellm 格式）
    api_key : str | None
        API Key
    fallback_models : list[str] | None
        回退模型列表
    base_url : str | None
        API 基础 URL
    fetcher_manager : Any | None
        DataFetcherManager 实例（用于回测获取数据）
    max_steps : int
        最大推理步数
    """

    SYSTEM_PROMPT = """你是一个专业的 A 股量化策略工程师。你的任务是根据用户的自然语言描述，
生成可在 StockQuant 框架中运行的 BaseStrategy 子类代码。

工作流程（严格按顺序）：
1. **解析策略意图**：调用 parse_strategy_intent 提取技术指标、入场/出场条件、仓位管理、风控参数
2. **生成策略代码**：调用 generate_strategy_code 生成 BaseStrategy 子类代码
3. **验证策略代码**：调用 validate_strategy_code 确保语法正确、导入合法、可实例化
4. **回测验证**：调用 backtest_strategy 使用 Cerebro 引擎运行回测
5. **评分**：调用 score_strategy 从收益/风险/交易质量/稳定性 4 个维度评分
6. **优化建议**：调用 suggest_improvements 基于评分给出具体改进方向

策略代码规范：
- 必须继承 BaseStrategy
- 必须实现 on_start() 和 on_bar()
- 使用 self.SMA/EMA/RSI/MACD/BOLL/ATR/KDJ 等指标方法
- 使用 self.order_market() / self.order_sell() 下单
- 使用 self.log() 记录交易日志

A 股特殊规则：
- 买入数量必须为 100 的整数倍
- T+1 卖出限制
- 涨跌停板限制（10%/20%/30%）
- 佣金万2.5 + 印花税千1

如果验证失败，需要重新生成代码并再次验证，直到通过或达到最大步数。
"""

    def __init__(
        self,
        model: str = "deepseek/deepseek-chat",
        api_key: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        base_url: Optional[str] = None,
        fetcher_manager: Any = None,
        max_steps: int = 15,
    ) -> None:
        self._adapter = LLMAdapter(
            model=model,
            api_key=api_key,
            fallback_models=fallback_models or [],
            base_url=base_url,
        )
        self._fetcher_manager = fetcher_manager
        self._max_steps = max_steps

        # 构建 ReActAgent
        self._react = ReActAgent(
            model=model,
            api_key=api_key,
            fallback_models=fallback_models,
            base_url=base_url,
            max_steps=max_steps,
        )

        # 注册策略生成工具
        self._react.register_tools(
            _make_parse_strategy_intent(self._adapter),
            _make_generate_strategy_code(self._adapter),
            validate_strategy_code,
            _make_backtest_strategy(fetcher_manager),
            score_strategy,
            _make_suggest_improvements(self._adapter),
        )

        # 覆盖系统提示词
        self._react.SYSTEM_PROMPT = self.SYSTEM_PROMPT

    def generate(
        self,
        description: str,
        symbol: str = "sh600519",
        start_date: str = "2023-01-01",
        end_date: str = "2024-12-31",
        cash: float = 1000000.0,
    ) -> StrategyGenerationResult:
        """从自然语言描述生成策略。

        Parameters
        ----------
        description : str
            自然语言策略描述
        symbol : str
            回测标的代码
        start_date : str
            回测开始日期
        end_date : str
            回测结束日期
        cash : float
            初始资金

        Returns
        -------
        StrategyGenerationResult
        """
        query = (
            f"请根据以下策略描述生成可执行的策略代码：\n{description}\n\n"
            f"回测参数：标的={symbol}, 起始={start_date}, 结束={end_date}, 资金={cash:,.0f}"
        )

        result = self._react.run(query)

        return self._parse_react_result(result, description)

    def improve(
        self,
        strategy_code: str,
        backtest_result: Dict[str, Any],
    ) -> StrategyGenerationResult:
        """基于回测结果改进策略。

        Parameters
        ----------
        strategy_code : str
            原始策略代码
        backtest_result : dict
            回测结果

        Returns
        -------
        StrategyGenerationResult
        """
        query = (
            f"请根据以下策略代码和回测结果，优化策略：\n\n"
            f"策略代码：\n```python\n{strategy_code[:2000]}\n```\n\n"
            f"回测结果：{json.dumps(backtest_result, ensure_ascii=False, default=str)[:1000]}"
        )

        result = self._react.run(query)

        return self._parse_react_result(result, "improve")

    def _parse_react_result(
        self, react_result: ReActResult, description: str
    ) -> StrategyGenerationResult:
        """解析 ReAct 推理结果为 StrategyGenerationResult。"""
        gen_result = StrategyGenerationResult()

        if not react_result.success:
            gen_result.success = False
            gen_result.error = react_result.error
            return gen_result

        # 从推理步骤中提取各工具的输出
        for thought in react_result.thoughts:
            if thought.observation:
                obs = thought.observation

                # 提取策略代码
                if thought.action == "generate_strategy_code":
                    gen_result.code = obs

                # 提取验证结果
                elif thought.action == "validate_strategy_code":
                    try:
                        parsed = json.loads(obs)
                        gen_result.validation = ValidationResult(
                            valid=parsed.get("valid", False),
                            errors=parsed.get("errors", []),
                            warnings=parsed.get("warnings", []),
                        )
                    except json.JSONDecodeError:
                        logger.debug("Failed to parse validation result from LLM: %s", obs[:200])

                # 提取回测结果
                elif thought.action == "backtest_strategy":
                    try:
                        gen_result.backtest_result = json.loads(obs)
                    except json.JSONDecodeError:
                        gen_result.backtest_result = {"raw": obs}

                # 提取评分
                elif thought.action == "score_strategy":
                    try:
                        parsed = json.loads(obs)
                        gen_result.score = StrategyScore(
                            total=parsed.get("total", 0),
                            profitability=parsed.get("profitability", 0),
                            risk_control=parsed.get("risk_control", 0),
                            trading_quality=parsed.get("trading_quality", 0),
                            stability=parsed.get("stability", 0),
                            overfitting_risk=parsed.get("overfitting_risk", "medium"),
                        )
                    except json.JSONDecodeError:
                        logger.debug("Failed to parse score from LLM: %s", obs[:200])

                # 提取优化建议
                elif thought.action == "suggest_improvements":
                    try:
                        parsed = json.loads(obs)
                        if isinstance(parsed, list):
                            gen_result.suggestions = [
                                ImprovementSuggestion(
                                    category=s.get("category", "general"),
                                    description=s.get("description", ""),
                                    priority=s.get("priority", "medium"),
                                    code_hint=s.get("code_hint", ""),
                                )
                                for s in parsed
                            ]
                    except json.JSONDecodeError:
                        logger.debug("Failed to parse improvements from LLM: %s", obs[:200])

                # 提取意图
                elif thought.action == "parse_strategy_intent":
                    try:
                        parsed = json.loads(obs)
                        gen_result.intent = StrategyIntent(
                            indicators=parsed.get("indicators", []),
                            entry_conditions=parsed.get("entry_conditions", []),
                            exit_conditions=parsed.get("exit_conditions", []),
                            position_method=parsed.get("position_method", "FixedFraction"),
                            position_params=parsed.get("position_params", {"pct": 0.2}),
                            risk_params=parsed.get("risk_params", {}),
                            description=description,
                        )
                    except json.JSONDecodeError:
                        logger.debug("Failed to parse intent from LLM: %s", obs[:200])

        gen_result.success = bool(gen_result.code)
        return gen_result
