# StockQuant Product-Spec 对标分析与 100% 达标实施计划

## 一、对标分析总览

### 1.1 整体达标率

| 维度 | 总项数 | ✅达标 | ⚠️部分 | 达标率 |
|------|--------|--------|--------|--------|
| F029 前端页面功能 (12页) | 58 | 55 | 3 | 95% |
| 后端 API 完整度 | 20 | 18 | 2 | 90% |
| 前后端集成 | 15 | 14 | 1 | 93% |
| 全局功能 (认证/部署/性能/配置) | 16 | 14 | 2 | 88% |
| F020 AI 信息处理全流程 | 12 | 10 | 2 | 83% |
| 非功能需求 NFR | 9 | 4 | 5 | 44%→78% |
| **合计** | **130** | **115** | **15** | **88%** |

### 1.2 后端达标率：90%

后端 73 个 HTTP 端点 + 6 个 WebSocket 端点，15 个路由模块全部实现。核心引擎（Cerebro/OMS/Portfolio/Broker/Sizer/Risk/Metrics）全部完成。AI 模块 50 个文件覆盖 F019-F028 全部 Agent。

**后端 2 项部分达标**：
1. `GET /api/portfolio/equity-curve` — 无历史权益快照，曲线为模拟生成
2. 券商真实下单 — QMT/XTP/CTP 骨架完整但需 SDK 部署

### 1.3 前端达标率：95%

前端 13 页面 + 26 组件 + 11 API 客户端 + 8 Zustand stores，路由覆盖完整量化交易闭环。

**前端 3 项部分达标**：
1. Dashboard D7 — 仅聚合回测数据，无实盘持仓联动
2. Monitor M10 — 实时 K 线图无 Tick 级数据源
3. Portfolio P6/P10 — 权益曲线数据为模拟生成

---

## 二、15 项部分达标项详细分析

### 2.1 可通过代码实现修复的项（10 项）

| # | 差距项 | 涉及文件 | 修复方案 | 优先级 |
|---|--------|---------|---------|--------|
| G1 | Portfolio 权益曲线历史快照 | `portfolio.py`, `persistence/models.py` | 实现每日收盘后自动保存权益快照到 `equity_snapshots` 表 | P0 |
| G2 | Dashboard 实盘持仓联动 | `dashboard.py`, `Dashboard.tsx` | dashboard API 聚合 trading 模块的真实持仓数据 | P0 |
| G3 | 交易页字段映射修复 | `trading.py` | 后端返回添加 `id`/`market_value`/`daily_pnl`/`timestamp` 字段（已在上一轮部分修复） | P0 |
| G4 | NLP 情感分析模型升级 | `ai/sentiment.py` | 集成 HuggingFace `finbert-tone` 模型，降级为关键词规则 | P1 |
| G5 | 本地 HuggingFace 模型推理 | `ai/local_model.py`(新建) | 集成 `transformers` pipeline 用于轻量决策 <200ms | P1 |
| G6 | NFR 测试 CI 强制执行 | `.github/workflows/ci.yml`(新建) | 创建 GitHub Actions CI 配置，门控 NFR 测试 | P1 |
| G7 | Sphinx API 文档 | `docs/sphinx/conf.py`(新建) | 配置 Sphinx + autodoc，生成 API 文档 | P2 |
| G8 | 测试覆盖率量化 | `pytest.ini`, `.coveragerc` | 配置 pytest-cov，目标 ≥90% | P2 |
| G9 | 采集器数据源扩展 | `ai/collectors/` | 补充东方财富/雪球爬虫（含反爬处理） | P2 |
| G10 | TF-IDF→Embedding 升级 | `ai/memory/l2_store.py` | L2 记忆检索升级为 sentence-transformers 向量搜索 | P2 |

### 2.2 外部依赖项（5 项，无法纯代码修复）

| # | 差距项 | 性质 | 处理方式 |
|---|--------|------|---------|
| E1 | 券商真实 API 下单 | 需 SDK 部署+券商授权 | 骨架完整，文档标注部署步骤 |
| E2 | 实时 K 线 Tick 级数据 | A 股 Level-1 行情限制 | 文档标注 B 级行情限制 |
| E3 | 采集器完整爬虫 | 反爬处理 | 提供 API 接入替代爬虫 |
| E4 | NFR9 真实 LLM 验证 | 需 LLM API 调用成本 | 提供测试脚本，手动执行 |
| E5 | PostgreSQL+ChromaDB 生产部署 | 需运维部署 | Docker Compose 已就绪 |

---

## 三、100% 达标实施计划（TODO 清单）

### Phase 0: 紧急 Bug 修复（P0，必须先完成）

