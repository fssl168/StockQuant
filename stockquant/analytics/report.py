# -*- coding: utf-8 -*-
"""F013 回测报表系统 — HTML/JSON/Console 报表生成"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stockquant.analytics")


class ReportGenerator:
    """回测报表生成器。

    - HTML（默认，含 matplotlib SVG 内嵌） - JSON（机器可读）
    - Console（控制台打印）
    """

    @staticmethod
    def generate_html(
        results: List[dict],
        output_path: Optional[str] = None,
        title: str = "StockQuant 回测报表",
    ) -> str:
        """
        生成 HTML 报表。

        Parameters
        ----------
        results : List[dict]
            Cerebro.run() 返回的结果列表
        output_path : str or None
            输出文件路径，None 则返回字符串
        title : str
            报表标题

        Returns
        -------
        str
            HTML 内容
        """
        strategy_reports = []
        for r in results:
            strategy_reports.append(ReportGenerator._render_strategy_section(r))

        html = ReportGenerator._html_template(title, strategy_reports)

        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"HTML report saved to: {output_path}")

        return html

    @staticmethod
    def generate_json(
        results: List[dict],
        output_path: Optional[str] = None,
    ) -> str:
        """
        生成 JSON 报表。

        Returns
        -------
        str
            JSON 字符串
        """

        def _serialize(obj):
            """递归序列化非标准类型"""
            if hasattr(obj, "__dict__"):
                return _serialize(obj.__dict__)
            if isinstance(obj, (list, tuple)):
                return [_serialize(i) for i in obj]
            if isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            if isinstance(obj, (int, float, str, bool, type(None))):
                return obj
            return str(obj)

        report = {
            "report_type": "StockQuant Backtest Report",
            "generated_at": datetime.now().isoformat(),
            "strategies": [],
        }

        for r in results:
            strategy_report = {
                "name": r.get("name", "Unnamed"),
                "metrics": r.get("metrics", {}),
                "trades": _serialize(r.get("trades", [])),
                "equity_curve": _serialize(r.get("equity_curve", [])),
            }
            report["strategies"].append(strategy_report)

        json_str = json.dumps(report, ensure_ascii=False, indent=2)

        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json_str)
            logger.info(f"JSON report saved to: {output_path}")

        return json_str

    @staticmethod
    def generate_pdf(
        results: List[dict],
        output_path: Optional[str] = None,
        title: str = "StockQuant 回测报表",
    ) -> bytes:
        """
        生成 PDF 报表。

        使用 weasyprint 将 HTML 转换为 PDF。若未安装 weasyprint 则抛出
        ImportError 并提示安装方式。

        Parameters
        ----------
        results : List[dict]
            Cerebro.run() 返回的结果列表
        output_path : str or None
            输出文件路径，None 则仅返回 bytes
        title : str
            报表标题

        Returns
        -------
        bytes
            PDF 文件内容
        """
        try:
            from weasyprint import HTML
        except ImportError:
            raise ImportError(
                "weasyprint 未安装，无法生成 PDF 报表。"
                "请运行: pip install weasyprint"
            )

        # 复用 generate_html，注入打印专用 CSS
        html_content = ReportGenerator.generate_html(results, title=title)
        print_css = """
        <style>
          @page {
            size: A4;
            margin: 15mm 12mm;
          }
          body {
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
          .strategy-section {
            page-break-inside: avoid;
          }
          .equity-chart {
            page-break-inside: avoid;
          }
          .trades-table {
            page-break-inside: avoid;
          }
        </style>
        """
        # 在 </head> 前插入打印 CSS
        html_content = html_content.replace("</head>", print_css + "\n</head>")

        pdf_bytes = HTML(string=html_content).write_pdf()

        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)
            logger.info(f"PDF report saved to: {output_path}")

        return pdf_bytes

    @staticmethod
    def generate_summary(results: List[dict]) -> str:
        """
        生成控制台摘要报告。
        """
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append(f"  StockQuant 回测报表摘要  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 70)

        for r in results:
            lines.append("")
            lines.append(f"  策略: {r.get('name', 'Unnamed')}")
            lines.append(f"  交易次数: {len(r.get('trades', []))}")
            lines.append("-" * 70)

            metrics = r.get("metrics", {})
            if isinstance(metrics, dict):
                for k, v in metrics.items():
                    if isinstance(v, float):
                        lines.append(f"  {k:35s}: {v:>12.4f}")
                    else:
                        lines.append(f"  {k:35s}: {str(v):>12}")

        lines.append("")
        lines.append("=" * 70)

        summary = "\n".join(lines)
        logger.info(summary)
        print(summary)
        return summary

    # ------------------------------------------------------------------
    # 内部渲染方法
    # ------------------------------------------------------------------

    @staticmethod
    def _render_strategy_section(r: dict) -> str:
        """渲染单个策略的 HTML 片段"""
        name = r.get("name", "Unnamed")
        metrics = r.get("metrics", {})
        trades = r.get("trades", [])
        equity = r.get("equity_curve", [])

        # 指标表格
        metrics_rows = ""
        if isinstance(metrics, dict):
            # 分类显示
            categories = {
                "收益指标": ["Total Return", "Annualized Return", "Excess Return (vs Benchmark)"],
                "风险指标": ["Max Drawdown", "Max Drawdown Duration", "Avg Drawdown", "Daily Volatility"],
                "风险调整收益": ["Sharpe Ratio", "Sortino Ratio", "Calmar Ratio", "Omega Ratio",
                                "Information Ratio", "Treynor Ratio"],
                "交易统计": ["Total Trades", "Total Wins", "Total Losses", "Win Rate",
                            "Profit Factor", "Avg Win", "Avg Loss"],
                "其他指标": ["SQN (System Quality Number)", "Kelly %", "VaR (95%)",
                            "CVaR (95%)", "Beta", "Alpha"],
            }

            for category, keys in categories.items():
                metrics_rows += f'          <tr><td colspan="3" class="category">{category}</td></tr>\n'
                for key in keys:
                    if key in metrics:
                        metrics_rows += f'          <tr><td class="metric-name">{key}</td><td class="metric-value">{metrics[key]}</td></tr>\n'

        # 交易明细表（前 50 条）
        trade_rows = ""
        display_trades = trades[:50] if trades else []
        for t in display_trades:
            if isinstance(t, dict):
                trade_rows += (
                    f'          <tr><td>{t.get("trade_id", "")}</td>'
                    f'<td>{t.get("symbol", "")}</td>'
                    f'<td>{t.get("side", "")}</td>'
                    f'<td>{t.get("price", ""):.2f}</td>'
                    f'<td>{t.get("quantity", "")}</td>'
                    f'</tr>\n'
                )

        # 权益曲线数据点（取最多 500 个点用于图表）
        equity_data = ReportGenerator._downsample_equity(equity, 500)

        # 回撤图表
        drawdown_html = ReportGenerator._render_drawdown_section(equity)

        # 月度热力图
        heatmap_html = ReportGenerator._render_monthly_heatmap(metrics)

        return f"""
      <div class="strategy-section">
        <h2>{name}</h2>
        <div class="metrics-table">
          <table>
            {metrics_rows}
          </table>
        </div>
        <div class="equity-chart">
          <h3>权益曲线</h3>
          <canvas id="equity-{hash(name)}" data-points="{json.dumps(equity_data)}"></canvas>
        </div>
{drawdown_html}
{heatmap_html}
        <div class="trades-table">
          <h3>交易明细（前 {len(display_trades)} 笔）</h3>
          <table>
            <thead><tr><th>Trade ID</th><th>Symbol</th><th>Side</th><th>Price</th><th>Qty</th></tr></thead>
            <tbody>
{trade_rows}
            </tbody>
          </table>
        </div>
      </div>
"""

    @staticmethod
    def _downsample_equity(equity_curve: List[tuple], max_points: int) -> List[tuple]:
        """对权益曲线进行降采样，保留关键趋势点"""
        if len(equity_curve) <= max_points:
            return equity_curve
        step = len(equity_curve) / max_points
        result = []
        for i in range(0, len(equity_curve), int(step)):
            result.append(equity_curve[i])
        if result[-1] != equity_curve[-1]:
            result.append(equity_curve[-1])
        return result[:max_points]

    @staticmethod
    def _render_drawdown_section(equity_curve: List[tuple]) -> str:
        """渲染回撤区间（Canvas）"""
        if not equity_curve or len(equity_curve) < 2:
            return ""

        # 计算回撤序列: drawdown = (peak - current) / peak
        drawdowns = []
        peak = equity_curve[0][0] if isinstance(equity_curve[0], (list, tuple)) else equity_curve[0]
        for point in equity_curve:
            val = point[0] if isinstance(point, (list, tuple)) else point
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0.0
            drawdowns.append(dd)

        # 降采样到 500 点
        sampled = drawdowns[:500] if len(drawdowns) > 500 else drawdowns

        return f"""
      <div class="drawdown-chart">
        <h3>最大回撤</h3>
        <canvas id="drawdown-{hash(str(equity_curve))}" data-points="{json.dumps(sampled)}"></canvas>
      </div>
"""

    @staticmethod
    def _render_monthly_heatmap(metrics: dict) -> str:
        """渲染月度收益热力图"""
        monthly_returns = metrics.get("Monthly Returns")
        if not monthly_returns or not isinstance(monthly_returns, dict):
            return ""

        # monthly_returns 格式: {1: 0.05, 2: -0.03, ...} 或 {str: float}
        values = {int(k): float(v) for k, v in monthly_returns.items()}
        if not values:
            return ""

        # 按月份聚合: {month: [val, val, ...]}
        month_groups: Dict[int, list] = {}
        for m, v in values.items():
            month_groups.setdefault(m, []).append(v)

        # 如果所有月份都只有 1 个值（单年），直接渲染 1-12 月
        single_year = all(len(vs) == 1 for vs in month_groups.values())

        if single_year:
            # 单年热力图: 12 个月一行
            cells = ""
            for m in range(1, 13):
                v = values.get(m)
                if v is not None:
                    pct = f"{v * 100:+.1f}%"
                    color = "#238636" if v >= 0 else "#da3633"
                    cells += f'<div class="hm-cell" style="background:{color}">{pct}</div>\n'
                else:
                    cells += '<div class="hm-cell hm-empty"></div>\n'
            return f"""
      <div class="heatmap-section">
        <h3>月度收益热力图</h3>
        <div class="heatmap">
{cells}        </div>
      </div>
"""
        else:
            # 多年热力图: 行=年份, 列=月份
            # 解析 key 格式：year*100+month → divmod(year, 100)
            year_months: Dict[int, Dict[int, float]] = {}
            for key, val in values.items():
                k = int(key)
                if k > 24:  # year*100 + month 格式
                    year, month = divmod(k, 100)
                    year_months.setdefault(year, {})[month] = val
                else:
                    # 单年份数据，归入 2024
                    year_months.setdefault(2024, {})[k] = val

            if not year_months:
                # 所有 key 都是单年份且 ≤24，无法组织多年数据
                cells = ""
                for m in range(1, 13):
                    v = values.get(m)
                    if v is not None:
                        pct = f"{v * 100:+.1f}%"
                        color = "#238636" if v >= 0 else "#da3633"
                        cells += f'<div class="hm-cell" style="background:{color}">{pct}</div>\n'
                    else:
                        cells += '<div class="hm-cell hm-empty"></div>\n'
                return f"""
      <div class="heatmap-section">
        <h3>月度收益热力图</h3>
        <div class="heatmap">
{cells}        </div>
      </div>
"""

            rows_html = ""
            for year in sorted(year_months.keys()):
                cells = ""
                for m in range(1, 13):
                    v = year_months[year].get(m)
                    if v is not None:
                        pct = f"{v * 100:+.1f}%"
                        color = "#238636" if v >= 0 else "#da3633"
                        cells += f'<div class="hm-cell" style="background:{color}">{pct}</div>\n'
                    else:
                        cells += '<div class="hm-cell hm-empty"></div>\n'
                rows_html += f'<div class="hm-row"><span class="hm-year">{year}</span>{cells}</div>\n'

            return f"""
      <div class="heatmap-section">
        <h3>月度收益热力图</h3>
        <div class="heatmap heatmap-multi-year">
{rows_html}        </div>
      </div>
"""

    @staticmethod
    def _html_template(title: str, strategy_sections: List[str]) -> str:
        """生成完整 HTML 页面"""
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
      background: #0d1117;
      color: #c9d1d9;
      padding: 20px;
      line-height: 1.6;
    }}
    .header {{
      background: linear-gradient(135deg, #1a1a2e, #16213e);
      padding: 30px;
      border-radius: 8px;
      margin-bottom: 30px;
      border: 1px solid #30363d;
    }}
    .header h1 {{
      color: #58a6ff;
      font-size: 28px;
      margin-bottom: 8px;
    }}
    .header .meta {{
      color: #8b949e;
      font-size: 14px;
    }}
    .strategy-section {{
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 8px;
      padding: 24px;
      margin-bottom: 24px;
    }}
    .strategy-section h2 {{
      color: #58a6ff;
      font-size: 22px;
      margin-bottom: 16px;
      padding-bottom: 8px;
      border-bottom: 1px solid #30363d;
    }}
    .strategy-section h3 {{
      color: #7ee787;
      font-size: 16px;
      margin: 20px 0 12px 0;
    }}
    .metrics-table {{ margin-bottom: 20px; }}
    .metrics-table table {{
      width: 100%;
      border-collapse: collapse;
    }}
    .metrics-table .category {{
      background: #1c2333;
      color: #f0883e;
      font-weight: bold;
      padding: 8px 12px;
      font-size: 13px;
    }}
    .metric-name {{
      padding: 6px 12px;
      border-bottom: 1px solid #21262d;
      color: #c9d1d9;
      font-size: 13px;
    }}
    .metric-value {{
      padding: 6px 12px;
      border-bottom: 1px solid #21262d;
      text-align: right;
      font-family: "SFMono-Regular", monospace;
      color: #58a6ff;
      font-size: 13px;
    }}
    .trades-table table {{
      width: 100%;
      border-collapse: collapse;
    }}
    .trades-table th {{
      background: #1c2333;
      padding: 8px;
      text-align: left;
      font-size: 12px;
      border: 1px solid #30363d;
    }}
    .trades-table td {{
      padding: 6px 8px;
      font-size: 12px;
      border: 1px solid #21262d;
    }}
    .trades-table tr:nth-child(even) {{
      background: #0d1117;
    }}
    .equity-chart {{
      background: #0d1117;
      border: 1px solid #30363d;
      border-radius: 4px;
      padding: 16px;
      margin: 16px 0;
      min-height: 250px;
      display: flex;
      align-items: flex-end;
    }}
    .equity-chart canvas {{
      width: 100%;
      height: 250px;
    }}
    .drawdown-chart {{
      background: #0d1117;
      border: 1px solid #30363d;
      border-radius: 4px;
      padding: 16px;
      margin: 16px 0;
      min-height: 250px;
      display: flex;
      align-items: flex-end;
    }}
    .drawdown-chart canvas {{
      width: 100%;
      height: 250px;
    }}
    .heatmap-section {{
      margin: 16px 0;
    }}
    .heatmap {{
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 4px;
      padding: 12px;
      background: #0d1117;
      border: 1px solid #30363d;
      border-radius: 4px;
    }}
    .hm-cell {{
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 12px 4px;
      border-radius: 4px;
      font-size: 12px;
      font-family: "SFMono-Regular", monospace;
      color: #fff;
      font-weight: bold;
      min-height: 40px;
    }}
    .hm-empty {{
      background: #161b22;
      border: 1px dashed #30363d;
    }}
    .footer {{
      text-align: center;
      color: #484f58;
      font-size: 12px;
      margin-top: 40px;
      padding: 20px;
    }}
  </style>
</head>
<body>
  <div class="header">
    <h1>{title}</h1>
    <div class="meta">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  StockQuant 2.0  |  共 {len(strategy_sections)} 个策略</div>
  </div>

  {"".join(strategy_sections)}

  <div class="footer">
    Powered by <strong>StockQuant 2.0</strong> — AI-Native Quantitative Trading Platform
  </div>

  <script>
    // 权益曲线 Canvas 渲染
    document.addEventListener('DOMContentLoaded', function() {{
      document.querySelectorAll('canvas[data-points]:not([id^="drawdown-"])').forEach(function(canvas) {{
        var ctx = canvas.getContext('2d');
        var data = JSON.parse(canvas.getAttribute('data-points'));
        if (data.length < 2) return;

        // 设置画布大小
        canvas.width = canvas.parentElement.offsetWidth || 800;
        canvas.height = 250;
        var w = canvas.width, h = canvas.height;

        // 计算权益范围
        var equities = data.map(function(d) {{ return d[0]; }});
        var minE = Math.min.apply(null, equities);
        var maxE = Math.max.apply(null, equities);
        var range = maxE - minE || 1;

        // 绘制渐变背景
        var gradient = ctx.createLinearGradient(0, 0, 0, h);
        gradient.addColorStop(0, 'rgba(88, 166, 255, 0.3)');
        gradient.addColorStop(1, 'rgba(88, 166, 255, 0.0)');

        ctx.beginPath();
        ctx.moveTo(0, h);
        for (var i = 0; i < data.length; i++) {{
          var x = (i / (data.length - 1)) * w;
          var y = h - ((data[i][0] - minE) / range) * (h - 20) - 10;
          if (i === 0) ctx.lineTo(x, y);
          else ctx.lineTo(x, y);
        }}
        ctx.lineTo(w, h);
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();

        // 绘制线条
        ctx.beginPath();
        for (var i = 0; i < data.length; i++) {{
          var x = (i / (data.length - 1)) * w;
          var y = h - ((data[i][0] - minE) / range) * (h - 20) - 10;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }}
        ctx.strokeStyle = '#58a6ff';
        ctx.lineWidth = 2;
        ctx.stroke();

        // 终点点位
        var lastX = w;
        var lastY = h - ((equities[equities.length-1] - minE) / range) * (h - 20) - 10;
        ctx.beginPath();
        ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
        ctx.fillStyle = '#3fb950';
        ctx.fill();
      }});

      // 回撤 Canvas 渲染
      document.querySelectorAll('canvas[data-points][id^="drawdown-"]').forEach(function(canvas) {{
        var ctx = canvas.getContext('2d');
        var data = JSON.parse(canvas.getAttribute('data-points'));
        if (data.length < 2) return;

        canvas.width = canvas.parentElement.offsetWidth || 800;
        canvas.height = 250;
        var w = canvas.width, h = canvas.height;

        // 回撤始终在 0~max 范围内，翻转绘制（从底部开始）
        var maxDD = Math.max.apply(null, data) || 1;

        // 渐变背景（红色向下）
        var gradient = ctx.createLinearGradient(0, 0, 0, h);
        gradient.addColorStop(0, 'rgba(218, 54, 51, 0.0)');
        gradient.addColorStop(1, 'rgba(218, 54, 51, 0.3)');

        ctx.beginPath();
        ctx.moveTo(0, h);
        for (var i = 0; i < data.length; i++) {{
          var x = (i / (data.length - 1)) * w;
          var y = h - (data[i] / maxDD) * (h - 20) - 10;
          ctx.lineTo(x, y);
        }}
        ctx.lineTo(w, h);
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();

        // 线条
        ctx.beginPath();
        for (var i = 0; i < data.length; i++) {{
          var x = (i / (data.length - 1)) * w;
          var y = h - (data[i] / maxDD) * (h - 20) - 10;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }}
        ctx.strokeStyle = '#da3633';
        ctx.lineWidth = 2;
        ctx.stroke();
      }});
    }});
  </script>
</body>
</html>"""
