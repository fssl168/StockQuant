# -*- coding: utf-8 -*-
"""F027 策略对比页面 — 多策略横向对比 + 组合优化建议"""

import json
from pathlib import Path

import streamlit as st

import requests

API_BASE = "http://localhost:8000/api"

st.set_page_config(page_title="策略对比", page_icon="📊", layout="wide")
st.title("📊 策略回测对比")
st.caption("F027 — 横向对比多个策略的优劣，推荐最优组合比例")

# ── 侧边栏：选择策略 ──
st.sidebar.header("选择策略")

# 从 API 获取历史回测列表
try:
    resp = requests.get(f"{API_BASE}/backtest", timeout=3)
    tasks = resp.json() if resp.ok else []
except Exception:
    tasks = []

if tasks:
    selected_ids = st.sidebar.multiselect(
        "回测任务",
        options=[t.get("task_id", "") for t in tasks],
        format_func=lambda x: next(
            (t.get("strategy_name", x) for t in tasks if t.get("task_id") == x), x
        ),
        max_selections=5,
    )
else:
    selected_ids = []
    st.sidebar.warning("暂无回测记录，请先运行回测任务")

# ── 主区域 ──
if len(selected_ids) >= 2:
    if st.button("开始对比", type="primary"):
        with st.spinner("正在对比分析..."):
            try:
                resp = requests.post(
                    f"{API_BASE}/comparison",
                    json={"strategy_ids": selected_ids},
                    timeout=10,
                )
                if resp.ok:
                    data = resp.json()
                    st.subheader("📋 对比结果")

                    # 排名表格
                    rankings = data.get("rankings", {})
                    if rankings:
                        st.markdown("**指标排名**")
                        rows = []
                        for metric, entries in rankings.items():
                            for rank, (name, val) in enumerate(entries, 1):
                                rows.append({"指标": metric, "排名": rank, "策略": name, "值": val})
                        import pandas as pd
                        st.dataframe(pd.DataFrame(rows), use_container_width=True)

                    # 组合权重
                    weights = data.get("portfolio_weights", {})
                    if weights:
                        st.markdown("**建议组合权重**")
                        import pandas as pd
                        st.bar_chart(
                            pd.DataFrame(list(weights.values()), index=weights.keys(), columns=["权重"])
                        )

                    # 相关性矩阵
                    corr = data.get("correlation_matrix", {})
                    if corr:
                        st.markdown("**收益相关性**")
                        corr_rows = []
                        for (s1, s2), v in corr.items():
                            corr_rows.append({"策略 A": s1, "策略 B": s2, "相关系数": v})
                        st.dataframe(pd.DataFrame(corr_rows), use_container_width=True)

                    # 近期表现
                    recent = data.get("recent_performance", {})
                    if recent:
                        st.markdown("**近期表现（最近 20 天）**")
                        rec_rows = []
                        for name, p in recent.items():
                            rec_rows.append({
                                "策略": name,
                                "近期收益(%)": p.get("recent_return", 0),
                                "近期回撤(%)": p.get("recent_drawdown", 0),
                            })
                        st.dataframe(pd.DataFrame(rec_rows), use_container_width=True)

                    # 建议
                    recs = data.get("recommendations", [])
                    if recs:
                        st.markdown("**AI 建议**")
                        for r in recs:
                            st.info(r)

                else:
                    st.error(f"对比失败: {resp.text}")
            except Exception as e:
                st.error(f"API 调用失败: {e}")
else:
    st.info("请在左侧选择至少 2 个回测策略进行对比")
