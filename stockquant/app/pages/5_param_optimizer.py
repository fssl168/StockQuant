# -*- coding: utf-8 -*-
"""F016 参数优化看板 — 参数扫描与可视化"""

import itertools
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
import streamlit as st

logger = logging.getLogger("stockquant.app")

st.set_page_config(page_title="参数优化", page_icon="🔧", layout="wide")
st.title("🔧 参数优化看板")
st.caption("F016 — 策略参数网格/随机扫描优化")

# 参数配置
st.subheader("优化配置")
col1, col2, col3 = st.columns(3)
with col1:
    param_name = st.text_input("参数名", value="fast_period")
    param_min = st.number_input("最小值", min_value=1, value=2)
    param_max = st.number_input("最大值", min_value=1, value=50)
with col2:
    opt_type = st.selectbox("优化方式", ["网格搜索", "随机采样"])
    n_runs = st.number_input("运行次数", min_value=10, value=100)
with col3:
    metric_target = st.selectbox("优化目标", ["年化收益", "夏普比率", "胜率"])

if st.button("开始优化", type="primary"):
    st.info(f"参数 [{param_name}] 范围 [{param_min}-{param_max}]，{opt_type} {n_runs} 次")

    # 模拟参数扫描结果
    if opt_type == "网格搜索":
        param_values = list(range(param_min, param_max + 1, max(1, (param_max - param_min) // 20)))
    else:
        param_values = sorted(np.random.randint(param_min, param_max + 1, size=n_runs))

    results = []
    np.random.seed(42)
    for p in param_values:
        results.append({
            param_name: p,
            "年化收益": round(5 + np.random.randn() * 3 + p * 0.3, 2),
            "夏普比率": round(0.3 + np.random.randn() * 0.5 + p * 0.02, 3),
            "最大回撤": round(-5 - np.random.randn() * 8 - p * 0.1, 2),
            "胜率": round(40 + np.random.randn() * 10 + p * 0.2, 2),
            "总交易": int(50 + np.random.randn() * 20),
        })

    df = pd.DataFrame(results)

    st.subheader("优化结果排名")
    sort_col = {
        "年化收益": "年化收益",
        "夏普比率": "夏普比率",
        "胜率": "胜率",
    }.get(metric_target, "年化收益")

    st.dataframe(df.sort_values(sort_col, ascending=False), use_container_width=True)

    # 散点图
    st.subheader(f"{param_name} vs {metric_target}")
    scatter_df = pd.DataFrame({param_name: df[param_name], metric_target: df[metric_target]})
    st.scatter_chart(scatter_df, x=param_name, y=metric_target)

    # 最佳参数
    best = df.loc[df[sort_col].idxmax()]
    st.success(f"最佳参数: {param_name} = {best[param_name]} → {metric_target} = {best[sort_col]}")
