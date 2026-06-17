# StockQuant Spec 对齐执行计划 — 剩余 25 项

> **目标**: 完成剩余 25 项 Todo，从当前 ~55% 达标率推进至 100%
> **已完成**: Phase 0.1-0.3, Phase 1.1-1.3 (6 项)
> **策略**: 按依赖链顺序执行，先修核心闭环 → 再补功能缺失 → 最后完善高级功能和 NFR

---

## 当前状态总结

| 阶段 | 已完成 | 待完成 | 达标率 |
|------|--------|--------|--------|
| Phase 0 | 3/3 | 0 | 100% |
| Phase 1 | 3/6 | 3 | 50% |
| Phase 2 | 0/12 | 12 | 0% |
| Phase 3 | 0/10 | 10 | 0% |

---

## Phase 1 剩余 (3 项)

### 1.4 JWT 认证 + 登录联动

**现状**: `deps.py` 有 `get_required_user` 但只有 `trading.py`(place_order/cancel_order) 和 `settings.py`(save_settings) 使用了它。其他路由全部无认证。

**修改文件**:
1. `stockquant/api/deps.py` — JWT secret 从环境变量读取，移除默认值
2. `stockquant/api/routers/trading.py` — 所有端点添加 `Depends(get_required_user)`
3. `stockquant/api/routers/settings.py` — 所有端点添加 `Depends(get_required_user)`
4. `stockquant/api/routers/portfolio.py` — 敏感端点添加认证
5. `stockquant/api/routers/signal.py` — 写操作添加认证
6. `stockquant/api/routers/monitor.py` — 写操作添加认证
7. `stockquant/api/routers/notification.py` — 写操作添加认证
8. `stockquant/api/routers/comparison.py` — 写操作添加认证

**规则**:
- 写操作(POST/PUT/DELETE) → `get_required_user`
- 只读操作(GET) → `get_current_user`（允许匿名浏览）
- auth 路由本身不需要认证

### 1.5 PaperBroker 实时数据集成

**现状**: PaperBroker 不主动获取行情，`get_positions()`/`get_balance()`/`get_history()` 返回硬编码空数据。`trading.py` 已有 `_get_latest_bar()` 获取 BaoStock 行情。

**修改文件**:
1. `stockquant/engine/broker.py` — PaperBroker 类
   - `get_positions()`: 从绑定的 Portfolio 获取真实持仓
   - `get_balance()`: 从绑定的 Portfolio 获取真实余额
   - `get_history()`: 从交易审计日志获取成交记录
   - `on_bar(bar)`: 接收行情数据，检查 LIMIT 订单是否可成交
   - 添加 `bind_portfolio(portfolio)` 方法绑定 Portfolio 实例
2. `stockquant/api/routers/trading.py` — 绑定 PaperBroker 与 Portfolio

### 1.6 F025 决策模式前端 UI

**现状**: 后端 DecisionAgent 完整实现三种模式(AUTO/SEMI_AUTO/READ_ONLY)，但前端无 UI。

**修改文件**:
1. `web/src/pages/Settings.tsx` — 在 AI 模型分组添加 `decision.mode` 下拉选择
2. `web/src/pages/Monitor.tsx` — 添加决策模式切换 Segmented
3. `web/src/pages/AIChat.tsx` — 添加 `decision` 模式到 ChatMode 类型

---

## Phase 2 (12 项)

### 2.1 AIChat 模式切换接入

**现状**: AIChat.tsx 有 mode 状态但未传给 ChatPanel 组件。ChatPanel 不感知当前模式。

**修改文件**:
1. `web/src/pages/AIChat.tsx` — 将 `mode` 和 `onModeChange` 传给 ChatPanel
2. `web/src/components/AI/ChatPanel.tsx` — 接收 mode prop，根据模式显示不同欢迎语

### 2.2 Settings 条件显隐

**现状**: `isVisible()` 已支持 `when` 字段，但缺少交易模式联动和通知渠道条件显示。

