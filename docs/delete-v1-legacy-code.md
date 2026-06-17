# 删除 v1 版过时代码 — 实施计划

## 概要

StockQuant 项目已从 v1 升级到 v2 架构。v2 的 `__init__.py` 完全不导出 v1 模块，v2 新代码（engine/strategy/data/execution/analytics/ai）也不依赖任何 v1 模块。本次清理将删除所有 v1 遗留代码，保持代码库整洁。

## 当前状态分析

### v1 遗留文件（待删除）

| 文件 | 说明 | v2 替代 |
|------|------|---------|
| `stockquant/quant.py` | v1 统一入口，`import *` 模式 | `stockquant/__init__.py` |
| `stockquant/backtest.py` | v1 回测类，CSV 写入 + matplotlib | `stockquant/engine/cerebro.py` |
| `stockquant/market.py` | v1 数据入口，静态方法 | `stockquant/data/feed.py` + providers/ |
| `stockquant/trade.py` | v1 交易类，依赖废弃的 easytrader | `stockquant/engine/broker.py` (LiveBroker) |
| `stockquant/tick.py` | v1 Tick 数据类 | `stockquant/models/bar.py` (BarData) |
| `stockquant/config.py` | v1 配置类，JSON 加载 | v2 未使用此配置方式 |
| `stockquant/indicators.py` | v1 指标，依赖 talib C 库 | `stockquant/indicators/` 包（纯 numpy） |
| `stockquant/source/` 整个目录 | v1 数据源（含已失效的新浪API） | `stockquant/data/providers/` |
| `stockquant/utils/tools.py` | v1 时间工具 | v2 未引用 |
| `stockquant/utils/storage.py` | v1 CSV/TXT 读写 | v2 DataCache |
| `stockquant/utils/dingtalk.py` | v1 钉钉推送 | `stockquant/execution/notifier/dingtalk.py` |
| `stockquant/utils/sendmail.py` | v1 邮件推送 | `stockquant/execution/notifier/email.py` |
| `stockquant/utils/logger.py` | v1 日志（依赖 v1 config） | v2 使用标准 logging |
| `stockquant/utils/__init__.py` | 空文件 | 不再需要 |
| `stockquant/backtest_v1_compat.py` | v1 兼容层 | 删除，v2 不再兼容 v1 |
| `stockquant/strategy/v1_compat.py` | v1 兼容层入口 | 删除，v2 不再兼容 v1 |

### v1 配置文件（待删除）

| 文件 | 说明 |
|------|------|
| `docs/config.json` | v1 配置文件模板 |

### 依赖关系确认

- v2 新代码（engine/strategy/data/execution/analytics/ai/models/indicators）**完全不依赖** v1 模块
- v1 模块之间的依赖链：`quant.py` → `backtest.py` → `utils/` → `config.py`，`market.py` → `source/` → `config.py`，均为 v1 内部循环
- 唯一桥接点 `strategy/v1_compat.py` → `backtest_v1_compat.py`，一并删除
- 测试代码中无任何 v1 引用 — 已确认 tests/ 目录下不引用任何 v1 模块

### setup.py 影响

#### install_requires 调整

从 `install_requires` 中移除以下两项：

| 依赖 | 原因 | 状态 |
|------|------|------|
| `"concurrent-log-handler>=0.9"` | 仅 v1 `utils/logger.py` 使用 | 移除 |
| `"colorlog>=6.0"` | 仅 v1 `utils/logger.py` 使用 | 移除 |

> **注意**：以下依赖**不在** `install_requires` 中，无需从 `install_requires` 移除：
> - `"easytrader"` — 仅 v1 `trade.py` 使用，setup.py 中**从未声明**（不在 install_requires 也不在 extras_require）
> - `"baostock"` — 在 `extras_require["baostock"]` 中声明，v2 的 `baostock_feed.py` 需要 `pip install stockquant[baostock]`，**保留**
> - `"talib"` — 在 `extras_require["talib"]` 中声明，非强制依赖，**保留**

#### packages 声明重构（新增）

当前 `setup.py` 第 9 行有 `find_packages(...)`，但第 10-22 行又手动列出了 `packages=[...]`。Python setuptools 中当同时存在时，**手动 `packages=` 覆盖 `find_packages()` 的返回值**，导致：
- `find_packages()` 的排除规则完全失效
- 新增包不会被自动发现

**修改方案**：删除第 10-22 行的手动 `packages=[...]` 列表，仅保留第 9 行的 `find_packages()` 调用。删除 `stockquant.utils` 和 `stockquant.source` 目录后，`find_packages()` 会自动不包含它们。

