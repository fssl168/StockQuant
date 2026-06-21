# 券商 SDK 部署指南

本指南介绍 StockQuant 支持的三家券商接口（QMT / XTP / CTP）的 SDK 安装、授权申请、客户端部署与配置接入流程。

> ⚠️ **实盘交易风险提示**：接入券商 SDK 后，下单/撤单将产生真实委托。请先在模拟环境完成全链路验证，并确认风控参数（`risk.max_position_pct` / `risk.max_daily_loss_pct` / `risk.max_drawdown_pct`）已合理设置。

## 目录

- [架构概览](#架构概览)
- [QMT 部署指南（迅投 QMT）](#qmt-部署指南迅投-qmt)
- [XTP 部署指南（中泰证券）](#xtp-部署指南中泰证券)
- [CTP 部署指南（期货 CTP）](#ctp-部署指南期货-ctp)
- [配置示例](#配置示例)
- [故障排查常见问题](#故障排查常见问题)

---

## 架构概览

StockQuant 通过统一的 `Broker` 抽象层对接券商，三个实现位于
`stockquant/execution/brokers/`：

| Broker | 文件 | 适用市场 | SDK 依赖 | 连接方式 |
|--------|------|----------|----------|----------|
| `QMTBroker` | `qmt_broker.py` | A 股 | `xtquant` | 本地 QMT 客户端（IPC） |
| `XTPBroker` | `xtp_broker.py` | A 股 / 基金 / 债券 | `vnpy_xtp` 或 `openctp` | 网络直连 XTP 网关 |
| `CTPBroker` | `ctp_broker.py` | 期货 / 期权 | `openctp-ctp` | 网络直连 CTP 前置 |

**降级机制**：三个 Broker 的 SDK 均为可选导入。若对应 SDK 未安装或连接失败，
Broker 会自动降级为**模拟模式**（订单以 `SIMULATED` 状态记录审计日志），
不会阻断策略运行，但也不会产生真实成交。

实盘模式由 `trading.broker = "live"` 触发，并通过 `trading.api` 选择券商
（见 [配置示例](#配置示例)）。实例化逻辑位于
`stockquant/api/routers/trading.py` 的 `_get_broker()`。

---

## QMT 部署指南（迅投 QMT）

QMT（迅投极速交易终端）通过本地客户端运行，StockQuant 经 `xtquant` SDK
与本地客户端通信，**不需要直连券商服务器**。

### 1. 申请权限

- 在支持 QMT 的券商（如国金、华泰、中泰等）开户并申请 QMT 交易权限。
- 获取**资金账号**（即 `account_id`）。
- QMT 客户端本身负责登录鉴权，StockQuant 侧**不保存交易密码**
  （`QMTBroker.__init__` 仅接收 `qmt_path` 与 `account_id`）。

### 2. 安装并运行 QMT 客户端

1. 从券商处获取 QMT 客户端安装包，安装到本机。
2. 启动 QMT 客户端，使用资金账号登录，并保持客户端**前台运行**。
3. 记录 QMT 客户端的 **userdata 目录路径**（即 `qmt_path`），
   通常形如 `D:\国金QMT交易端\userdata_mini`。

   > `qmt_path` 是 `xttrader.XtQuantTrader(qmt_path, session_id)` 的第一个参数，
   > 指向客户端的用户数据目录，SDK 通过该目录与客户端建立 IPC 通信。

### 3. 安装 xtquant SDK

```bash
pip install xtquant
```

> `xtquant` 通常随 QMT 客户端一同分发，也可在券商提供的 SDK 包中找到。
> 安装后可执行以下命令验证：
>
> ```python
> python -c "from xtquant import xttrader, xtconstant; print('xtquant OK')"
> ```

### 4. 接入验证

启动 StockQuant 后，日志中出现以下信息表示 QMT 已就绪：

```
INFO stockquant.execution.qmt: QMT 连接成功: <account_id>
```

若出现 `xtquant 未安装` 或 `QMT 连接失败`，Broker 将降级为模拟模式。

### QMT 连接参数说明

| 参数 | settings key | 说明 |
|------|--------------|------|
| `qmt_path` | `qmt.path` | QMT 客户端 userdata 目录绝对路径 |
| `account_id` | `qmt.account` | 资金账号 |

连接时使用 session_id = `1`（见 `qmt_broker.py` 的 `_connect()`）。
下单时强制 **100 股整数倍**校验，不满足则订单被 `REJECTED`。

---

## XTP 部署指南（中泰证券）

XTP（eXtreme Transaction Platform）是中泰证券提供的极速交易系统，
支持 A 股、基金、债券等品种。StockQuant 通过网络直连 XTP 交易网关。

### 1. 申请中泰证券授权

向中泰证券申请 XTP 接入权限，获取以下凭证：

| 凭证 | 说明 |
|------|------|
| **资金账号** (`user`) | XTP 交易资金账号 |
| **交易密码** (`password`) | 资金账号交易密码 |
| **应用 ID** (`app_id`) | 由中泰证券分配的整数型应用 ID |
| **客户端 ID** (`client_id`) | 0–99 范围内整数，同一 `app_id` 下需唯一 |
| **软件密钥** (`software_key`) | XTP 软件授权密钥 |
| **交易服务器地址** (`server_addr`) | `ip:port` 格式，默认端口 `6002` |

> `client_id` 用于 `TraderApi.CreateTraderApi(client_id, log_path)` 创建 API 实例，
> 同一 `app_id` 下多个客户端需使用不同 `client_id`，否则会冲突。

### 2. 安装 XTP SDK

推荐使用 VeighNa 框架封装的 `vnpy_xtp`：

```bash
pip install vnpy_xtp
```

或使用 openctp 提供的 XTP 兼容接口：

```bash
pip install openctp
```

验证安装：

```python
python -c "from vnpy_xtp import XtpGateway; print('XTP SDK OK')"
```

### 3. 接入验证

XTP 连接流程（见 `xtp_broker.py` 的 `connect()`）：

1. `TraderApi.CreateTraderApi(client_id, "xtp_log")` 创建实例（日志写入当前目录 `xtp_log/`）
2. `RegisterSpi()` 注册回调（`_XTPTaderSpi`）
3. `SetSoftwareKey(software_key)` 设置软件密钥
4. `RegisterFront(ip, port)` 注册前置地址（从 `server_addr` 解析）
5. `SubscribePublicTopic(0)` / `SubscribePrivateTopic(0)` 订阅公有/私有流
6. `Init()` 启动连接，等待前置连接回调（最多 10 秒）
7. `Login(user, password, app_id)` 登录，返回 `session_id`

连接成功日志：

```
INFO stockquant.execution.xtp: XTP SDK (vnpy_xtp) 已加载
INFO stockquant.execution.xtp: XTP 前置连接成功
INFO stockquant.execution.xtp: XTP 登录成功: user=<user>, session_id=<id>, client_id=<id>
```

### XTP 订单类型映射

| OrderType | XTP price_type | 说明 |
|-----------|----------------|------|
| `LIMIT` | `1` (`XTP_PRICE_LIMIT`) | 限价单 |
| `MARKET` | `5` (`XTP_PRICE_MARKET`) | 市价单 |
| 其他 | `6` (`XTP_PRICE_BEST5_OR_CANCEL`) | 最优五档即时成交剩余撤销 |

XTP 同样强制 **100 股整数倍**校验。持仓查询返回
`total_qty` / `avg_price` / `market_value` / `unrealized_pnl` / `exchange_id`，
余额查询返回 `buying_power` / `frozen_cash` / `total_asset` / `market_value`。

---

## CTP 部署指南（期货 CTP）

CTP（Comprehensive Transaction Platform）是上期技术开发的期货交易前置系统，
支持国内所有期货交易所（上期所、大商所、郑商所、中金所、广期所）的期货/期权交易。

### 1. 申请期货公司授权

在期货公司开户并申请程序化交易权限，获取以下凭证：

| 凭证 | 说明 |
|------|------|
| **资金账号** (`user`) | 即 CTP `InvestorID` |
| **交易密码** (`password`) | 资金账号交易密码 |
| **期货公司代码** (`broker_id`) | 期货公司 `BrokerID`（如 `"9999"`） |
| **交易前置地址** (`front_addr`) | `tcp://ip:port` 格式 |
| **AppID** (`app_id`) | 部分期货公司需要，用于客户端认证 |

> `front_addr` 必须以 `tcp://` 开头（如 `tcp://180.168.146.187:10201`），
> 这是 `RegisterFront()` 直接接收的格式。
> 实盘与仿真（SimNow）的前置地址不同，请向期货公司确认。

### 2. 安装 CTP SDK

推荐使用 openctp 官方 Python 封装：

```bash
pip install openctp-ctp
```

或从上期技术官网获取原生 CTP API。验证安装：

```python
python -c "from openctp_ctp.thosttraderapi import CThostFtdcTraderApi; print('CTP SDK OK')"
```

### 3. 接入验证

CTP 连接流程（见 `ctp_broker.py` 的 `connect()`）：

1. 创建 flow 目录 `ctp_flow/`（当前工作目录下，`os.makedirs` 保证存在）
2. `CreateFtdcTraderApi(flow_path)` 创建实例
3. `RegisterSpi()` 注册回调（`_CTPTraderSpi`）
4. `SubscribePublicTopic(0)` / `SubscribePrivateTopic(0)` 订阅公有/私有流
5. `RegisterFront(front_addr)` 注册前置地址
6. `Init()` 启动连接，等待 `OnFrontConnected` 回调（最多 10 秒）
7. 若配置了 `app_id`，先 `ReqAuthenticate()` 客户端认证
8. `ReqUserLogin()` 登录，等待 `OnRspUserLogin` 回调（最多 10 秒）

连接成功日志：

```
INFO stockquant.execution.ctp: CTP SDK (openctp_ctp.thosttraderapi) 已加载
INFO stockquant.execution.ctp: CTP 前置连接成功
INFO stockquant.execution.ctp: CTP 认证成功
INFO stockquant.execution.ctp: CTP 登录成功: user=<user>, trading_day=<yyyymmdd>
```

### CTP 交易注意事项

- **数量单位为「手」而非「股」**：CTP Broker **不强制** 100 整数倍校验
  （与 QMT/XTP 不同），下单数量直接作为 `VolumeTotalOriginal` 传入。
- **不同合约每手数量不同**：如 IF 每手 300、rb 每手 10，需在策略层换算。
- **买卖方向与开平仓**：买入映射为 `Direction=Buy` + `CombOffsetFlag=Open`（买入开仓），
  卖出映射为 `Direction=Sell` + `CombOffsetFlag=Close`（卖出平仓）。
  若需平昨仓，需使用 `THOST_FTDC_OF_CloseYesterday="4"`（当前实现默认平仓）。
- **持仓区分多空**：查询返回 `long_qty`（多头，`PosiDirection='2'`）与
  `short_qty`（空头，`PosiDirection='3'`）。
- **资金含保证金**：余额查询返回 `cash`（Available）、`frozen`（FrozenMargin+FrozenCash）、
  `equity`（Balance）、`margin`（CurrMargin）。

### CTP 订单类型映射

| OrderType | CTP OrderPriceType | LimitPrice |
|-----------|--------------------|------------|
| `LIMIT` | `"2"` (`THOST_FTDC_OPT_LimitPrice`) | `order.price` |
| `MARKET` | `"1"` (`THOST_FTDC_OPT_AnyPrice`) | `0.0` |

报单有效期固定为 `GFD`（当日有效，`TimeCondition="3"`），
成交触发条件为立即（`ContingentCondition="1"`），投机套保标志为投机
（`CombHedgeFlag="1"`）。

---

## 配置示例

StockQuant 通过 **settings 键** 与 **`.env` 环境变量** 两套机制配置券商参数。
settings 键由 `stockquant/api/routers/trading.py` 的 `_get_broker()` 读取并实例化 Broker；
`.env` 变量由 `stockquant/config.py` 与 `stockquant/api/routers/settings.py` 加载映射。

### 1. 切换实盘模式

必须同时设置以下两项才能进入实盘：

| settings key | 说明 | 取值 |
|--------------|------|------|
| `trading.broker` | 交易模式 | `"paper"`（模拟）/ `"live"`（实盘） |
| `trading.api` | 券商类型 | `"qmt"` / `"xtp"` / `"ctp"` |

### 2. QMT 配置

**settings 键**（`_get_broker()` 实际读取）：

| settings key | 类型 | 说明 |
|--------------|------|------|
| `qmt.path` | str | QMT 客户端 userdata 目录绝对路径 |
| `qmt.account` | str | 资金账号 |

**`.env` 变量**：

```env
TRADING_BROKER=live
# trading.api 默认为 qmt，可不显式设置
QMT_PATH=D:\国金QMT交易端\userdata_mini
QMT_ACCOUNT=你的资金账号
# QMT_PASSWORD 预留，QMTBroker 当前不使用（客户端已登录）
```

### 3. XTP 配置

**settings 键**：

| settings key | 类型 | 说明 |
|--------------|------|------|
| `xtp.user` | str | XTP 资金账号 |
| `xtp.password` | str | 交易密码（存储时加密，读取时解密） |
| `xtp.app_id` | int | 中泰证券分配的应用 ID |
| `xtp.client_id` | int | 客户端 ID（0–99，同一 app_id 下唯一） |
| `xtp.server_addr` | str | 交易服务器地址 `ip:port`（默认端口 6002） |
| `xtp.software_key` | str | 软件密钥 |

**`.env` 变量**：

```env
TRADING_BROKER=live
TRADING_API=xtp
XTP_USER=你的XTP资金账号
XTP_PASSWORD=你的交易密码
XTP_APP_ID=1
XTP_CLIENT_ID=1
XTP_SERVER_ADDR=120.27.164.138:6002
XTP_SOFTWARE_KEY=你的软件密钥
```

### 4. CTP 配置

**settings 键**：

| settings key | 类型 | 说明 |
|--------------|------|------|
| `ctp.user` | str | CTP 资金账号（InvestorID） |
| `ctp.password` | str | 交易密码（存储时加密，读取时解密） |
| `ctp.broker_id` | str | 期货公司 BrokerID |
| `ctp.front_addr` | str | 交易前置地址 `tcp://ip:port` |
| `ctp.app_id` | str | AppID（部分期货公司需要，可留空） |

**`.env` 变量**：

```env
TRADING_BROKER=live
TRADING_API=ctp
CTP_USER=你的CTP资金账号
CTP_PASSWORD=你的交易密码
CTP_BROKER_ID=9999
CTP_FRONT_ADDR=tcp://180.168.146.187:10201
CTP_APP_ID=你的AppID
```

> **密码加密**：XTP 与 CTP 的密码在 settings 中存储时会加密，
> 实例化时通过 `_decrypt_value()` 解密后传入 Broker。QMT 不涉及密码。

### 5. 模拟盘（默认）

不进行任何券商配置时，`trading.broker` 默认为 `paper`，
系统使用 `PaperBroker` 执行模拟交易，无需安装任何券商 SDK。

---

## 故障排查常见问题

### 通用问题

**Q: 日志显示 `xxx 未安装，XXX Broker 将以模拟模式运行`？**

A: 对应券商 SDK 未安装成功。请按各券商章节的 `pip install` 命令安装，
并用 `python -c "import ..."` 验证。SDK 为可选依赖，未安装时 Broker
自动降级模拟模式，不会报错，但订单不会真实成交（审计日志状态为 `SIMULATED`）。

**Q: 日志显示 `XXXBroker 导入失败，降级为 LiveBroker 骨架`？**

A: Broker 模块本身导入异常（非 SDK 缺失）。检查
`stockquant/execution/brokers/` 下的文件是否完整，以及
`stockquant.models` / `stockquant.engine` 等依赖模块是否可正常导入。

**Q: 订单被 `REJECTED`，审计日志显示 `quantity not multiple of 100`？**

A: QMT 与 XTP 强制 A 股 100 股整数倍校验（见 `place_order()` 开头）。
请确保下单数量为 100 的整数倍。CTP（期货）不受此限制。

### QMT 专项

**Q: `QMT 连接失败: <error>，降级为模拟模式`？**

A: 可能原因：
1. QMT 客户端未启动或未登录 —— 请先启动客户端并完成登录，保持前台运行。
2. `qmt.path` 指向的 userdata 目录不正确 —— 确认路径为客户端安装目录下的
   `userdata_mini`（极简模式）或 `userdata`（完整模式）。
3. `xtquant` 与客户端版本不匹配 —— 使用客户端自带的 `xtquant` 包。

**Q: 持仓/余额查询返回空？**

A: `get_positions()` / `get_balance()` 在未连接时返回空字典/默认值。
连接正常但查询异常时，`query_stock_positions` / `query_stock_asset` 抛出异常
会被捕获并返回空，请检查客户端是否处于正常交易状态。

### XTP 专项

**Q: `XTP 连接超时`？**

A: `connect()` 等待前置连接回调最多 10 秒（100 × 0.1s）。
请检查：
1. `xtp.server_addr` 的 `ip:port` 是否正确（默认端口 6002）。
2. 网络是否可达（防火墙/安全组是否放行）。
3. `client_id` 是否与同 `app_id` 下其他客户端冲突。

**Q: `XTP 登录失败: session_id=0`？**

A: `Login()` 返回的 `session_id <= 0` 表示登录失败。检查：
1. `xtp.user` / `xtp.password` 是否正确。
2. `xtp.app_id` 是否由中泰证券正式分配。
3. `xtp.software_key` 是否已通过 `SetSoftwareKey` 设置且有效。

**Q: `OnFrontDisconnected: reason=<n>`？**

A: 前置连接断开，`_connected` 与 `_logged_in` 均置为 `False`，
后续操作将降级模拟模式。需排查网络中断或服务器维护。

### CTP 专项

**Q: `CTP 前置连接超时`？**

A: `OnFrontConnected` 回调未在 10 秒内触发。检查：
1. `ctp.front_addr` 是否以 `tcp://` 开头且地址端口正确。
2. 实盘与仿真（SimNow）前置地址不同，确认使用的是对应环境的地址。
3. 交易时段外 CTP 前置可能关闭，请在交易时段内连接。

**Q: `CTP 认证失败` 或 `CTP 登录失败`？**

A:
1. 认证失败（`OnRspAuthenticate` 中 `ErrorID != 0`）：`app_id` 未在期货公司备案，
   或该期货公司不需要认证（可留空 `ctp.app_id`，代码会跳过认证）。
2. 登录失败（`OnRspUserLogin` 中 `ErrorID != 0`）：`broker_id` / `user` / `password`
   不匹配，或账号未开通程序化交易权限。

**Q: CTP 持仓/余额查询返回的是缓存值？**

A: CTP 查询为异步回调机制：`get_positions()` / `get_balance()` 发起查询请求后
立即返回 `_positions_cache` / `_asset_cache`，真实结果通过
`OnRspQryInvestorPosition` / `OnRspQryTradingAccount` 回调更新缓存。
首次查询可能返回空，需稍后再次查询获取最新值。

**Q: 期货下单数量应该填多少？**

A: CTP 以「手」为单位，`place_order()` 不做数量校验，`quantity` 直接作为
`VolumeTotalOriginal` 传入。请按合约规则换算（如 IF 每手 300 元 × 指数点）。
策略层应自行确保数量为合约最小变动单位的整数倍。

**Q: 如何平昨仓而非平今仓？**

A: 当前实现卖出固定映射为 `CombOffsetFlag=Close`（平仓）。
若需区分平今/平昨（上期所部分品种需区分），需扩展 `ctp_broker.py`
引入 `OrderSide` 之外的平仓方向参数，使用
`THOST_FTDC_OF_CloseYesterday="4"`（平昨）或
`THOST_FTDC_OF_CloseToday="3"`（平今）。
