# -*- coding: utf-8 -*-
"""回测配置页面"""

import json
import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st

from stockquant import Cerebro, BaseStrategy, BacktestBroker, CommissionInfo

logger = logging.getLogger("stockquant.app")


st.set_page_config(page_title="回测配置", layout="wide")
st.title("回测配置")

# 侧边栏配置
with st.sidebar:
    st.header("参数设置")
    symbol = st.text_input("股票代码", value="sh600519")
    fast_period = st.number_input("快速均线周期", min_value=2, max_value=50, value=5)
    slow_period = st.number_input("慢速均线周期", min_value=5, max_value=200, value=20)
    start_date = st.date_input("开始日期", datetime.now() - timedelta(days=365))
    end_date = st.date_input("结束日期", datetime.now())
    initial_cash = st.number_input("初始资金", value=1_000_000)
    run_button = st.button("运行回测", type="primary")


class DualMAStrategy(BaseStrategy):
    name = "DualMA"
    parameters = {"fast": 5, "slow": 20}

    def on_start(self):
        self.ma_fast = self.EMA(period=self.parameters["fast"])
        self.ma_slow = self.EMA(period=self.parameters["slow"])

    def on_bar(self, bars):
        if self.ma_fast.crossed_above(self.ma_slow):
            self.order_market(self.data.close[0], 100)
        elif self.ma_fast.crossed_below(self.ma_slow):
            self.close_all()


if run_button:
    with st.spinner("正在运行回测..."):
        try:
            cerebro = Cerebro()
            cerebro.set_broker(BacktestBroker())
            cerebro.set_commission(CommissionInfo())

            # 使用模拟数据
            dates = pd.date_range(end=datetime.now(), periods=500, freq="D")
            np.random.seed(42)
            closes = [100 + i * 0.1 + np.random.randn() * 2 for i in range(500)]
            volumes = [1_000_000 + abs(np.random.randn()) * 200_000 for _ in range(500)]
            df = pd.DataFrame({"close": closes, "volume": volumes}, index=dates)
            from stockquant.data import DataCache
            cerebro.add_data(DataCache(df, symbol=symbol))
            cerebro.add_strategy(DualMAStrategy, fast=fast_period, slow=slow_period)

            results = cerebro.run()
            report = cerebro.show_report(results)

            st.success("回测完成！")

            # 显示关键指标
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("年化收益", f"{report.get('Annualized Return', 'N/A')}")
            with col2:
                st.metric("最大回撤", f"{report.get('Max Drawdown', 'N/A')}")
            with col3:
                st.metric("夏普比率", f"{report.get('Sharpe Ratio', 'N/A')}")
            with col4:
                st.metric("胜率", f"{report.get('Win Rate', 'N/A')}")

            st.subheader("资金曲线")
            equity = report.get("equity_curve", [])
            if equity:
                st.line_chart(equity)

            st.subheader("权益曲线")
            st.json(equity)

        except Exception as exc:
            logger.error("Backtest failed: %s", exc)
            st.error(f"回测失败: {exc}")