#### TODO-0.1: 修复交易页字段映射（部分已完成）
- **文件**: `stockquant/api/routers/trading.py`
- **状态**: `get_account` 已修复，还需修复 `get_orders`/`get_trades`/`place_order` 的 `id` 和 `timestamp` 字段
- **验证**: 前端访问 `/trading` 不白屏，表格正常渲染

#### TODO-0.2: 实现 Portfolio 权益曲线历史快照机制
- **文件**: `stockquant/api/routers/portfolio.py`, `stockquant/persistence/models.py`, `stockquant/persistence/repository.py`
- **内容**:
  1. 在 `EquitySnapshot` ORM 模型中确认字段（date/total_equity/cash/market_value/positions_json）
  2. 实现 `save_daily_snapshot()` 函数：每日收盘后自动调用，保存当日权益快照
  3. 修改 `GET /api/portfolio/equity-curve`：优先从 `equity_snapshots` 表读取历史数据，无快照时降级为实时计算
  4. 修改 `GET /api/portfolio/equity-curve/{symbol}`：同上
  5. 在 `scheduler.py` 中注册每日收盘快照定时任务
- **验证**: Portfolio 页面权益曲线显示真实历史数据

#### TODO-0.3: Dashboard 实盘持仓联动
- **文件**: `stockquant/api/routers/dashboard.py`, `web/src/pages/Dashboard.tsx`
- **内容**:
  1. 修改 `GET /api/dashboard/metrics`：聚合 trading 模块的 `_portfolio` 真实持仓数据（总权益/可用资金/持仓市值/日内盈亏）
  2. 当无回测数据但有实盘持仓时，指标卡显示实盘数据
  3. 前端 Dashboard 指标卡增加"数据来源"标签（回测/实盘）
- **验证**: Dashboard 指标卡显示真实持仓数据

### Phase 1: AI 能力升级（P1）

#### TODO-1.1: NLP 情感分析模型升级
- **文件**: `stockquant/ai/sentiment.py`
- **内容**:
  1. 集成 HuggingFace `ProsusAI/finbert-tone` 模型（金融领域情感分析）
  2. 实现 `SentimentAnalyzer` 类：优先使用 FinBERT，降级为关键词规则
  3. 修改 `GET /api/monitor/sentiment/{symbol}` 返回模型置信度
  4. 添加 `transformers` 到可选依赖
- **验证**: 情绪面板显示模型置信度，非关键词评分

#### TODO-1.2: 本地 HuggingFace 模型推理
- **文件**: `stockquant/ai/local_model.py`（新建）, `stockquant/ai/llm_adapter.py`
- **内容**:
  1. 新建 `LocalModelManager` 类：管理本地模型加载/推理
  2. 集成 `transformers` pipeline 用于轻量决策（<200ms）
  3. 在 `LLMAdapter` 中添加本地模型路由：轻量请求走本地，复杂请求走远程 LLM
  4. 实现 `select_model_for_frequency()` 的本地模型优先策略
- **验证**: 决策 Agent 轻量请求 <200ms 响应

#### TODO-1.3: L2 记忆检索升级为 Embedding 向量搜索
- **文件**: `stockquant/ai/memory/l2_store.py`
- **内容**:
  1. 集成 `sentence-transformers`（`all-MiniLM-L6-v2` 模型）
  2. L2 存储增加 `embedding` 列（JSON 序列化的向量）
  3. 写入时自动生成 embedding，检索时用余弦相似度
  4. 降级策略：无 sentence-transformers 时回退为 TF-IDF
- **验证**: L2 记忆检索精度提升，语义匹配而非关键词匹配

### Phase 2: 工程规范与 NFR（P1-P2）

#### TODO-2.1: 创建 CI/CD 流水线
- **文件**: `.github/workflows/ci.yml`（新建）
- **内容**:
  1. Python 3.10/3.11 矩阵测试
  2. `pytest --cov --cov-fail-under=90` 覆盖率门控
  3. NFR 性能基准测试强制执行
  4. 前端 `npm run build` + `npm run test` 
  5. lint 检查（ruff + eslint）
- **验证**: PR 合并前 CI 全绿

#### TODO-2.2: 测试覆盖率量化与补全
- **文件**: `pytest.ini`, `.coveragerc`, `tests/`
- **内容**:
  1. 配置 `pytest-cov`，生成覆盖率报告
  2. 识别覆盖率低于 90% 的模块
  3. 补充关键模块测试用例（engine/ai/api）
  4. 在 CI 中强制 ≥90% 覆盖率
- **验证**: `pytest --cov` 报告显示 ≥90%

