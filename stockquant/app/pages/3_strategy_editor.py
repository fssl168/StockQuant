# -*- coding: utf-8 -*-
"""F016 策略编辑器 — 管理/编辑/运行策略代码"""

import ast
import logging

import streamlit as st

logger = logging.getLogger("stockquant.app")

st.set_page_config(page_title="策略编辑器", page_icon="✏️", layout="wide")
st.title("✏️ 策略编辑器")
st.caption("F016 — 创建、编辑和验证策略代码")

# 策略模板
st.subheader("策略模板库")
templates = {
    "双均线交叉": """from stockquant import BaseStrategy, EMA

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
""",
    "RSI 超买超卖": """from stockquant import BaseStrategy, RSI

class RSIStrategy(BaseStrategy):
    name = "RSI"
    parameters = {"period": 14, "oversold": 30, "overbought": 70}

    def on_start(self):
        self.rsi = self.RSI(period=self.parameters["period"])

    def on_bar(self, bars):
        if self.rsi[0] < self.parameters["oversold"]:
            self.order_market(self.data.close[0], 100)
        elif self.rsi[0] > self.parameters["overbought"]:
            self.close_all()
""",
    "MACD 策略": """from stockquant import BaseStrategy, MACD

class MACDStrategy(BaseStrategy):
    name = "MACD"
    parameters = {"fast": 12, "slow": 26, "signal": 9}

    def on_start(self):
        self.macd = self.MACD(fast=self.parameters["fast"], slow=self.parameters["slow"], signal=self.parameters["signal"])

    def on_bar(self, bars):
        dif, dea, hist = self.macd[0]
        if hist > 0 and self.macd.hist[1] <= 0:
            self.order_market(self.data.close[0], 100)
        elif hist < 0 and self.macd.hist[1] >= 0:
            self.close_all()
""",
}

selected_template = st.selectbox("选择模板", list(templates.keys()))

st.subheader("代码编辑器")
code = st.text_area("策略代码", value=templates[selected_template], height=400,
                    placeholder="输入 Python 策略代码...")

# 语法检查
col1, col2 = st.columns(2)
with col1:
    check_btn = st.button("语法检查", type="primary")
with col2:
    save_btn = st.button("保存策略")

if check_btn and code:
    try:
        ast.parse(code)
        st.success("✅ 语法正确")
    except SyntaxError as e:
        st.error(f"❌ 语法错误: 第 {e.lineno} 行 — {e.msg}")

if save_btn and code:
    try:
        ast.parse(code)
        st.success("策略已保存")
    except SyntaxError:
        st.warning("请先修复语法错误")

# 已有策略列表
st.subheader("已有策略")
st.info("策略持久化功能待实现，当前仅支持编辑器预览。")