**修改文件**:
1. `web/src/pages/Settings.tsx` — GROUPS 中添加更多 when 条件:
   - QMT 配置项 when `trading.broker=qmt`（已有）
   - 实盘风控参数 when `trading.mode=live`
   - 通知渠道配置 when 对应渠道启用

### 2.3 通知数据持久化

**现状**: 后端已有 SQLite 持久化（`_persist_notification()`），但 Session 使用不规范。

**修改文件**:
1. `stockquant/api/routers/notification.py` — 优化 Session 使用，使用 sessionmaker

### 2.4 对比历史持久化

**现状**: `_comparison_history` 纯内存列表，重启丢失。

**修改文件**:
1. `stockquant/api/routers/comparison.py` — 替换为 SQLite 持久化
   - 新建 `comparison_results` 表
   - `_save_comparison()` / `_load_comparisons()` 函数

### 2.5 通知通道补全

**现状**: 后端有 9 种通知器，前端 NotifierForm 只有 4 项。通知路由未调用 MessageRouter。

**修改文件**:
1. `web/src/components/Settings/NotifierForm.tsx` — 添加飞书/Discord/PushPlus/ServerChan/Webhook 配置
2. `stockquant/api/routers/settings.py` — 添加新通道的环境变量映射
3. `stockquant/api/routers/notification.py` — add_notification 时调用 MessageRouter 发送

### 2.6 F013 报表 API 暴露

**现状**: `ReportGenerator` 完整实现，但无 REST 端点。

**修改文件**:
1. `stockquant/api/routers/backtest.py` — 添加 `GET /backtest/{task_id}/report` 端点
2. `web/src/pages/BacktestResult.tsx` — 添加"导出报表"按钮

### 2.7 调度器 API 暴露

**现状**: `StockScheduler` 完整实现，但无 REST 端点，未与应用集成。

**修改文件**:
1. 新建 `stockquant/api/routers/scheduler.py` — CRUD 端点
2. `stockquant/api/main.py` — 注册路由 + lifespan 启动调度器
3. 新建 `web/src/api/scheduler.ts` — 前端 API 客户端
4. `web/src/pages/Settings.tsx` — 添加调度管理区域

### 2.8 F020 采集环节

**现状**: `pipeline/collection.py` 已有基础采集器，但缺少多源爬虫和来源验证。

**修改文件**:
1. 新建 `stockquant/ai/collectors/` 目录
2. 新建 `base.py` — 采集器基类
3. 新建 `news_collector.py` — AkShare 新闻采集
4. 新建 `announcement_collector.py` — 公告采集
5. 新建 `social_collector.py` — 社交媒体采集
6. 新建 `verifier.py` — 来源验证+事实初筛
7. 修改 `stockquant/ai/orchestrator.py` — 集成采集编排器

### 2.9 F020 记忆系统 L2/L3

**现状**: `memory/` 目录有 4 层记忆系统骨架，但 L2/L3 未完整实现。

**修改文件**:
1. 新建 `stockquant/ai/memory/l2_store.py` — SQLite + TF-IDF 语义检索
2. 新建 `stockquant/ai/memory/l3_store.py` — ChromaDB 向量存储
3. 新建 `stockquant/ai/memory/manager.py` — 统一管理 L1/L2/L3
4. 新建 `stockquant/ai/memory/forgetting.py` — 遗忘机制
5. 新建 `stockquant/ai/memory/compressor.py` — 记忆压缩

### 2.10 F020 反幻觉检查点

**现状**: `hallucination/pipeline.py` 有基础管线，但缺少 8 检查点和五步纠正。

**修改文件**:
1. 新建 `stockquant/ai/hallucination/checkpoints.py` — 8 个检查点函数
2. 新建 `stockquant/ai/hallucination/corrector.py` — 五步纠正流程
3. 新建 `stockquant/ai/hallucination/modes.py` — 4 种触发模式
4. 修改 `hallucination/pipeline.py` — 接入检查点

### 2.11 F024 消息面联动

**现状**: MonitorAgent 有基础扫描，但无新闻-持仓联动分析。

