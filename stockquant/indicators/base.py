# -*- coding: utf-8 -*-
"""指标基类与代理"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    import matplotlib.figure
    import plotly.graph_objects  # noqa: F401


class Indicator(ABC):
    """指标抽象基类"""

    @abstractmethod
    def calculate(self, data: List[float]) -> List[float]:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class IndicatorProxy:
    """
    指标结果代理，支持 __getitem__ 访问历史值。

    Usage:
        ema = self.EMA(prices, period=12)
        current = ema[0]        # 最新值
        prev = ema[-1]          # 前一根
        series = list(ema)      # 转为列表
    """

    def __init__(self, values: List[float], name: Optional[str] = None):
        self._values = values
        self._name = name or "Indicator"

    def __getitem__(self, key: int) -> float:
        n = len(self._values)
        if n == 0:
            return 0.0
        # 支持负索引
        idx = key if key >= 0 else n + key
        if idx < 0 or idx >= n:
            return 0.0  # NaN 缺失值
        v = self._values[idx]
        if v is None or (isinstance(v, float) and (v != v)):  # NaN check
            return 0.0
        return float(v)

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self):
        return iter(self._values)

    def __repr__(self) -> str:
        n = len(self._values)
        return f"IndicatorProxy([{self._values[0] if n > 0 else 0}... ({n} values)])"

    @property
    def current(self) -> float:
        return self[-1]

    def crossed_above(self, other: "IndicatorProxy") -> bool:
        """当前值上穿 other"""
        return self[-1] > other[-1] and self[-2] <= other[-2]

    def crossed_below(self, other: "IndicatorProxy") -> bool:
        """当前值下穿 other"""
        return self[-1] < other[-1] and self[-2] >= other[-2]

    # ------------------------------------------------------------------
    # 可视化
    # ------------------------------------------------------------------

    def _filter_nan(self, values: List[float]) -> tuple:
        """过滤 NaN 值，返回 (indices, valid_values)"""
        indices: List[int] = []
        valid: List[float] = []
        for i, v in enumerate(values):
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                indices.append(i)
                valid.append(float(v))
        return indices, valid

    def plot(self, title: Optional[str] = None) -> "plotly.graph_objects.Figure | matplotlib.figure.Figure | None":
        """
        绘制指标曲线图。

        优先使用 plotly（交互式），未安装时回退到 matplotlib。
        如果两者都不可用，打印提示并返回 None。

        Returns
        -------
        plotly.graph_objects.Figure 或 matplotlib.figure.Figure
        """
        indices, valid = self._filter_nan(self._values)
        if not valid:
            print(f"[plot_indicator] {self._name}: 无可绘制的有效数据")
            return None

        title = title or self._name

        # 1) 尝试 plotly
        try:
            import plotly.graph_objects as go  # type: ignore
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=indices, y=valid, mode="lines", name=self._name,
            ))
            fig.update_layout(
                title=title,
                xaxis_title="Bar Index",
                yaxis_title=self._name,
                template="plotly_white",
                height=450,
            )
            return fig
        except ImportError:
            pass

        # 2) 回退到 matplotlib
        try:
            import matplotlib  # type: ignore
            matplotlib.use("Agg")  # 无头模式
            import matplotlib.pyplot as plt  # type: ignore

            fig, ax = plt.subplots(figsize=(12, 4))
            ax.plot(indices, valid, label=self._name, color="#1f77b4")
            ax.set_title(title)
            ax.set_xlabel("Bar Index")
            ax.set_ylabel(self._name)
            ax.legend()
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            return fig
        except ImportError:
            pass

        print(f"[plot_indicator] {self._name}: 请安装 plotly 或 matplotlib 以启用可视化")
        return None

    def plot_html(self, title: Optional[str] = None, filename: Optional[str] = None) -> str:
        """
        将指标图渲染为 HTML 字符串。

        Returns
        -------
        str -- 包含图表的 HTML 代码
        """
        title = title or self._name
        fig = self.plot(title)
        if fig is None:
            return "<p>No data to plot.</p>"

        # plotly figure 支持 to_html
        if hasattr(fig, "to_html"):
            return fig.to_html(include_plotlyjs="cdn", full_html=False)

        # matplotlib figure 导出为 SVG 内联
        try:
            import matplotlib  # type: ignore
            matplotlib.use("Agg")
            import io
            import base64

            buf = io.BytesIO()
            fig.savefig(buf, format="svg", bbox_inches="tight")
            buf.seek(0)
            svg_bytes = buf.read()
            encoded = base64.b64encode(svg_bytes).decode("utf-8")
            # matplotlib savefig 不支持直接 SVG 到 base64 内联显示
            # 改为直接返回 SVG 字符串
            return svg_bytes.decode("utf-8")
        except Exception:
            return f"<p>图表渲染失败: {self._name}</p>"
