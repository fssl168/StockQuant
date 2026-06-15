# -*- coding: utf-8 -*-
"""F016 数据浏览器 — 加载/查看/下载行情数据"""

import logging

import pandas as pd
import streamlit as st

import requests

API_BASE = "http://localhost:8000/api"
logger = logging.getLogger("stockquant.app")

st.set_page_config(page_title="数据浏览器", page_icon="🔍", layout="wide")
st.title("🔍 数据浏览器")
st.caption("F016 — 查询、浏览和下载行情数据")

# 数据源选择
col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    symbol = st.text_input("股票代码", value="sh600519")
with col2:
    days = st.number_input("查询天数", min_value=1, max_value=500, value=60)
with col3:
    load_btn = st.button("加载数据", type="primary")

if load_btn and symbol:
    try:
        resp = requests.post(
            f"{API_BASE}/chat",
            json={"conversation_id": "system", "message": f"查询 {symbol} 最近 {days} 天行情"},
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            st.info("AI 对话已记录，请前往 AI 对话页查看完整结果。")
        else:
            st.warning(f"API 未返回有效数据: {resp.status_code}")
    except Exception as e:
        st.warning(f"API 调用失败 ({e})，请使用下方的 mock 模式")

# mock 数据展示
st.divider()
st.subheader("本地模拟数据预览")
np = __import__("numpy")
np.random.seed(hash(symbol) % 2**31)
dates = pd.date_range(end=pd.Timestamp.now(), periods=min(days, 100), freq="D")
closes = [100 + i * 0.05 + np.random.randn() * 1.5 for i in range(len(dates))]
volumes = [int(1_000_000 + abs(np.random.randn()) * 200_000) for _ in range(len(dates))]
df = pd.DataFrame({"close": closes, "volume": volumes}, index=dates)
df.index.name = "date"

st.dataframe(df, use_container_width=True)

col_a, col_b = st.columns(2)
with col_a:
    csv_data = df.to_csv().encode("utf-8")
    st.download_button("下载 CSV", data=csv_data, file_name=f"{symbol}_data.csv", mime="text/csv")

with col_b:
    parquet_data = df.to_parquet()
    st.download_button("下载 Parquet", data=parquet_data, file_name=f"{symbol}_data.parquet", mime="application/octet-stream")

# 统计信息
st.markdown("**统计摘要**")
c = st.columns(5)
c[0].metric("最新收盘价", f"{closes[-1]:.2f}" if closes else "N/A")
c[1].metric("区间最高", f"{max(closes):.2f}" if closes else "N/A")
c[2].metric("区间最低", f"{min(closes):.2f}" if closes else "N/A")
c[3].metric("平均成交量", f"{sum(volumes)//len(volumes):,}" if volumes else "N/A")
c[4].metric("数据行数", len(df))
