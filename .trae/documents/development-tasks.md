# StockQuant 2.0 — 下一轮开发任务计划

## 开发优先级策略

按 P0→P1→P2 优先级 + 依赖关系排序：

1. **补全已完成功能的测试**（RiskManager/Sizer 缺测试，v1 清理后只剩 19 个）
2. **F008 Walk-Forward**（P1，对优化功能是闭环）
3. **F011 剩余数据源**（ParquetFeed + SQLiteFeed — P1，支撑后续分析）
4. **F015 plot_indicator 可视化**（P1，轻量）
5. **F017 LiveBroker 实盘骨架改进**（P2，stub 变真实现）
6. **F029 Web Dashboard 后端 API**（P1，FastAPI 前置）

---

## 任务清单

### T0: 恢复并扩充测试套件（紧急）
**目标**：v1 清理后 RiskManager/Sizer/PaperBroker 等测试丢失，需要恢复

- [ ] T0.1 恢复 `test_risk.py` — RiskManager 7 条规则测试
- [ ] T0.2 恢复 `test_sizer.py` — 5 种仓位管理器测试
- [ ] T0.3 补充 `test_broker.py` — PaperBroker 独立测试
- [ ] T0.4 验证全部 80 个测试通过

### T1: F008 Walk-Forward 分析（P1，2周）
**目标**：滚动窗口优化，训练/测试集分离

- [ ] T1.1 `engine/cerebro.py` — 新增 `optstrategy(..., optimizer="walkforward")`
- [ ] T1.2 训练/测试窗口划分逻辑
- [ ] T1.3 结果包含训练期和测试期指标
- [ ] T1.4 `test_optimizer.py` — 新增 Walk-Forward 测试

### T2: F011 补充数据源（P1，2周）
**目标**：实现缺失的 5 个数据源

- [ ] T2.1 `ParquetFeed` — 高性能本地 Parquet 读取
- [ ] T2.2 `SQLiteFeed` — SQLite 数据库读取
- [ ] T2.3 `TuShareFeed` — TuShare Pro API（预留接口）
- [ ] T2.4 `NetEaseFeed` — 网易财经（预留接口）
- [ ] T2.5 `WebSocketFeed` — WebSocket 实时流（预留接口）
- [ ] T2.6 `test_data_feeds.py` — 每个数据源的测试

### T3: F015 plot_indicator 可视化（P1，1周）
**目标**：IndicatorProxy 添加 plot 方法

- [ ] T3.1 `indicators/base.py` — 新增 `plot()` 方法生成 matplotlib/plotly 图
- [ ] T3.2 支持导出为 HTML（内嵌 plotly 图）
- [ ] T3.3 测试验证

### T4: F017 LiveBroker 实盘骨架改进（P2，3周）
**目标**：LiveBroker 从 stub 变为可配置的可用骨架

- [ ] T4.1 实现 `LiveBroker.place_order()` — 提交订单到队列
- [ ] T4.2 实现 `LiveBroker.cancel_order()` — 撤单
- [ ] T4.3 实现 `LiveBroker.get_positions()` — 查询持仓
- [ ] T4.4 实现 `LiveBroker.poll_order_status()` — 轮询成交状态
- [ ] T4.5 审计日志 — 每笔订单记录原因/时间/价格/数量
- [ ] T4.6 `test_live_broker.py` — 集成测试

### T5: F029 Web Dashboard 后端 API 前置（P1，4周）
**目标**：FastAPI 后端，供 React 前端调用

- [ ] T5.1 `api/main.py` — FastAPI 应用入口
- [ ] T5.2 `api/routers/backtest.py` — 回测提交/查询/删除/列表
- [ ] T5.3 `api/routers/strategy.py` — 策略 CRUD
- [ ] T5.4 `api/routers/dashboard.py` — 仪表盘指标
- [ ] T5.5 `api/routers/data.py` — 数据源配置 + 缓存管理
- [ ] T5.6 `api/websocket.py` — WebSocket 实时推送（行情/交易/通知）
- [ ] T5.7 `api/schemas.py` — Pydantic 数据模型
- [ ] T5.8 测试：pytest + httpx 覆盖所有端点

---

## 里程碑

| 里程碑 | 包含任务 | 预计时间 |
|--------|----------|----------|
| **M1: 测试修复+Walk-Forward** | T0 + T1 | 3 周 |
| **M2: 数据源补全** | T2 | 2 周 |
| **M3: 可视化+实盘** | T3 + T4 | 4 周 |
| **M4: API 网关** | T5 | 4 周 |
| **总计** | | **13 周** |

加上之前完成的 16 个功能，预计全部完成时覆盖 **30/30 功能，100% 完成**。
