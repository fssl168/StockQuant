# -*- coding: utf-8 -*-
"""F016 风控面板 — 风险参数展示 + 风控触发历史"""

import logging

import pandas as pd
import streamlit as st

logger = logging.getLogger("stockquant.app")

st.set_page_config(page_title="风控面板", page_icon="🛡️", layout="wide")
st.title("🛡️ 风控面板")
st.caption("F016 — 当前风控参数、触发历史、风险指标仪表")

# 风控参数
st.subheader("当前风控参数")
col1, col2, col3, col4 = st.columns(4)
col1.metric("最大仓位比例", "80%")
col2.metric("单笔最大亏损", "2%")
col3.metric("总回撤止损", "15%")
col4.metric("行业集中度上限", "30%")

# 参数表
risk_params = pd.DataFrame([
    {"参数": "最大仓位比例", "阈值": "80%", "当前": "65%", "状态": "正常"},
    {"参数": "单笔最大亏损", "阈值": "2%", "当前": "0.8%", "状态": "正常"},
    {"参数": "总回撤止损", "阈值": "15%", "当前": "-5.2%", "状态": "正常"},
    {"参数": "行业集中度", "阈值": "30%", "当前": "22%", "状态": "正常"},
    {"参数": "单标的最大持仓", "阈值": "20%", "当前": "15%", "状态": "正常"},
    {"参数": "杠杆上限", "阈值": "1.0x", "当前": "1.0x", "状态": "正常"},
], columns=["参数", "阈值", "当前", "状态"])

st.dataframe(risk_params, use_container_width=True)

# 风险指标仪表
st.subheader("风险指标")
import numpy as np
cols = st.columns(4)
cols[0].metric("VaR (95%)", "-1.2%")
cols[1].metric("Beta", "0.85")
cols[2].metric("波动率 (30日)", "18.5%")
cols[3].metric("最大连续亏损", "-4.3%")

# 风控触发历史
st.subheader("风控触发历史")
triggers = pd.DataFrame([
    {"时间": "2026-06-01 14:30", "类型": "回撤预警", "详情": "组合回撤达 -10%", "等级": "黄"},
    {"时间": "2026-05-15 10:15", "类型": "行业集中", "详情": "消费行业占比超 25%", "等级": "蓝"},
    {"时间": "2026-04-20 09:45", "类型": "止损触发", "详情": "个股 sz000858 亏损达 -3%", "等级": "红"},
], columns=["时间", "类型", "详情", "等级"])

st.dataframe(triggers, use_container_width=True)

# 风险图表
st.subheader("回撤追踪")
days = pd.date_range(end=pd.Timestamp.now(), periods=90, freq="D")
np.random.seed(42)
dd = -np.abs(np.cummax(np.random.randn(90) * 0.5) + np.random.randn(90) * 0.2)
df_dd = pd.DataFrame({"日期": days, "回撤%": dd.round(2)})
st.area_chart(df_dd.set_index("日期"), y="回撤%")
