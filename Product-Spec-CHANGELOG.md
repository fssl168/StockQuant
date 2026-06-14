# Product-Spec-CHANGELOG

> 产品需求变更记录

---

## v2.0.0 — AI 驱动全流程闭环增强

**日期**：2026-06-14
**作者**：AI 产品经理
**来源**：基于 `stockquant-deep-analysis.md` 升级路线图 + 用户 AI 驱动需求

### 变更内容

- **初始产品需求文档创建**
- **AI 驱动全流程闭环设计**：从"量化框架"升级为"AI 原生交易平台"
- **7 个 AI Agent 功能需求**：F019-F027
  - F019：AI 数据采集 Agent（P0）— 多源采集 + 情感分析 + 结构化
  - F020：AI 指标发现 Agent（P1）— 自动推荐指标和参数
  - F021：AI 策略生成 Agent（P0）— 自然语言 → 策略代码
  - F022：AI 回测解读 Agent（P1）— 自然语言解读 + 过拟合检测
  - F023：AI 实时盯盘 Agent（P1）— 行情 + 消息面联动
  - F024：AI 辅助决策 Agent（P0）— 交易建议 + 风险预警
  - F025：AI 动态风控 Agent（P1）— 市场环境自适应风控
  - F026：AI 策略回测对比 Agent（P2）
  - F027：AI 自然语言交互界面（P2）
- **AI 原生架构设计**：
  - AI Agent Orchestrator 中枢架构
  - LLM 适配层（OpenAI/Claude/本地 Ollama）
  - 数据采集器模块（东方财富/雪球/财联社/巨潮/上交所）
  - NLP 处理链（情感分析 + 信息抽取 + 分类）
  - AI 数据存储（SQLite/PostgreSQL）
- **新增非功能需求**：NFR008（AI 性能与成本）、NFR009（AI 可靠性）
- **新增 AI 配置方案**：YAML 配置驱动
- **新增 AI API 设计预览**：对话式策略开发 + AI 配置
- **总工期延长**：16-22 周 → 24-32 周（6-8 个月）
- **新增 AI 相关风险与缓解**

### 关键设计决策

| 决策 | 理由 |
|------|------|
| AI Agent 作为独立模块（`ai/`），不与核心引擎耦合 | 核心回测/交易功能不依赖 AI 可用性，LLM 不可用时降级为规则引擎 |
| LLM 提供商抽象层 | 避免供应商锁定，支持 OpenAI/Claude/本地模型热切换 |
| 情感分析双方案（本地 HuggingFace 模型 + LLM 降级） | 本地模型零成本但准确率有限，LLM 准确率高但有成本，双方案平衡 |
| 全自动模式需人工确认 | 防止 LLM 幻觉导致误交易，合规要求 |
| AI 决策必须引用来源 | 可追溯性，避免 AI 编造数据 |
| 爬虫多源冗余 | 单一数据源被反爬时不影响整体数据采集 |
| AI 功能 P0/P1/P2 分级 | 数据采集 + 策略生成 + 辅助决策为 P0（核心差异），其余逐步推进 |
| **AI 记忆 + 反幻觉内建于全流程** | 记忆和反幻觉不再是独立模块，而是深度嵌入采集→降噪→总结→升华 每个环节。每个环节都有对应的记忆读写和反幻觉检查点 |

### v2.0.1 — 项目经理复核修复（2026-06-14）

> 基于项目经理对 Product-Spec.md 的全面复核，修复 14 个问题。

- **Fix #1**：删除重复的 F020 条目（原 F018 消息推送内容的重复遗留），修正功能编号
- **Fix #2**：明确 F023（盯盘 Agent=信号探测器）与 F024（决策 Agent=信号决策器）的职责边界，添加"与 F023 的边界"说明
- **Fix #3**：新增信号优先级矩阵，定义三层优先级：传统策略信号 > AI 辅助信号 > AI 生成策略信号
- **Fix #4**：新增 F019「信号管线系统」功能需求（P0），定义 AI 信号↔策略信号双向转换、信号冲突解决、A 股规则约束
- **Fix #5**：F020-F025 AI Agent 章节全部补充 A 股规则约束（T+1、100 股整数倍、涨跌停范围、预估费用）
- **Fix #6**：`ai/memory/summarizer.py` 重命名为 `ai/memory/memory_lifecycle.py`，避免与顶层 `ai/summarizer.py` 命名冲突
- **Fix #7**：F019（原 F020 AI 信息处理全流程）工期从 5 周调整为 7 周，总工期从 28-36 周调整为 36-48 周，附工期说明
- **Fix #8**：NFR008 拆分为轻量模式（< 200ms，本地模型）和完整模式（< 3s，LLM），解决与 NFR009 的性能互斥
- **Fix #9**：Scrapers 从 DataAgent 和 CollectionStage 两处独立定义改为共享基础设施（`ai/scrapers/`），两处均引用同一份
- **Fix #10**：目标用户排序调整为"资深个人开发者→专业量化研究员→金融工程学生"，新增"渐进式平台定位"说明
- **Fix #11**：新增 Agent 间通信协议定义（`AIEvent` 事件总线 + 异步事件驱动 + 共享内存）
- **Fix #12**：F022 回测解读补充"回测模式说明"——回测模式下 AI 仅做后分析，不实时介入交易流
- **Fix #13**：F015 自定义指标 DSL 从 P2 提升至 P1，与 F004 同步开发
- **Fix #14**：v1 vs v2 对比表新增 4 个 AI 维度（记忆系统/反幻觉/AI 数据存储/AI 配置机制）
- **编号调整**：原 F019（AI 信息处理全流程）重新编号为 F020，原 F020-F027 顺延为 F021-F028

