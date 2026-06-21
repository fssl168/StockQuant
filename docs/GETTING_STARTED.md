# StockQuant 快速开始指南

本文档帮助你在 10 分钟内完成 StockQuant 的安装、回测、Web Dashboard、AI 对话和自定义策略。

---

## 1. 安装

### 系统要求

- Python 3.10+
- Windows / macOS / Linux

### 安装命令

```bash
pip install stockquant
```

### 安装可选组件

```bash
# 技术指标加速（C 扩展）
pip install stockquant[talib]

# pandas-ta 补充指标
pip install stockquant[pandas-ta]

# 交互式图表
pip install stockquant[plotly]

# BaoStock 数据源
pip install stockquant[baostock]

# Parquet 高性能数据
pip install stockquant[pyarrow]

# Web 服务
pip install stockquant[web]

# Dashboard
pip install stockquant[dashboard]

# 模拟交易
pip install stockquant[trading]

# 开发调试
pip install stockquant[dev]
```

---

## 2. 五分钟回测

### 2.1 使用 BaoStock 数据

```python
# -*- coding: utf-8 -*-
"""双均线策略回测示例"""

from datetime import datetime
from stockquant.engine import Cerebro, BacktestBroker
from stockquant.engine.commission import CommissionInfo
from stockquant.data.providers import BaoStockFeed
from stockquant.strategy.base import BaseStrategy


class DualMAStrategy(BaseStrategy):
    """双均线交叉策略"""
    name = "Dual MA Crossover"
    parameters = {"fast": 5, "slow": 20}

    def on_start(self):
        # 构建指标
        self.ma_fast = self.EMA(self.data, self.parameters["fast"])
        self.ma_slow = self.EMA(self.data, self.parameters["slow"])

    def on_bar(self, bars):
        # 金叉买入，死叉卖出
        if self.ma_fast.crossed_above(self.ma_slow):
            bar = bars["sh600519"]
            self.order_market(bar, 100)
        elif self.ma_fast.crossed_below(self.ma_slow):
            bar = bars["sh600519"]
            self.order_sell(bar, 100)


def run_backtest():
    # 获取 BaoStock 日线数据
    feed = BaoStockFeed(
        symbols=["sh600519"],    # 贵州茅台
        start_date="20200101",
        end_date="20241231",
        period="d",
    )

    # 创建引擎
    cerebro = Cerebro(cash=1_000_000)
    cerebro.add_data(feed)
    cerebro.add_strategy(DualMAStrategy, fast=5, slow=20)

    # 设置佣金和滑点
    cerebro.commission = CommissionInfo(
        commission_rate=0.00025,    # 万 2.5
        stamp_tax_rate=0.0005,      # 印花税千 0.5
    )
    cerebro.broker = BacktestBroker()

    # 运行回测
    results = cerebro.run()
    cerebro.show_report(results)

    return results


if __name__ == "__main__":
    run_backtest()
```

### 2.2 使用合成数据快速体验

不需要配置数据源，直接运行：

```python
import numpy as np
import pandas as pd
from datetime import datetime
from stockquant.engine import Cerebro
from stockquant.data.providers.csv_feed import CSVFeed
from stockquant.strategy.base import BaseStrategy
import tempfile, os

# 生成合成数据
np.random.seed(42)
n = 500
dates = pd.bdate_range(start=datetime(2023, 1, 1), periods=n)
closes = [100.0]
for _ in range(n - 1):
    closes.append(closes[-1] * (1 + np.random.normal(0, 0.01)))

df = pd.DataFrame({
    "open": closes, "high": [c * 1.02 for c in closes],
    "low": [c * 0.98 for c in closes], "close": closes,
    "volume": 1_000_000,
}, index=dates)
df.index.name = "timestamp"

# 写入临时 CSV
tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
tmp.close()
df.to_csv(tmp.name, index=True)

# 加载数据并回测
feed = CSVFeed(filepath=tmp.name, symbol="SYNTH", timeframe="1d")

class SimpleStrategy(BaseStrategy):
    name = "Simple"
    parameters = {}
    def on_start(self):
        pass
    def on_bar(self, bars):
        bar = bars["SYNTH"]
        if bar.close > bar.open:
            self.order_market(bar, 100)

cerebro = Cerebro(cash=1_000_000)
cerebro.add_data(feed)
cerebro.add_strategy(SimpleStrategy)
results = cerebro.run()
cerebro.show_report(results)

os.unlink(tmp.name)
```

### 2.3 使用本地 CSV 数据

```python
from stockquant.data.providers.csv_feed import CSVFeed
from stockquant.engine import Cerebro

feed = CSVFeed(
    filepath="data/sh600519_1d.csv",
    symbol="sh600519",
    timeframe="1d",
)
cerebro = Cerebro(cash=1_000_000)
cerebro.add_data(feed)
cerebro.add_strategy(MyStrategy)
results = cerebro.run()
```

CSV 文件格式要求：

