架构设计
========

系统架构
--------

StockQuant 采用分层架构设计:

1. **数据层** — DataFeed 抽象 + 多数据源（BaoStock/AkShare/AlphaFeed）
2. **引擎层** — Cerebro 回测引擎 + PaperBroker/LiveBroker 交易引擎
3. **策略层** — BaseStrategy + 7 个内置模板 + 仓位管理器
4. **AI 层** — Agent Orchestrator + 6 个 Agent + LLM Adapter
5. **API 层** — FastAPI REST + WebSocket 实时推送
6. **前端层** — React 18 + TypeScript + Ant Design 5

模块组织
--------

.. code-block:: text

   stockquant/
   ├── api/              # FastAPI 路由 + WebSocket
   ├── agent/            # ReAct Agent + LLM Adapter + 工具注册
   ├── ai/               # AI 信息处理（采集/记忆/反幻觉/管线）
   ├── brokers/          # 交易引擎（Paper/QMT/XTP/CTP）
   ├── data/             # 数据源 + 缓存
   ├── engine/           # 回测引擎（Cerebro）
   ├── indicators/       # 技术指标（30+）
   ├── models/           # 数据模型（Order/Portfolio/Signal）
   ├── persistence/      # ORM + 数据库
   ├── strategy/         # 策略基类 + 模板 + 信号
   └── config.py         # 全局配置

关键设计决策
------------

1. **三级降级机制** — LLM 调用支持远程 → 本地 LLM → 规则引擎降级
2. **幂等性 + 崩溃恢复** — 订单 idempotency_key + JSON 持久化
3. **4 级 JWT 认证** — current/required/admin/trader + UserRole 枚举
4. **F020 信息处理闭环** — 采集 → 降噪 → 总结 → 升华 4 阶段
5. **反幻觉五步纠正** — 事实验证 → 来源验证 → 逻辑一致性 → 交叉验证 → 置信度
