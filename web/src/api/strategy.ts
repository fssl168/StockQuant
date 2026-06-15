import client from './client'
import type { Strategy } from '@/types'

const STRATEGY_TEMPLATES = [
  {
    name: 'Dual MA Crossover',
    code: `from stockquant.strategy import BaseStrategy
from stockquant.indicators import EMA

class DualMACrossover(BaseStrategy):
    name = "Dual MA Crossover"
    parameters = {"fast": 5, "slow": 20, "position_size": 0.1}

    def on_start(self):
        self.ma_fast = EMA(self.data, period=self.parameters["fast"])
        self.ma_slow = EMA(self.data, period=self.parameters["slow"])

    def on_bar(self):
        if self.ma_fast[0] > self.ma_slow[0] and self.ma_fast[-1] <= self.ma_slow[-1]:
            self.order_market(self.data.close[0], int(self.portfolio.cash * self.parameters["position_size"] / self.data.close[0]))
        elif self.ma_fast[0] < self.ma_slow[0] and self.ma_fast[-1] >= self.ma_slow[-1]:
            self.close_all()
`,
  },
  {
    name: 'RSI Reversal',
    code: `from stockquant.strategy import BaseStrategy
from stockquant.indicators import RSI

class RSIReversal(BaseStrategy):
    name = "RSI Reversal"
    parameters = {"period": 14, "oversold": 30, "overbought": 70, "position_size": 0.2}

    def on_start(self):
        self.rsi = RSI(self.data, period=self.parameters["period"])

    def on_bar(self):
        if self.rsi[0] < self.parameters["oversold"]:
            self.order_market(self.data.close[0], int(self.portfolio.cash * self.parameters["position_size"] / self.data.close[0]))
        elif self.rsi[0] > self.parameters["overbought"]:
            self.close_all()
`,
  },
  {
    name: 'Bollinger Bounce',
    code: `from stockquant.strategy import BaseStrategy
from stockquant.indicators import BOLL

class BollingerBounce(BaseStrategy):
    name = "Bollinger Bounce"
    parameters = {"period": 20, "std_dev": 2, "position_size": 0.15}

    def on_start(self):
        self.boll = BOLL(self.data, period=self.parameters["period"], std_dev=self.parameters["std_dev"])

    def on_bar(self):
        if self.data.close[0] < self.boll.lower[0]:
            self.order_market(self.data.close[0], int(self.portfolio.cash * self.parameters["position_size"] / self.data.close[0]))
        elif self.data.close[0] > self.boll.upper[0]:
            self.close_all()
`,
  },
  {
    name: 'MACD Divergence',
    code: `from stockquant.strategy import BaseStrategy
from stockquant.indicators import MACD

class MACDDivergence(BaseStrategy):
    name = "MACD Divergence"
    parameters = {"fast": 12, "slow": 26, "signal": 9, "position_size": 0.1}

    def on_start(self):
        self.macd = MACD(self.data, fast=self.parameters["fast"], slow=self.parameters["slow"], signal=self.parameters["signal"])

    def on_bar(self):
        if self.macd.historical[-2] < 0 and self.macd.historical[-1] >= 0 and self.macd.signal[-1] < 0:
            self.order_market(self.data.close[0], int(self.portfolio.cash * self.parameters["position_size"] / self.data.close[0]))
        elif self.macd.historical[-2] > 0 and self.macd.historical[-1] <= 0:
            self.close_all()
`,
  },
  {
    name: 'Dual Thrust',
    code: `from stockquant.strategy import BaseStrategy
from stockquant.indicators import HIGHEST, LOWEST

class DualThrust(BaseStrategy):
    name = "Dual Thrust"
    parameters = {"lookback": 4, "long_threshold": 0.7, "short_threshold": 0.7, "position_size": 0.1}

    def on_start(self):
        self.high = HIGHEST(self.data.high, period=self.parameters["lookback"]+1)
        self.low = LOWEST(self.data.low, period=self.parameters["lookback"]+1)

    def on_bar(self):
        range_val = max(
            self.high[-1] - self.low[-1],
            self.high[-1] - self.data.close[-2] if self.data.close[-2] else 0,
            self.data.close[-2] - self.low[-1] if self.data.close[-2] else 0,
        )
        if range_val > 0:
            upper = self.data.open[0] + self.parameters["long_threshold"] * range_val
            lower = self.data.open[0] - self.parameters["short_threshold"] * range_val
            if self.data.close[0] > upper:
                self.order_market(self.data.close[0], int(self.portfolio.cash * self.parameters["position_size"] / self.data.close[0]))
            elif self.data.close[0] < lower:
                self.close_all()
`,
  },
  {
    name: 'Mean Reversion',
    code: `from stockquant.strategy import BaseStrategy
from stockquant.indicators import SMA, STDDEV

class MeanReversion(BaseStrategy):
    name = "Mean Reversion"
    parameters = {"period": 20, "std_threshold": 2, "position_size": 0.15}

    def on_start(self):
        self.ma = SMA(self.data, period=self.parameters["period"])
        self.std = STDDEV(self.data, period=self.parameters["period"])

    def on_bar(self):
        upper = self.ma[0] + self.parameters["std_threshold"] * self.std[0]
        lower = self.ma[0] - self.parameters["std_threshold"] * self.std[0]
        if self.data.close[0] < lower:
            self.order_market(self.data.close[0], int(self.portfolio.cash * self.parameters["position_size"] / self.data.close[0]))
        elif self.data.close[0] > upper:
            self.close_all()
`,
  },
  {
    name: 'Momentum',
    code: `from stockquant.strategy import BaseStrategy
from stockquant.indicators import ROC

class Momentum(BaseStrategy):
    name = "Momentum"
    parameters = {"period": 10, "threshold": 0.05, "position_size": 0.1}

    def on_start(self):
        self.roc = ROC(self.data, period=self.parameters["period"])

    def on_bar(self):
        if self.roc[0] > self.parameters["threshold"]:
            self.order_market(self.data.close[0], int(self.portfolio.cash * self.parameters["position_size"] / self.data.close[0]))
        elif self.roc[0] < -self.parameters["threshold"]:
            self.close_all()
`,
  },
]

export const strategyApi = {
  list: () =>
    client.get('/strategy') as Promise<Strategy[]>,
  create: (data: Omit<Strategy, 'id' | 'created_at' | 'updated_at'>) =>
    client.post('/strategy', data) as Promise<Strategy>,
  get: (id: string) =>
    client.get(`/strategy/${id}`) as Promise<Strategy>,
  update: (id: string, data: Partial<Strategy>) =>
    client.put(`/strategy/${id}`, data) as Promise<Strategy>,
  delete: (id: string) =>
    client.delete(`/strategy/${id}`) as Promise<void>,
  templates: () => STRATEGY_TEMPLATES as { name: string; code: string }[],
}