```csv
timestamp,open,high,low,close,volume
2024-01-02,1680.00,1695.00,1675.00,1690.00,1234567
2024-01-03,1690.00,1700.00,1685.00,1698.00,1345678
```

---

## 3. Web Dashboard

### 3.1 启动 API 服务器

```bash
# 启动 FastAPI 后端（含热重载）
uvicorn stockquant.api.main:app --reload --host 0.0.0.0 --port 8000
```

API 文档自动生成在：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 3.2 启动前端 Dashboard

```bash
# 如果项目有前端代码
cd frontend
npm install
npm run dev

# 或使用 Streamlit Dashboard（如果已实现）
streamlit run stockquant/dashboard/app.py
```

### 3.3 主要 API 端点

| 端点 | 功能 |
|------|------|
| `GET /api/health` | 健康检查 |
| `POST /api/backtest/run` | 启动回测 |
| `GET /api/backtest/{task_id}` | 查询回测状态 |
| `POST /ai/chat` | AI 对话 |
| `GET /api/portfolio` | 获取投资组合 |
| `POST /api/monitor/watchlist` | 管理自选股 |
| `WS /ws` | 统一 WebSocket 入口 |
| `WS /ws/monitor` | 盯盘行情推送 |
| `WS /ws/chat/{conv_id}` | AI 对话推送 |

### 3.4 健康检查

```bash
curl http://localhost:8000/api/health
# 返回: {"status": "ok", "version": "2.0.0-dev", "uptime": 123.45}
```

---

## 4. AI 对话

### 4.1 通过 API 调用

```python
import requests

resp = requests.post("http://localhost:8000/api/ai/chat", json={
    "message": "茅台现在的估值如何？",
    "conversation_id": "conv_001",
})
print(resp.json())
```

### 4.2 通过 Python SDK

```python
from stockquant.ai.chat_agent import ChatAgent

agent = ChatAgent(
    model="gpt-4o",
    api_key="your-api-key",
)

response = agent.chat("分析一下贵州茅台的基本面")
print(response)
```

### 4.3 支持的 AI 工具

| 工具 | 功能 |
|------|------|
| `query_market_data` | 查询行情数据 |
| `generate_chart_json` | 生成图表 JSON |
| `trigger_backtest` | 触发回测 |
| `search_news` | 搜索新闻 |

### 4.4 WebSocket 实时对话

```python
import asyncio
import websockets

async def chat_ws():
    async with websockets.connect(
        "ws://localhost:8000/ws/chat/conv_001"
    ) as ws:
        connected = await ws.recv()
        print(f"Connected: {connected}")

        await ws.send('{"message": "分析宁德时代"}')
        while True:
            msg = await ws.recv()
            print(f"Response: {msg}")
            if "done" in msg:
                break

asyncio.run(chat_ws())
```

---

## 5. Paper Trading（模拟交易）

### 5.1 快速开始

```python
from stockquant.engine import Cerebro, PaperBroker
from stockquant.engine.commission import CommissionInfo

# 创建模拟盘 Broker
broker = PaperBroker(
    slippage=None,           # 无滑点
    limit_up_ratio=0.10,     # ±10% 涨跌停
    state_file="paper_state.json",  # 崩溃恢复
)

cerebro = Cerebro(cash=1_000_000)
cerebro.add_data(feed)
cerebro.add_strategy(MyStrategy)
cerebro.broker = broker
cerebro.commission = CommissionInfo()

results = cerebro.run()
```

### 5.2 模拟盘实时循环

```python
# 逐 Bar 模拟实时行情推送
trades = broker.run_realtime_loop(
    data_feed=feed,
    strategies=[my_strategy],
    interval_seconds=0.0,     # 0 = 不延迟
    max_bars=100,             # 最多处理 100 根
)
print(f"模拟交易成交: {len(trades)} 笔")
```

### 5.3 回测 vs 模拟盘对比

```python
# 模拟盘 vs 回测误差分析
comparison = broker.compare_with_backtest(
    backtest_broker=backtest_broker,
    backtest_equity=[1000000, 1005000, 1010000, ...],
    paper_equity=[1000000, 1004800, 1009500, ...],
)
print(comparison["summary"])
# 输出: "模拟盘与回测误差 < 1%"
```

---

## 6. 自定义策略

### 6.1 策略模板

继承 `BaseStrategy`，实现 `on_start` 和 `on_bar` 两个方法即可：