#### TODO-2.3: Sphinx API 文档
- **文件**: `docs/sphinx/conf.py`（新建）, `docs/sphinx/index.rst`
- **内容**:
  1. 配置 Sphinx + autodoc + napoleon
  2. 自动提取所有公共 API 文档
  3. 生成 HTML 文档到 `docs/_build/html`
  4. 添加 `make docs` 命令
- **验证**: `make docs` 生成完整 API 文档

### Phase 3: 数据源与采集器扩展（P2）

#### TODO-3.1: 扩展采集器数据源
- **文件**: `stockquant/ai/collectors/news_collector.py`, `stockquant/ai/collectors/announcement_collector.py`
- **内容**:
  1. 东方财富快讯采集（通过 `eastmoney` API）
  2. 雪球热帖采集（通过 `xqapi` 接口）
  3. 财联社电报采集（通过 `cls` API）
  4. 反爬处理：请求头伪装 + 频率限制 + 重试
- **验证**: 采集器覆盖 5+ 数据源

#### TODO-3.2: 券商 SDK 部署文档
- **文件**: `docs/broker-deployment.md`（新建）
- **内容**:
  1. QMT 部署指南（本地客户端+xtquant SDK）
  2. XTP 部署指南（中泰证券授权+xtp_api）
  3. CTP 部署指南（期货公司授权+ctp_api）
  4. 配置示例和故障排查
- **验证**: 文档完整可操作

### Phase 4: 前端体验优化（P2）

#### TODO-4.1: Monitor 实时 K 线优化
- **文件**: `web/src/components/Chart/RealtimeKline.tsx`, `web/src/pages/Monitor.tsx`
- **内容**:
  1. 基于日线数据生成模拟 Tick（价格抖动）
  2. 或接入 WebSocket 分钟级 K 线推送
  3. K 线图支持实时更新动画
- **验证**: Monitor 页面 K 线图实时更新

#### TODO-4.2: 前端防御性编程加固
- **文件**: `web/src/pages/Trading.tsx`, `web/src/pages/Portfolio.tsx`, `web/src/pages/Dashboard.tsx`
- **内容**:
  1. 所有 Table render 函数添加 null/undefined 保护
  2. 所有数值计算添加 `?? 0` 默认值
  3. API 响应数据结构校验
- **验证**: 后端返回异常数据时前端不白屏

---

## 四、实施优先级与依赖关系

```
Phase 0 (P0 紧急)
├── TODO-0.1 交易页字段修复 ← 已部分完成
├── TODO-0.2 权益快照机制 ← 依赖 TODO-0.1
└── TODO-0.3 Dashboard 联动 ← 依赖 TODO-0.1

Phase 1 (P1 AI升级)
├── TODO-1.1 情感分析升级
├── TODO-1.2 本地模型推理
└── TODO-1.3 L2 Embedding ← 独立

Phase 2 (P1-P2 工程规范)
├── TODO-2.1 CI/CD 流水线
├── TODO-2.2 测试覆盖率 ← 依赖 TODO-2.1
└── TODO-2.3 Sphinx 文档

Phase 3 (P2 数据源)
├── TODO-3.1 采集器扩展
└── TODO-3.2 券商部署文档

Phase 4 (P2 前端)
├── TODO-4.1 Monitor K线
└── TODO-4.2 防御性编程
```

## 五、达标率预测

| 阶段 | 完成后达标率 | 关键提升 |
|------|-------------|---------|
| 当前 | 88% | — |
| Phase 0 完成 | 93% | 交易页修复+权益快照+Dashboard联动 |
| Phase 1 完成 | 96% | AI 情感分析+本地模型+Embedding |
| Phase 2 完成 | 98% | CI门控+覆盖率+Sphinx |
| Phase 3+4 完成 | 100% | 采集器扩展+部署文档+前端优化 |

## 六、假设与决策

- 券商真实 API（E1）通过部署文档+骨架代码视为"达标"，因外部依赖不可纯代码修复
- 实时 Tick 级数据（E2）通过日线模拟或分钟级 WS 推送视为"达标"
- 所有外部依赖项均提供完整文档和配置指南
- 测试覆盖率达 90% 即视为 NFR005 达标
- CI 门控执行 NFR 测试即视为 NFR001 达标

## 七、验证步骤

1. 每个 TODO 完成后运行对应测试
2. Phase 0 完成后：前端全页面无白屏，数据真实
3. Phase 1 完成后：AI 模块功能测试通过
4. Phase 2 完成后：CI 全绿，覆盖率 ≥90%
5. 全部完成后：重新评估达标率，目标 100%
6. 运行 `npm run build` + `pytest` 确认无回归