### v2.0.2 — Web 前端架构补全（2026-06-14）

> 产品需求文档补充前端架构开发步骤和流程，完成从后端核心到完整用户界面的闭环设计。

- **新增 F029「Web Dashboard 前端」**（P1，4 周）：React 18 + TypeScript + Vite + Ant Design 5 + ECharts + Monaco Editor
  - 10 个页面完整定义（Dashboard / Backtest / BacktestResult / Strategy / Monitor / AIChat / Portfolio / DataManage / Settings / Login）
  - 3 条核心交互流程（回测流程 / AI 对话流程 / 实时盯盘流程）
  - 公共组件库定义（Chart/Table/AI/Monitor/common 五大类）
  - 状态管理（Zustand 5 个 store）
  - 验收标准：首屏 < 3s、图表渲染 < 2s、推送延迟 < 500ms
- **新增 F030「前后端集成部署」**（P1，2 周）：Docker Compose + Nginx 反向代理 + FastAPI Uvicorn
- **新增 api/ 包结构**（FastAPI 网关）：7 个路由模块 + WebSocket + Pydantic schemas
- **新增 web/ 包结构**（React 前端）：170+ 文件层级定义
- **新增 5.2 Web 前端架构**：架构图 + 前后端交互模式 + 实时数据流
- **新增 5.3 API 网关（FastAPI）**：完整 RESTful + WebSocket 路由表 + 消息格式
- **技术栈扩展**：新增前端依赖（React/ECharts/Zustand/Monaco）、后端依赖（FastAPI/Uvicorn/Pydantic/JWT/WebSocket）
- **API 设计预览扩展**：新增 Web API 调用示例（TypeScript/Axios/WebSocket/SSE）
- **工期调整**：总估时 36-48 周 → 40-52 周（10-13 个月），F029(4 周)+F030(2 周)与后端并行
- **发布计划调整**：v2.0.0 从第 32 周延至第 36 周，新增 v2.1.0（第 48 周）高级功能迭代
- **测试策略扩展**：新增前端测试（Jest + React Testing Library + Cypress E2E）
- **风险扩展**：新增 4 个前端风险（依赖冲突/CORS/WebSocket 稳定性/大表格渲染卡顿）
- **成功指标扩展**：新增 5 个前端相关指标（首屏加载/API 延迟/推送延迟/E2E 通过率）
- **总功能数**：F001-F030，共 30 个功能需求（20 传统量化 + 8 AI + 2 前端）

### v2.0.3 — 系统设置页详细设计（2026-06-14）

> 参考 autoquant 项目 Settings.vue（Vue3 + Element Plus）UI 效果，以及 runtime.py（14 分组白名单配置体系），设计 StockQuant 2.0 前端 Settings 页面的详细参数项和 UI 规格。

- **参考源**：
  - `D:\projects\autoquant\frontend\src\views\Settings.vue`（暗色科技感 UI + 向导/专家双模式）
  - `D:\projects\autoquant\src\utils\runtime.py`（ALLOWED_SETTINGS 白名单 14 分组 + 完整 UI 元数据）
  - `D:\projects\autoquant\src\web\api\settings_api.py`（Settings RESTful API）
  - `D:\projects\autoquant\config\settings.py`（Pydantic Settings 配置结构）
- **新增 Settings 页设计**（嵌入 F029 Web Dashboard 前端章节）：
  - 14 个配置分组完整映射表（autoquant 14 分组 → StockQuant 14 分组，按实际功能精简参数）
  - 后台 API 设计：5 个端点（GET /api/settings, POST /api/settings/save, DELETE /api/settings/:key, GET /api/settings/whitelist）
  - API 响应格式 JSON Schema 示例（groups + items 结构，含完整 UI 元数据：value_type/when/slider/secret/scale/unit/options/order 等）
  - 前端 Settings 页面实现规格（React + Ant Design 复刻 Element Plus 布局）：
    - 暗色主题 CSS Variables + 紫色渐变横幅 + 毛玻璃效果
    - 专家模式：Collapse 折叠 + grid 布局（label | control | status | action）
    - 向导模式：Steps 分步导航（6 步）
    - 动态控件：value_type → Select/Switch/InputNumber+Slider/Input.Password/TimePicker/Textarea
    - 条件显隐（when 依赖字段）
    - 密钥掩码（secret 字段）
    - Dirty 追踪 + 浮动保存条
    - 管理员口令二次确认（Modal）
- **页面组件更新**：`pages/Settings.tsx` 描述扩展为完整配置中心设计
