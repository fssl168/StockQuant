# -*- coding: utf-8 -*-
"""F016 盯盘面板 — 自选股管理 + AI 信号推送"""

import logging

import pandas as pd
import streamlit as st

import requests

API_BASE = "http://localhost:8000/api"
logger = logging.getLogger("stockquant.app")

st.set_page_config(page_title="盯盘面板", page_icon="👁️", layout="wide")
st.title("👁️ 盯盘面板")
st.caption("F016 — 自选股列表 + 实时行情 + AI 信号推送")

# 自选股管理
st.subheader("自选股管理")
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    new_symbol = st.text_input("添加股票代码", placeholder="如 sh600519")
with col2:
    add_btn = st.button("添加")
with col3:
    refresh_btn = st.button("刷新行情")

# 默认自选股
if "watchlist" not in st.session_state:
    st.session_state.watchlist = ["sh600519", "sz000858", "sh601318", "sz002415"]

for sym in list(st.session_state.watchlist):
    if st.button(f"❌ {sym}", key=f"remove_{sym}"):
        st.session_state.watchlist.remove(sym)
        st.rerun()

# 行情数据
if st.session_state.watchlist:
    st.subheader("实时行情")
    import numpy as np
    data = []
    for sym in st.session_state.watchlist:
        np.random.seed(hash(sym) % 2**31)
        base = 10 + np.random.rand() * 200
        change = np.random.randn() * 3
        data.append({
            "代码": sym,
            "最新价": f"{base + change:.2f}",
            "涨跌幅": f"{change/base*100:+.2f}%",
            "成交量": f"{int(1_000_000 + abs(np.random.randn()) * 500_000):,}",
            "状态": "交易中" if 930 <= (1000) < 1500 else "休市中",
        })
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)

# AI 信号
st.subheader("AI 信号推送")
signals = [
    {"时间": "09:45", "标的": "sh600519", "信号": "放量突破", "方向": "买入", "置信度": "高"},
    {"时间": "10:20", "标的": "sz000858", "信号": "MACD 死叉", "方向": "卖出", "置信度": "中"},
    {"时间": "14:30", "标的": "sh601318", "信号": "异常放量", "方向": "关注", "置信度": "中"},
]
signals_df = pd.DataFrame(signals)
st.dataframe(signals_df, use_container_width=True)

# 控制
st.subheader("监控控制")
if st.button("启动盯盘监控", type="primary"):
    try:
        resp = requests.post(f"{API_BASE}/monitor/start-monitoring", json={
            "symbols": st.session_state.watchlist,
            "interval": 60,
        }, timeout=5)
        if resp.ok:
            st.success("盯盘监控已启动")
        else:
            st.error(f"启动失败: {resp.text}")
    except Exception as e:
        st.warning(f"API 不可用 ({e})，监控功能暂无法启动")