```python
# 修改前
    packages=find_packages(exclude=["tests*", "logs*", "build*", "*.egg-info*"]),
    packages=[
        "stockquant",
        "stockquant.engine",
        ...  # 22 行手动列表
    ],

# 修改后
    packages=find_packages(exclude=["tests*", "logs*", "build*", "*.egg-info*"]),
```

## 实施步骤

### 步骤 1：删除 v1 根级模块文件

删除以下 7 个文件：
- `stockquant/quant.py`
- `stockquant/backtest.py`
- `stockquant/market.py`
- `stockquant/trade.py`
- `stockquant/tick.py`
- `stockquant/config.py`
- `stockquant/indicators.py`

### 步骤 2：删除 v1 source 目录

删除整个目录（4 个文件）：
- `stockquant/source/__init__.py`
- `stockquant/source/baostockdata.py`
- `stockquant/source/money.py`
- `stockquant/source/sinadata.py`
- `stockquant/source/tusharedata.py`

### 步骤 3：删除 v1 utils 目录

删除整个目录（6 个文件）：
- `stockquant/utils/__init__.py`
- `stockquant/utils/tools.py`
- `stockquant/utils/storage.py`
- `stockquant/utils/dingtalk.py`
- `stockquant/utils/sendmail.py`
- `stockquant/utils/logger.py`

### 步骤 4：删除 v1 兼容层

删除以下 2 个文件：
- `stockquant/backtest_v1_compat.py`
- `stockquant/strategy/v1_compat.py`

### 步骤 5：删除 v1 配置文件

- `docs/config.json`

### 步骤 6：更新 setup.py

1. **移除手动 `packages=[...]` 列表**（第 10-22 行） — 仅保留第 9 行 `find_packages()` 调用
2. **从 `install_requires` 中移除**：
   - `"concurrent-log-handler>=0.9"` — 仅 v1 utils/logger.py 使用
   - `"colorlog>=6.0"` — 仅 v1 utils/logger.py 使用
3. **无需操作**（原计划有误，已修正）：
   - ~~`"easytrader"`~~ — setup.py 中从未声明，无需移除
   - ~~`"baostock"`~~ — 在 `extras_require["baostock"]` 中，v2 baostock_feed.py 仍需要，保留
   - ~~`"talib"`~~ — 在 `extras_require["talib"]` 中，非强制依赖，保留
4. 版本号保持 `"2.0.0-dev"` 不变（版本升级不在本次范围内）

### 步骤 6.5：验证 setup.py 修改后仍可安装

```bash
pip install -e . --dry-run   # 仅验证，不实际安装
python -c "import setuptools; from setuptools import find_packages; print(find_packages(exclude=['tests*', 'logs*', 'build*', '*.egg-info*']))"
```

确认输出包含所有 v2 包（engine, strategy, indicators, models, analytics, data, execution, ai）且**不包含** source 和 utils。

### 步骤 7：删除 v1 文档

- `docs/框架安装方法.txt` — 纯 v1 安装说明（日期 2021/01/19），删除
- `docs/config.json` — v1 配置模板，删除

> 注意：`docs/change logs.md` 保留（v2 更新日志可能在其中）。

### 步骤 8：验证

1. 运行 `python -c "from stockquant import *"` 确认 v2 导入正常
2. 运行 `python -c "from stockquant import Cerebro, BaseStrategy, BarData"` 确认核心模块可用
3. 确认 `from stockquant.quant import *` 已不可用（v1 入口已删除）

## 假设与决策

1. **不保留 v1 兼容层** — v2 已是全新架构，保留兼容层只会增加维护负担
2. **不保留 v1 utils/** — v2 有自己的通知器（execution/notifier/），不再需要 v1 的 dingtalk/sendmail/logger
3. **保留 baostock 依赖** — 在 `extras_require["baostock"]` 中，v2 的 baostock_feed.py 仍在使用（需 `pip install stockquant[baostock]`）
4. **不修改版本号** — 版本升级是独立决策，不在本次清理范围内
5. **删除 docs/config.json** — v1 配置模板，v2 不再使用此格式
6. **删除 docs/框架安装方法.txt** — 纯 v1 安装说明，v2 无对应文档
7. **setup.py packages 改用 find_packages()** — 删除手动列表，避免 `find_packages()` 被覆盖失效
8. **easytrader 从未在 setup.py 中声明** — v1 trade.py 依赖它但 setup.py 无此条目，删除 trade.py 后无影响
9. **保留 extras_require 中的 talib/web/ai 依赖组** — 非 v1 遗留，v2 可能在未来使用

## 风险

- 如果有外部代码仍使用 `from stockquant.quant import *`，删除后将无法运行 — 这是预期行为，v2 API 完全不同
- `build/` 目录下的旧构建产物会在下次 `pip install -e .` 时自动更新，无需手动处理
- setup.py `packages` 重构后需验证 `pip install -e .` 正常，避免遗漏包的发现