**修改文件**:
1. `stockquant/ai/monitor_agent.py` — 添加 `analyze_news_correlation()` 方法
2. `stockquant/api/routers/monitor.py` — 添加 `GET /monitor/news-correlation` 端点

### 2.12 F024 AI 信号融合

**现状**: 无信号融合机制。

**修改文件**:
1. 新建 `stockquant/ai/signal_fusion.py` — 三源融合（技术面+情绪面+基本面）
2. `stockquant/ai/orchestrator.py` — 集成信号融合
3. `stockquant/api/routers/monitor.py` — 添加 `GET /monitor/fused-signals` 端点

---

## Phase 3 (10 项)

### 3.1 LiveBroker 券商 API

**修改文件**:
1. `stockquant/engine/broker.py` — LiveBroker 类（QMT 集成）
2. 新建 `stockquant/execution/brokers/qmt_broker.py`
3. `stockquant/api/routers/trading.py` — 根据 broker_mode 选择 PaperBroker/LiveBroker

### 3.2 F028 对话式交互完善

**修改文件**:
1. `stockquant/ai/chat_agent.py` — 不同模式不同工具集
2. `web/src/pages/AIChat.tsx` — 模式感知 UI

### 3.3 Docker Compose 完整部署

**修改文件**:
1. `docker-compose.yml` — 添加 Redis 服务
2. 新建 `web/nginx/default.conf` — 反向代理配置
3. `stockquant/api/main.py` — CORS 生产配置

### 3.4 NFR 性能基准测试

**修改文件**:
1. 新建 `tests/test_nfr_performance.py`

### 3.5 F020 降噪/总结/升华闭环

**修改文件**:
1. 新建 `stockquant/ai/pipeline/denoiser.py`
2. 新建 `stockquant/ai/pipeline/summarizer.py`
3. 新建 `stockquant/ai/pipeline/elevator.py`
4. 修改 `stockquant/ai/pipeline/orchestrator.py`

### 3.6 幻觉数据库

**修改文件**:
1. 新建 `stockquant/ai/hallucination/database.py`
2. 修改 `stockquant/persistence/models.py` — HallucinationRecord ORM

### 3.7 F027 策略组合优化

**修改文件**:
1. `stockquant/ai/comparison_agent.py` — 添加组合优化
2. `stockquant/api/routers/comparison.py` — 添加优化端点
3. `web/src/pages/Comparison.tsx` — 添加组合优化 Tab

### 3.8 F027 策略生命周期建议

**修改文件**:
1. `stockquant/ai/comparison_agent.py` — 添加生命周期建议
2. `web/src/pages/Comparison.tsx` — 添加生命周期建议面板

### 3.9 NFR008/009 AI 可靠性测试

**修改文件**:
1. 新建 `tests/test_nfr_ai_reliability.py`

### 3.10 NFR002 可靠性补全

**修改文件**:
1. `stockquant/api/routers/trading.py` — 订单幂等性
2. `stockquant/engine/broker.py` — 崩溃恢复
3. 新建 `tests/test_nfr_reliability.py`

---

## 执行优先级

```
1.4 JWT认证 → 1.5 PaperBroker → 1.6 决策模式UI
→ 2.1 AIChat模式 → 2.2 Settings条件 → 2.3 通知持久化 → 2.4 对比持久化
→ 2.5 通知通道 → 2.6 报表API → 2.7 调度器API
→ 2.8 F020采集 → 2.9 F020记忆 → 2.10 F020反幻觉
→ 2.11 F024消息面 → 2.12 F024信号融合
→ 3.1 LiveBroker → 3.2 F028对话 → 3.3 Docker
→ 3.4 NFR性能 → 3.5 F020闭环 → 3.6 幻觉数据库
→ 3.7 F027组合优化 → 3.8 F027生命周期 → 3.9 NFR AI → 3.10 NFR可靠性
```

## 验证策略

- 每完成一项，运行 `pytest tests/` 确保不引入回归
- 每完成一个 Phase，检查验收标准
- 前端修改后运行 `cd web; npx tsc --noEmit` 检查类型
