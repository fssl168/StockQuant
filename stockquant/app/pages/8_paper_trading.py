# -*- coding: utf-8 -*-
"""F016 模拟盘监控 — 持仓与交易记录"""

import logging

import pandas as pd
import streamlit as st

logger = logging.getLogger("stockquant.app")

st.set_page_config(page_title="模拟盘", page_icon="📋", layout="wide")
st.title("📋 模拟盘监控")
st.caption("F016 — 模拟交易持仓、盈亏与交易记录")

# 模拟持仓
st.subheader("持仓汇总")
col1, col2, col3, col4 = st.columns(4)
col1.metric("总资产", "¥1,234,567")
col2.metric("持仓市值", "¥987,654")
col3.metric("可用现金", "¥246,913")
col4.metric("累计盈亏", "+¥123,456 (+11.1%)")

# 个股持仓
st.subheader("个股持仓")
positions = pd.DataFrame([
    {"代码": "sh600519", "名称": "贵州茅台", "数量": 100, "成本价": 1680.00, "现价": 1725.50, "盈亏": 4550.00, "盈亏率": "2.71%"},
    {"代码": "sz000858", "名称": "五粮液", "数量": 500, "成本价": 152.00, "现价": 148.30, "盈亏": -1850.00, "盈亏率": "-2.43%"},
    {"代码": "sh601318", "名称": "中国平安", "数量": 300, "成本价": 45.50, "现价": 47.80, "盈亏": 690.00, "盈亏率": "5.05%"},
], columns=["代码", "名称", "数量", "成本价", "现价", "盈亏", "盈亏率"])

positions["盈亏"] = positions["盈亏"].apply(lambda x: f"{'+' if x > 0 else ''}¥{x:,.2f}")
st.dataframe(positions, use_container_width=True)

# 权益曲线
st.subheader("权益曲线")
import numpy as np
np.random.seed(42)
days = pd.date_range(end=pd.Timestamp.now(), periods=90, freq="D")
equity = 1_000_000 + np.cumsum(np.random.randn(90) * 5000 + 2000)
df_eq = pd.DataFrame({"日期": days, "权益": equity.astype(int)})
st.line_chart(df_eq.set_index("日期"), height=300)

# 交易记录
st.subheader("交易记录")
trades = pd.DataFrame([
    {"时间": "2026-06-01 09:35", "代码": "sh600519", "方向": "买入", "数量": 100, "价格": 1680.00, "金额": 168000.00},
    {"时间": "2026-06-03 14:20", "代码": "sz000858", "方向": "买入", "数量": 500, "价格": 152.00, "金额": 76000.00},
    {"时间": "2026-06-05 10:15", "代码": "sh601318", "方向": "买入", "数量": 300, "价格": 45.50, "金额": 13650.00},
    {"时间": "2026-06-10 11:30", "代码": "sh600519", "方向": "卖出", "数量": 50, "价格": 1710.00, "金额": 85500.00},
], columns=["时间", "代码", "方向", "数量", "价格", "金额"])

st.dataframe(trades, use_container_width=True)
