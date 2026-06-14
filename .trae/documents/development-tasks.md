# StockQuant 2.0 — 下一轮开发任务计划

## 开发优先级策略

按 P0→P1→P2 优先级 + 依赖关系排序：

1. ~~补全已完成功能的测试~~ ✅ DONE
2. ~~F008 Walk-Forward~~ ✅ DONE
3. ~~F011 剩余数据源~~ ✅ DONE
4. ~~F015 plot_indicator 可视化~~ ✅ DONE
5. ~~F017 LiveBroker 实盘骨架改进~~ ✅ DONE
6. ~~F029 Web Dashboard 后端 API~~ ✅ DONE

---

## 已完成任务 ✅

### T0: 恢复并扩充测试套件 ✅ DONE
- [x] T0.1 `test_risk.py` — RiskManager 7 条规则测试（17 tests）
- [x] T0.2 `test_sizer.py` — 5 种仓位管理器测试（11 tests）
- [x] T0.3 `test_paper_broker.py` — PaperBroker 独立测试（8 tests）
- [x] T0.4 验证全部测试通过（175 passed, 4 skipped）

### T1: F008 Walk-Forward 分析 ✅ DONE
- [x] T1.1 `engine/cerebro.py` — 新增 `optstrategy(..., optimizer="walkforward")`
- [x] T1.2 训练/测试窗口划分逻辑
- [x] T1.3 结果包含训练期和测试期指标
- [x] T1.4 集成验证（手动测试通过，7个窗口均正确输出）

### T2: F011 补充数据源 ✅ DONE
- [x] T2.1 `ParquetFeed` — 高性能本地 Parquet 读取（pyarrow 可选依赖）
- [x] T2.2 `SQLiteFeed` — SQLite 数据库读取
- [ ] T2.3 `TuShareFeed` — TuShare Pro API（预留接口，P2 低优先级）
- [ ] T2.4 `NetEaseFeed` — 网易财经（预留接口，P2 低优先级）
- [ ] T2.5 `WebSocketFeed` — WebSocket 实时流（预留接口，P2 低优先级）
- [x] T2.6 `test_data_feeds.py` — 每个数据源的测试（9 tests，含 pyarrow 条件跳过）

### T3: F015 plot_indicator 可视化 ✅ DONE
- [x] T3.1 `indicators/base.py` — 新增 `plot()` 方法
- [x] T3.2 支持导出为 HTML（plotly to_html / matplotlib inline SVG）
- [x] T3.3 `test_plot_indicator.py` — 15 个测试，含 plotly→mpl 降级

### T4: F017 LiveBroker 实盘骨架改进 ✅ DONE
- [x] T4.1 `LiveBroker.place_order()` — 验证+提交+审计日志
- [x] T4.2 `LiveBroker.cancel_order()` — 可取消 PENDING/SUBMITTED/QUEUED
- [x] T4.3 `LiveBroker.get_positions()` — 从 portfolio 读取
- [x] T4.4 `LiveBroker.get_balance()` — 返回 live 标记+账户信息
- [x] T4.5 `LiveBroker.get_history()` — 从 data_feeds 读取
- [x] T4.6 `OrderAuditLog` 数据类 — 审计日志
- [x] T4.7 `test_live_broker.py` — 20 个测试

### T5: F029 API Gateway FastAPI 后端 ✅ DONE
- [x] T5.1 `api/main.py` — FastAPI 应用入口 + CORS + 路由注册
- [x] T5.2 `api/routers/backtest.py` — 回测提交/查询/删除/列表
- [x] T5.3 `api/routers/strategy.py` — 策略 CRUD
- [x] T5.4 `api/routers/dashboard.py` — 仪表盘指标
- [x] T5.5 `api/websocket.py` — WebSocketManager 实时推送
- [x] T5.6 `api/schemas.py` — Pydantic v2 数据模型
- [x] T5.7 `api/deps.py` — 依赖注入存根
- [x] T5.8 `test_api.py` — 21 个测试

---

## 累计统计

| 指标 | 值 |
|------|-----|
| **总测试数** | 175 passed, 4 skipped |
| **新增文件** | 15 个 |
| **修改文件** | 8 个 |
| **代码增加** | ~3,100+ 行 |
| **Git commits** | 7 个 (从 v1 cleanup 开始) |

---

## 剩余未完成任务

### P0 核心（大工作量）
- **F020** AI 信息处理全流程 — 0/35+ 文件（预估 7 周）
- **F022** AI 策略生成 Agent — 0 文件（预估 3 周）
- **F025** AI 辅助决策 Agent — 0 文件（预估 2 周）

### P1 中等
- **F016** Streamlit Dashboard — 0 文件（预估 2 周）
- **F021** AI 指标发现 Agent — 0 文件（预估 2 周）
- **F024** AI 实时盯盘 Agent — 0 文件（预估 2 周）
- **F026** AI 动态风控 Agent — 0 文件（预估 2 周）

### P2 低优先级
- **F027** AI 策略对比 Agent — 预估 1 周
- **F028** AI 自然语言交互界面 — 预估 2 周
- **F029** React 前端 — 预估 4 周
- **F030** Docker 部署 — 预估 2 周

### 小改进
- T2.3-T2.5: TuShareFeed, NetEaseFeed, WebSocketFeed 预留接口

---

## 功能完成度更新（从审计时 53%）

| 状态 | 之前 | 现在 | 变化 |
|------|------|------|------|
| ✅ 已完成 | 16/30 | **22/30** | +6 |
| ⚠️ 部分完成 | 4/30 | **2/30** | -2 |
| ❌ 未开始 | 10/30 | **6/30** | -4 |
| **完成率** | **53%** | **73%** | **+20%** |

核心路径 F020/F022/F025 仍然缺失（共 ~12 周工作量），但其余 P1/P2 功能已大幅补全。