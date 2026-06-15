# -*- coding: utf-8 -*-
"""F016 回测结果仪表盘 — 查看/分析历史回测结果"""

import logging

import streamlit as st

import requests

API_BASE = "http://localhost:8000/api"
logger = logging.getLogger("stockquant.app")

st.set_page_config(page_title="回测结果", page_icon="📈", layout="wide")
st.title("📈 回测结果仪表盘")
st.caption("F016 — 历史回测结果查看与 AI 解读")

# 加载回测列表
try:
    resp = requests.get(f"{API_BASE}/backtest", timeout=3)
    tasks = resp.json() if resp.ok else []
except Exception:
    tasks = []

if not tasks:
    st.info("暂无回测记录，请先在【回测配置】页面运行回测")
    st.stop()

# 选择回测任务
task_map = {t.get("strategy_name", tid): tid for t in (tid := tasks)}
selected_name = st.selectbox("选择回测任务", list(task_map.keys()))
selected_id = task_map[selected_name]

# 加载详情
try:
    resp = requests.get(f"{API_BASE}/backtest/{selected_id}", timeout=3)
    task = resp.json() if resp.ok else {}
except Exception:
    task = {}

if not task:
    st.error("无法加载回测详情")
    st.stop()

# 关键指标
st.subheader("关键指标")
cols = st.columns(6)
metrics_map = {
    "年化收益": "Annualized Return",
    "最大回撤": "Max Drawdown",
    "夏普比率": "Sharpe Ratio",
    "胜率": "Win Rate",
    "总交易": "Total Trades",
    "SQN": "SQN (System Quality Number)",
}

for i, (label, key) in enumerate(metrics_map.items()):
    val = task.get(key, "N/A")
    cols[i].metric(label, str(val))

# 资金曲线
st.subheader("资金曲线")
equity = task.get("equity_curve", [])
if equity:
    try:
        import pandas as pd
        if isinstance(equity[0], (list, tuple)):
            df = pd.DataFrame(equity, columns=["date", "value"])
        else:
            df = pd.DataFrame(equity, columns=["value"])
        st.line_chart(df.set_index("date") if "date" in df.columns else df)
    except Exception:
        st.json(equity)
else:
    st.info("暂无资金曲线数据")

# 回撤曲线
st.subheader("回撤曲线")
try:
    import numpy as np
    if equity:
        values = [float(p[1]) if isinstance(p, (list, tuple)) else float(p) for p in equity]
        peak = np.maximum.accumulate(values)
        drawdown = [(v - p) / max(abs(p), 1) * 100 for v, p in zip(values, peak)]
        if drawdown:
            import pandas as pd
            st.area_chart(pd.DataFrame(drawdown, columns=["回撤%"]).set_index(pd.RangeIndex(len(drawdown))))
except Exception:
    st.info("无法绘制回撤曲线")

# 月度收益
st.subheader("月度收益")
st.info("月度收益热力图待接入真实回测数据后显示。")

# AI 解读
st.subheader("🤖 AI 解读")
if task.get("task_id"):
    if st.button("请求 AI 解读..."):
        with st.spinner("AI 正在分析..."):
            try:
                resp = requests.post(
                    f"{API_BASE}/chat",
                    json={
                        "conversation_id": "system",
                        "message": f"解读回测任务 {task.get('task_id')} 的结果，策略: {task.get('strategy_name')}",
                    },
                    timeout=15,
                )
                if resp.ok:
                    result = resp.json()
                    st.info(result.get("reply", result.get("content", "暂无解读")))
                else:
                    st.warning("AI 解读不可用")
            except Exception as e:
                st.error(f"AI 解读失败: {e}")
else:
    st.info("请先运行回测获取结果后再生成 AI 解读")
