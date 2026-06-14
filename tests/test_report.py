# -*- coding: utf-8 -*-
"""F013 回测报表系统测试"""

import os
import tempfile
import json

import pytest

from stockquant.analytics import ReportGenerator
from stockquant.ai import BacktestAgent


class TestReportGenerator:
    """报表生成器测试"""

    @pytest.fixture
    def sample_results(self):
        """模拟回测结果"""
        return [
            {
                "name": "Test Strategy",
                "metrics": {
                    "Total Return": "15.50%",
                    "Annualized Return": "12.30%",
                    "Max Drawdown": "8.20%",
                    "Sharpe Ratio": "1.2345",
                    "Sortino Ratio": "1.8765",
                    "Calmar Ratio": "1.5000",
                    "Win Rate": "55.0%",
                    "Profit Factor": "1.30",
                    "Total Trades": 50,
                    "SQN (System Quality Number)": "1.5000",
                    "Kelly %": "5.00%",
                    "VaR (95%)": "2.00%",
                    "CVaR (95%)": "3.50%",
                },
                "trades": [
                    {
                        "trade_id": f"t{i}",
                        "symbol": "sh600519",
                        "side": "Buy" if i % 2 == 0 else "Sell",
                        "price": 100.0 + i,
                        "quantity": 100,
                    }
                    for i in range(20)
                ],
                "equity_curve": [
                    (1_000_000.0 + i * 1000, i)
                    for i in range(100)
                ],
            }
        ]

    def test_generate_summary(self, sample_results):
        """控制台摘要报告"""
        summary = ReportGenerator.generate_summary(sample_results)
        assert "Test Strategy" in summary
        assert "15.50%" in summary
        assert "1.2345" in summary
        assert "50" in summary

    def test_generate_html(self, sample_results):
        """HTML 报表生成"""
        html = ReportGenerator.generate_html(sample_results)
        assert "<!DOCTYPE html>" in html
        assert "Test Strategy" in html
        assert "15.50%" in html
        assert "Sharpe Ratio" in html
        assert "equity" in html.lower()

    def test_generate_html_file(self, sample_results):
        """HTML 报表保存到文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "report.html")
            ReportGenerator.generate_html(sample_results, output_path=path)
            assert os.path.exists(path)
            content = open(path, encoding="utf-8").read()
            assert len(content) > 1000
            assert "Test Strategy" in content

    def test_generate_json(self, sample_results):
        """JSON 报表生成"""
        json_str = ReportGenerator.generate_json(sample_results)
        data = json.loads(json_str)
        assert data["report_type"] == "StockQuant Backtest Report"
        assert len(data["strategies"]) == 1
        assert data["strategies"][0]["name"] == "Test Strategy"
        assert "15.50%" in data["strategies"][0]["metrics"]["Total Return"]

    def test_generate_json_file(self, sample_results):
        """JSON 报表保存到文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "report.json")
            ReportGenerator.generate_json(sample_results, output_path=path)
            assert os.path.exists(path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert len(data["strategies"]) == 1

    def test_empty_results(self):
        """空结果处理"""
        summary = ReportGenerator.generate_summary([])
        assert "StockQuant" in summary

        report = BacktestAgent().analyze([])
        assert "未提供" in report["summary"]

    def test_equity_chart_data_downsample(self):
        """权益曲线降采样"""
        from stockquant.analytics.report import ReportGenerator as RG

        # 生成 1000 个数据点
        curve = [(1_000_000 + i * 100, i) for i in range(1000)]
        downsamped = RG._downsample_equity(curve, 500)
        assert len(downsamped) <= 500
        # 首元素保留
        assert downsamped[0] == curve[0]
        # 尾元素近似保留（可能偏移 1-2 个点）
        assert abs(downsamped[-1][1] - curve[-1][1]) <= 2
