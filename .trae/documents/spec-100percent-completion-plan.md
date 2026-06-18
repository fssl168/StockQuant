# StockQuant 前端 100% 达标率完善计划

> **目标**: 将前端功能达标率从 88% 提升至 100%，修复所有代码层面可解决的差距项
> **基准**: `frontend-product-spec-gap-assessment-v2.md` (v3 更新版) + 前端代码扫描报告
> **原则**: 自行判断优先级，自行决策，聚焦代码层面可修复的差距

---

## 一、当前差距项分析

### v3 报告剩余 5 项 (R1-R5)
| # | 差距项 | 性质 | 可否代码修复 |
|---|--------|------|-------------|
| R1 | Portfolio 权益曲线历史快照 | 数据机制 | ✅ 可添加后端快照机制 |
| R2 | 券商真实 API 下单 | 外部依赖 | ❌ 需 SDK 部署 |
| R3 | NLP 情感分析模型升级 | 精度优化 | ✅ 可集成 HuggingFace |
| R4 | NFR 测试 CI 强制执行 | 工程规范 | ✅ 可添加 CI 配置 |
| R5 | 本地 HuggingFace 模型推理 | 性能优化 | ✅ 可集成本地模型 |

### 前端扫描发现的具体代码差距
| # | 差距项 | 文件 | 优先级 |
|---|--------|------|--------|
| F1 | Strategy AI 生成策略功能标注"开发中" | Strategy.tsx:222,225 | P0 |
| F2 | Monitor 动态风控数据使用 mock | Monitor.tsx:71 | P1 |
| F3 | Portfolio 行业分布/历史交易/风险指标硬编码 mock | Portfolio.tsx:33,45,48 | P1 |
| F4 | Data 采集日志硬编码 mock | Data.tsx | P1 |
| F5 | Data K线查询 mock fallback | Data.tsx:77,122 | P1 |
| F6 | Optimize 导出结果/应用到回测按钮无实现 | Optimize.tsx | P1 |
| F7 | Data 下载按钮无实现 | Data.tsx | P2 |
| F8 | notification.py 认证依赖缺失 (v3 唯一安全缺口) | notification.py | P0 |

---

## 二、实施计划 (按优先级排序)

### Phase 1: P0 核心功能修复 (2 项)

#### 1.1 修复 Strategy AI 生成策略功能 (F1)
- **文件**: `web/src/pages/Strategy.tsx`
- **问题**: 第 222、225 行 `message.info('AI 策略生成功能开发中')` — AI 生成策略 Modal 已存在但按钮点击只弹提示
- **修复**: 接入已有的 `/api/ai/strategy/generate` 端点，实现 AI 策略生成 Modal 的完整交互
- **验证**: 输入自然语言描述 → 点击生成 → 调用 API → 返回策略代码 → 插入编辑器

#### 1.2 修复 notification.py 认证依赖 (F8)
- **文件**: `stockquant/api/routers/notification.py`
- **问题**: `mark_as_read` 和 `delete_notification` 端点缺少认证依赖
- **修复**: 添加 `current_user` 依赖注入
- **验证**: 未认证请求返回 401

### Phase 2: P1 数据真实化 (4 项)

#### 2.1 Portfolio 真实数据接入 (F3)
- **文件**: `web/src/pages/Portfolio.tsx`
- **问题**: `industryData`、`tradeHistory`、`riskMetrics` 为硬编码 mock
- **修复**:
  - `industryData`: 从持仓数据按行业分组计算（后端添加行业分类接口或前端映射）
  - `tradeHistory`: 调用 `tradingApi.getTrades()` 获取真实成交记录
  - `riskMetrics`: 调用 `/api/portfolio/risk-metrics` 或从持仓数据计算
- **验证**: 页面展示的数据与后端 API 返回一致

#### 2.2 Monitor 动态风控真实数据 (F2)
- **文件**: `web/src/pages/Monitor.tsx`
- **问题**: 第 71 行 `// F026: 加载动态风控数据 (mock, 后续接入 API)`
- **修复**: 调用后端 `/api/monitor/risk-status` 或从 `monitorApi` 获取真实风控数据
- **验证**: 风控面板展示真实市场环境、风险等级、动态参数

