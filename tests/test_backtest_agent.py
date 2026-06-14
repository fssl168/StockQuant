# -*- coding: utf-8 -*-
"""F023 AI 回测解读 Agent 测试"""

import pytest

from stockquant.ai import BacktestAgent


class TestBacktestAgent:
    """AI 回测解读 Agent 测试"""

    @pytest.fixture
    def good_strategy_results(self):
        """表现良好的回测结果"""
        return [
            {
                "name": "Good Strategy",
                "metrics": {
                    "Total Return": "25.50%",
                    "Annualized Return": "18.30%",
                    "Max Drawdown": "8.20%",
                    "Sharpe Ratio": "1.8765",
                    "Sortino Ratio": "2.5000",
                    "Calmar Ratio": "2.2340",
                    "Win Rate": "62.0%",
                    "Profit Factor": "1.80",
                    "Total Trades": 45,
                    "SQN (System Quality Number)": "2.5000",
                    "Kelly %": "8.50%",
                    "VaR (95%)": "1.50%",
                    "CVaR (95%)": "2.80%",
                    "Beta": "0.85",
                    "Alpha": "5.20%",
                },
                "trades": [
                    {"trade_id": "t1", "symbol": "sh600519", "side": "Buy", "price": 1800.0, "quantity": 100},
                    {"trade_id": "t2", "symbol": "sh600519", "side": "Sell", "price": 1850.0, "quantity": 100},
                ],
                "equity_curve": [(1_000_000 + i * 200, i) for i in range(100)],
            }
        ]

    @pytest.fixture
    def bad_strategy_results(self):
        """表现糟糕的回测结果"""
        return [
            {
                "name": "Bad Strategy",
                "metrics": {
                    "Total Return": "-15.30%",
                    "Annualized Return": "-12.30%",
                    "Max Drawdown": "45.20%",
                    "Sharpe Ratio": "-0.5000",
                    "Sortino Ratio": "-1.2000",
                    "Calmar Ratio": "-0.2700",
                    "Win Rate": "35.0%",
                    "Profit Factor": "0.60",
                    "Total Trades": 620,
                    "SQN (System Quality Number)": "0.5000",
                    "Kelly %": "0.00%",
                    "VaR (95%)": "5.20%",
                    "CVaR (95%)": "8.10%",
                },
                "trades": [
                    {"trade_id": "t1", "symbol": "sh600519", "side": "Buy", "price": 1800.0, "quantity": 100},
                ],
                "equity_curve": [(1_000_000 - i * 100, i) for i in range(100)],
            }
        ]

    def test_analyze_good_strategy(self, good_strategy_results):
        """良好策略的解读"""
        agent = BacktestAgent()
        report = agent.analyze(good_strategy_results)

        assert "回测" in report["summary"]
        assert len(report["issues"]) < 3  # 问题应该很少
        assert len(report["suggestions"]) > 0  # 建议应该存在

    def test_analyze_bad_strategy(self, bad_strategy_results):
        """糟糕策略的解读 — 应该发现问题"""
        agent = BacktestAgent()
        report = agent.analyze(bad_strategy_results)

        assert len(report["issues"]) >= 3  # 至少发现 3 个问题

        # 应该检测到关键问题
        issue_text = " ".join(report["issues"])
        assert "回撤" in issue_text or "夏普" in issue_text

    def test_analyze_empty(self):
        """空结果处理"""
        agent = BacktestAgent()
        report = agent.analyze([])

        assert "未提供" in report["summary"]
        assert report["issues"] == []
        assert report["suggestions"] == []

    def test_multi_strategy_analysis(self):
        """多策略对比分析"""
        agent = BacktestAgent()
        results = [
            {
                "name": "Strategy A",
                "metrics": {
                    "Total Return": "25.50%",
                    "Annualized Return": "18.30%",
                    "Max Drawdown": "8.20%",
                    "Sharpe Ratio": "1.8765",
                    "Win Rate": "62.0%",
                    "Profit Factor": "1.80",
                    "Total Trades": 45,
                    "SQN (System Quality Number)": "2.5000",
                    "Kelly %": "8.50%",
                    "VaR (95%)": "1.50%",
                },
                "trades": [],
                "equity_curve": [(1_000_000 + i * 200, i) for i in range(100)],
            },
            {
                "name": "Strategy B",
                "metrics": {
                    "Total Return": "-5.30%",
                    "Annualized Return": "-4.30%",
                    "Max Drawdown": "25.20%",
                    "Sharpe Ratio": "-0.8000",
                    "Win Rate": "35.0%",
                    "Profit Factor": "0.60",
                    "Total Trades": 150,
                    "SQN (System Quality Number)": "0.8000",
                    "Kelly %": "0.00%",
                    "VaR (95%)": "4.20%",
                },
                "trades": [],
                "equity_curve": [(1_000_000 - i * 100, i) for i in range(100)],
            },
        ]

        report = agent.analyze(results)

        assert "2" in report["summary"]  # 应该提到 2 个策略
        assert "Strategy A" in report["dimensions"]
        assert "Strategy B" in report["dimensions"]
        assert len(report["issues"]) > 1  # 至少检测到 Strategy B 的问题

    def test_identify_issues_over_drawdown(self):
        """检测到过大回撤"""
        agent = BacktestAgent()
        metrics = {
            "Max Drawdown": "35.00%",
            "Sharpe Ratio": "1.0",
            "Win Rate": "50.0%",
            "Total Trades": 100,
        }
        issues = agent._identify_issues(metrics)
        assert len(issues) >= 1
        assert "回撤" in issues[0]

    def test_identify_issues_low_winrate(self):
        """检测到过低胜率"""
        agent = BacktestAgent()
        metrics = {
            "Max Drawdown": "10.00%",
            "Sharpe Ratio": "1.0",
            "Win Rate": "30.0%",
            "Total Trades": 50,
        }
        issues = agent._identify_issues(metrics)
        assert any("胜率" in i for i in issues)

    def test_identify_issues_overtrading(self):
        """检测到过度交易"""
        agent = BacktestAgent()
        metrics = {
            "Max Drawdown": "10.00%",
            "Sharpe Ratio": "1.0",
            "Win Rate": "50.0%",
            "Total Trades": 600,
        }
        issues = agent._identify_issues(metrics)
        assert any("交易次数" in i or "过度" in i for i in issues)

    def test_generate_suggestions(self):
        """生成改进建议"""
        agent = BacktestAgent()
        issues = [
            "最大回撤 35% 超过 30% 警戒线",
            "胜率 30% 偏低",
        ]
        suggestions = agent._generate_suggestions({}, issues)
        assert len(suggestions) >= 2
        assert any("止损" in s or "仓位" in s for s in suggestions)
        assert any("确认" in s or "过滤" in s or "胜率" in s for s in suggestions)

    def test_multi_dimension_analysis(self):
        """多维度分析"""
        agent = BacktestAgent()
        metrics = {
            "Annualized Return": "18.30%",
            "Max Drawdown": "8.20%",
            "Sharpe Ratio": "1.8765",
            "Sortino Ratio": "2.5000",
            "Calmar Ratio": "2.2340",
            "Win Rate": "62.0%",
            "Profit Factor": "1.80",
            "Total Trades": 45,
            "SQN (System Quality Number)": "2.5000",
            "Kelly %": "8.50%",
            "VaR (95%)": "1.50%",
            "Beta": "0.85",
            "Alpha": "5.20",
        }
        dims = agent._multi_dimension_analysis(metrics, [])

        assert "performance" in dims
        assert "risk" in dims
        assert "trading" in dims
        assert "quality" in dims
        assert "Beta 0.85" in dims["quality"]