```python
# -*- coding: utf-8 -*-
from stockquant.strategy.base import BaseStrategy
from stockquant.indicators import MA, EMA, RSI, MACD


class MyStrategy(BaseStrategy):
    """自定义策略示例"""
    name = "My Custom Strategy"
    parameters = {
        "fast": 5,
        "slow": 20,
        "rsi_period": 14,
        "rsi_lower": 30,
        "rsi_upper": 70,
    }

    def on_start(self):
        """回测开始时初始化指标"""
        close = self.data  # 收盘价序列

        # 使用策略内置的指标快捷方法
        self.ma_fast = self.EMA(close, self.parameters["fast"])
        self.ma_slow = self.EMA(close, self.parameters["slow"])
        self.rsi = self.RSI(close, period=self.parameters["rsi_period"])

        # 或直接用 Indicators
        self.macd = self.MACD(close, fast=12, slow=26, signal=9)

        self.buy_signal = False
        self.sell_signal = False

    def on_bar(self, bars):
        """每根 K 线触发"""
        if not self.data or len(self.data) < self.parameters["slow"]:
            return

        # 交易逻辑
        if self.buy_signal:
            bar = bars["sh600519"]
            self.order_market(bar, 100)
            self.buy_signal = False

        if self.sell_signal:
            bar = bars["sh600519"]
            self.order_sell(bar, 100)
            self.sell_signal = False

    def _update_signals(self):
        """更新信号"""
        if self.ma_fast[-1] > self.ma_slow[-1] and \
           self.ma_fast[-2] <= self.ma_slow[-2] and \
           self.rsi[-1] < self.parameters["rsi_upper"]:
            self.buy_signal = True

        if self.ma_fast[-1] < self.ma_slow[-1] and \
           self.ma_fast[-2] >= self.ma_slow[-2]:
            self.sell_signal = True
```

### 6.2 可用指标

| 类别 | 指标 | 方法 |
|------|------|------|
| 移动平均 | MA / EMA / KAMA / TRIX | `self.EMA(data, period)` |
| 震荡指标 | RSI / KDJ / CCI / ROC / STOCHRSI | `self.RSI(data, period)` |
| 波动率 | BOLL / ATR / STDDEV / SAR | `self.BOLL(data, period)` |
| 趋势 | MACD / OBV / HIGHEST / LOWEST | `self.MACD(data)` |

### 6.3 订单发送

```python
# 市价单买入
self.order_market(bar, 100)

# 限价单买入
self.order_limit(bar, 100, limit_price=1680.0)

# 市价单卖出
self.order_sell(bar, 100)

# 平掉全部持仓
self.close_all()
```

### 6.4 运行自定义策略

```python
from stockquant.engine import Cerebro
from my_strategy import MyStrategy

cerebro = Cerebro(cash=1_000_000)
cerebro.add_data(feed)
cerebro.add_strategy(MyStrategy, fast=5, slow=20, rsi_period=14)
results = cerebro.run()
cerebro.show_report(results)
```

### 6.5 参数优化

```python
results = cerebro.optstrategy(
    strategy_cls=MyStrategy,
    param_grid={
        "fast": [3, 5, 10, 20],
        "slow": [10, 20, 30, 50],
    },
    optimizer="grid",
    target="Sharpe Ratio",
)
# 返回 Top 20 参数组合
```

---

## 7. 配置

### 7.1 环境变量

复制 `.env.example` 为 `.env`，填入你的配置：

```bash
cp .env.example .env
```

### 7.2 核心配置项

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | (空) | OpenAI API 密钥（AI 对话必需） |
| `OPENAI_MODEL` | `gpt-4o` | 使用的 LLM 模型 |
| `OPENAI_API_BASE` | (空) | 兼容 API 地址（如本地部署） |
| `ANTHROPIC_API_KEY` | (空) | Anthropic Claude API 密钥 |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL 连接字符串 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接地址 |
| `DATA_PROVIDER_SOURCE` | `baostock` | 数据源（baostock / tushare / akshare） |
| `TUSHARE_TOKEN` | (空) | Tushare Token |
| `TRADING_BROKER` | `paper` | 交易模式（paper / live） |
| `HOST` | `0.0.0.0` | API 服务器监听地址 |
| `PORT` | `8000` | API 服务器端口 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

### 7.3 最小配置（仅回测）

如果只跑回测，只需：

```bash
# .env
DATA_PROVIDER_SOURCE=baostock
LOG_LEVEL=INFO
```

### 7.4 启用 AI 对话

```bash
# .env
OPENAI_API_KEY=sk-xxxx
OPENAI_MODEL=gpt-4o
OPENAI_API_BASE=                     # 可选，兼容 API
```

### 7.5 使用本地 LLM

```bash
# .env
LOCAL_LLM_ENABLED=true
LOCAL_LLM_BACKEND=ollama
LOCAL_LLM_MODEL=qwen2.5-7b-instruct
LOCAL_LLM_BASE_URL=http://localhost:11434
```

---

## 常见故障

| 问题 | 解决方案 |
|------|----------|
| `ModuleNotFoundError: No module named 'baostock'` | `pip install baostock` |
| `connection refused` on port 8000 | 确认 `uvicorn` 已启动 |
| AI 对话返回空 | 检查 `OPENAI_API_KEY` 是否已配置 |
| 回测速度很慢 | 减少数据量，或改用 Parquet 数据源 |
| Parquet 读取失败 | `pip install pyarrow` |