#### 2.3 Data 页面真实数据接入 (F4, F5)
- **文件**: `web/src/pages/Data.tsx`
- **问题**: 采集日志硬编码 mock；K线查询有 mock fallback
- **修复**:
  - 采集日志: 调用 `/api/data/collect-logs` 获取真实日志，无日志时显示空表
  - K线查询: 移除 `generateMockKline`，API 失败时显示错误提示而非 mock 数据
- **验证**: 数据展示与后端一致，无 mock 数据

#### 2.4 Optimize 按钮功能实现 (F6)
- **文件**: `web/src/pages/Optimize.tsx`
- **问题**: "导出结果"和"应用到回测"按钮无 onClick
- **修复**:
  - "导出结果": 将优化排名表导出为 CSV/JSON
  - "应用到回测": 将最佳参数填充到回测页面（通过 URL params 或 store 传递）
- **验证**: 按钮点击后有实际功能响应

### Phase 3: P2 功能完善 (3 项)

#### 3.1 Data 下载按钮实现 (F7)
- **文件**: `web/src/pages/Data.tsx`
- **问题**: 数据源表格中"下载"按钮无 onClick
- **修复**: 调用 `/api/data/download` 触发数据下载，显示进度
- **验证**: 点击下载后有实际下载行为

#### 3.2 Portfolio 权益曲线快照机制 (R1)
- **文件**: 后端 `stockquant/api/routers/portfolio.py` + 前端 `Portfolio.tsx`
- **问题**: 权益曲线为模拟生成，无历史快照
- **修复**:
  - 后端: 添加 `equity_snapshots` 表，每日收盘后保存权益快照
  - 后端: `/api/portfolio/equity-curve` 优先从快照表读取
  - 前端: 无需修改（API 返回真实数据后自动展示）
- **验证**: 权益曲线展示真实历史数据

#### 3.3 NFR 测试 CI 门控 (R4)
- **文件**: 新建 `.github/workflows/nfr-gate.yml` 或类似
- **问题**: NFR 测试存在但未在 CI 中强制执行
- **修复**: 添加 CI 配置，在 PR 合并前强制运行 NFR 测试
- **验证**: CI pipeline 包含 NFR 测试步骤

### Phase 4: P3 高级优化 (2 项)

#### 4.1 NLP 情感分析模型升级 (R3)
- **文件**: `stockquant/ai/` 相关模块
- **问题**: 当前使用关键词规则，精度受限
- **修复**: 集成 HuggingFace `transformers` 管线（如 `clue/albert-base-chinese-sst`）
- **验证**: 情感分析准确率提升（对比测试）

#### 4.2 本地 HuggingFace 模型推理 (R5)
- **文件**: `stockquant/agent/llm_adapter.py`
- **问题**: NFR008 要求 Tick 级 <200ms，当前依赖远程 LLM
- **修复**: 添加 `LocalLLM` 适配器，支持 Ollama/HuggingFace 本地推理
- **验证**: 本地模型调用延迟 <200ms

---

## 三、执行策略

1. **Phase 1 → Phase 2 → Phase 3 → Phase 4** 顺序执行
2. 每个 Phase 内的任务可并行
3. 每完成一个任务，运行 `npx tsc --noEmit` 验证前端编译
4. 每完成一个任务，运行 `python -c "import stockquant.api.main"` 验证后端
5. R2（券商真实 API）为外部依赖，不在代码修复范围内，标记为"骨架完整，待 SDK 部署"

---

## 四、验收标准

- [ ] F1: Strategy AI 生成策略可实际调用 API 并返回代码
- [ ] F8: notification.py 认证依赖完整
- [ ] F3: Portfolio 无硬编码 mock 数据
- [ ] F2: Monitor 风控面板展示真实数据
- [ ] F4/F5: Data 页面无 mock 数据
- [ ] F6: Optimize 按钮功能完整
- [ ] F7: Data 下载按钮功能完整
- [ ] R1: Portfolio 权益曲线有历史快照机制
- [ ] R4: NFR 测试 CI 门控配置
- [ ] R3: NLP 情感分析模型升级
- [ ] R5: 本地模型推理支持
- [ ] 前端 `npx tsc --noEmit` 零错误
- [ ] 后端 `python -c "import stockquant.api.main"` 成功
