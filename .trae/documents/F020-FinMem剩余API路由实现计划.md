# F020-FinMem 三模块架构增强 — 剩余 API 路由实施计划

> **本计划是 `F020-FinMem剩余差距修复执行计划.md` 的续作**，聚焦剩余 5 个任务的实施。
> 用户授权：自行决策优先级，无需征求意见。

---

## 一、Summary（总体结论）

### 1.1 进度复核（截至本次复核）

| 差距编号 | 描述 | 状态 | 备注 |
|:---:|:---|:---:|:---|
| GAP-H1 | checkpoints.py 集成 ClaimVerifier | ✅ 已修复 | v1 计划完成 |
| GAP-H2 | pipeline.py 集成 CrossValidator | ✅ 已修复 | v1 计划完成 |
| GAP-L1 | scheduler.py 公开 API | ✅ 已修复 | v1 计划完成 |
| GAP-H3 | main.py 启动 PipelineScheduler | ✅ 已修复 | [main.py#L63-L88](file:///d:/projects/StockQuant/stockquant/api/main.py#L63-L88) lifespan + 绑定 pipeline |
| GAP-M1 | hallucination/__init__.py 导出 | ✅ 已修复 | 13 个公共类已导出 |
| GAP-M2 | memory/__init__.py 导出 | ✅ 已修复 | 11 个公共类已导出 |
| GAP-M3 | collectors/__init__.py 导出 | ✅ 已修复 | 11 个公共类已导出 |
| GAP-M4 | pipeline/__init__.py 导出 | ✅ 已修复 | 6 个公共类已导出 |
| GAP-M8 | orchestrator.py F020→F025 桥接 | ✅ 已修复 | [orchestrator.py#L24](file:///d:/projects/StockQuant/stockquant/ai/orchestrator.py#L24) 导入 InsightsBridge + [L202-L244](file:///d:/projects/StockQuant/stockquant/ai/orchestrator.py#L202-L244) 构造 DecisionContext |
| **GAP-M5** | **新增 PipelineScheduler API 端点** | ❌ 待修复 | `api/routers/pipeline_scheduler.py` 缺失 |
| **GAP-M6** | **新增 CollectorAuditLog 查询 API 端点** | ❌ 待修复 | `api/routers/pipeline_audit.py` 缺失 |
| **GAP-M7** | **新增 ClaimVerifier/CrossValidator API 端点** | ❌ 待修复 | `api/routers/hallucination_verify.py` 缺失（注意已有 `hallucination.py` 但仅含配置/记录，无验证调用） |
| **GAP-L2** | **新增 UserProfileHistory 查询 API 端点** | ❌ 待修复 | `api/routers/profiling.py` 缺失 |

**当前完成度**：8/13 差距已修复（约 88%）→ 本计划完成后达到 100%。

### 1.2 关键架构发现

1. **`hallucination.py` 已存在但不重复**：现有 [api/routers/hallucination.py](file:///d:/projects/StockQuant/stockquant/api/routers/hallucination.py) 仅含 4 个管理端点（config/records/analysis/suggestions），不包含 ClaimVerifier/CrossValidator 的验证调用。GAP-M7 应新建独立文件 `hallucination_verify.py`，与现有路由协同。
2. **`pipeline.py` 已存在但不含调度器端点**：现有 [api/routers/pipeline.py](file:///d:/projects/StockQuant/stockquant/api/routers/pipeline.py) 提供 run/collect/config/status 端点，不与 PipelineScheduler 重叠。GAP-M5 应新建 `pipeline_scheduler.py`，与 `pipeline.py` 并列注册。
3. **认证模式**：现有路由统一使用 `Depends(get_current_user)` 与 `Depends(get_admin_user)`（[api/deps.py](file:///d:/projects/StockQuant/stockquant/api/deps.py)），新路由保持一致。
4. **APIRouter prefix**：现有路由使用 `router = APIRouter(tags=[...])`，路径写在端点装饰器上（如 `@router.get("/pipeline/config")`），main.py 统一加 `/api` prefix。

---

## 二、Current State Analysis（关键接口签名）

### 2.1 PipelineScheduler（GAP-M5 依赖）

- **位置**：[stockquant/ai/scheduler.py](file:///d:/projects/StockQuant/stockquant/ai/scheduler.py)
- **单例**：`get_scheduler()` 返回 `PipelineScheduler` 实例
- **关键 API**：
  - `async start()` — 启动调度器
  - `async stop()` — 停止调度器
  - `status() -> Dict[str, Any]` — 返回 `{"is_running": bool, "tasks": [...], ...}`
  - `list_tasks() -> List[ScheduleSpec]` — 列出所有调度任务
  - `add_task(spec: ScheduleSpec) -> None` — 添加任务
  - `remove_task(name: str) -> bool` — 移除任务
  - `is_running: bool` — 属性
- **ScheduleSpec dataclass**：name/level/interval_seconds/daily_hour/daily_minute/symbols/enabled/last_run_at/last_result/run_count/error_count

### 2.2 CollectorAuditLog（GAP-M6 依赖）

- **位置**：[stockquant/ai/collectors/audit_log.py](file:///d:/projects/StockQuant/stockquant/ai/collectors/audit_log.py)
- **单例**：`get_audit_log()` 返回 `CollectorAuditLog` 实例
- **关键 API**：
  - `query(limit=100, offset=0, collector=None, action=None, source=None, result=None) -> List[AuditEntry]` — 同步查询
  - `stats() -> Dict[str, int]` — 返回 `{"total", "success", "failure", "partial", "skipped"}`
  - `summary() -> Dict[str, Any]` — 返回 size/max_size/stats/success_rate/collectors/sources
  - `count_by_collector() -> Dict[str, int]`
  - `count_by_source() -> Dict[str, int]`
  - `success_rate() -> float`
  - `clear() -> int`
- **AuditEntry dataclass**：collector/action/source/result/count/error/timestamp/duration_ms/metadata

### 2.3 ClaimVerifier + CrossValidator（GAP-M7 依赖）

- **位置**：[stockquant/ai/hallucination/claim_verifier.py](file:///d:/projects/StockQuant/stockquant/ai/hallucination/claim_verifier.py)、[cross_validator.py](file:///d:/projects/StockQuant/stockquant/ai/hallucination/cross_validator.py)
- **ClaimVerifier 关键 API**：
  - `@staticmethod classify_claim(text: str) -> ClaimType` — **同步**静态方法，返回 `ClaimType` 枚举（NUMERIC/TEMPORAL/ENTITY_ATTR/COMPARATIVE/REGULATORY/COMPUTATIONAL）
  - `async verify_claim(text: str, claim_type: Optional[ClaimType] = None) -> ClaimVerification` — 异步验证单个声明
  - `async verify_claims_batch(claims: List[str]) -> List[ClaimVerification]` — 批量验证
- **ClaimVerification dataclass**：claim/claim_type/verified/score/evidence/source/error
- **CrossValidator 关键 API**：
  - `async verify(claim: str) -> VerifyResult` — 多模型交叉验证
  - `async verify_batch(claims: List[str]) -> List[VerifyResult]`
- **VerifyResult dataclass**：claim/consensus/verdict/confidence/models/agreement_score/disagreements
- **模块级函数**：`async multi_model_verify(claim: str) -> VerifyResult`（便利封装）

### 2.4 ProfilingManager（GAP-L2 依赖）

- **位置**：[stockquant/ai/profiling/manager.py](file:///d:/projects/StockQuant/stockquant/ai/profiling/manager.py)
- **构造**：`ProfilingManager(db_url=None, user_id="test_user", transitioner=None)` — 自动初始化 DB 或降级内存
- **关键 API**（注意参数顺序与原计划文档不同）：
  - `get_profile(user_id: Optional[str] = None) -> RiskProfile` — 读取
  - `get_params(user_id: Optional[str] = None) -> ProfileParams` — 获取决策参数
  - `update_profile(new_profile: RiskProfile, user_id: Optional[str] = None, trigger: str = TRIGGER_MANUAL, context: Optional[TransitionContext] = None) -> None` — **第一个参数是 new_profile，不是 user_id**
  - `evaluate_transition(context: TransitionContext, user_id: Optional[str] = None) -> Optional[RiskProfile]`
  - `get_history(user_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]`
- **RiskProfile 枚举**：CONSERVATIVE/NEUTRAL/AGGRESSIVE（值："conservative"/"neutral"/"aggressive"），含 `from_str(s)` 类方法
- **ProfileParams dataclass**：max_position_pct/stop_loss_pct/take_profit_pct/max_drawdown_tolerance/confidence_threshold

---

## 三、Proposed Changes（剩余任务清单 — 按执行顺序）

### 修复优先级原则

1. **Batch 3（4 任务，可并行）**：新建 4 个 API 路由文件 — 让用户能通过 HTTP 操作 F020 新功能
2. **Batch 4（1 任务）**：在 main.py 注册 4 个新路由 + 全量回归测试 — 完成集成与验证

---

### Batch 3：新增 4 个 API 路由（4 任务，可并行）

#### Task 7（Medium）：GAP-M5 — 新增 PipelineScheduler API 路由

- **新文件**：`d:\projects\StockQuant\stockquant\api\routers\pipeline_scheduler.py`
- **目的**：让运维/前端能通过 HTTP 控制 PipelineScheduler 的启停、查看状态、管理调度任务
- **端点设计**：
  | 方法 | 路径 | 认证 | 说明 |
  |------|------|------|------|
  | GET | `/pipeline/scheduler/status` | get_current_user | 返回调度器状态 + 任务列表 |
  | POST | `/pipeline/scheduler/start` | get_admin_user | 启动调度器（已运行则返回当前状态） |
  | POST | `/pipeline/scheduler/stop` | get_admin_user | 停止调度器 |
  | GET | `/pipeline/scheduler/tasks` | get_current_user | 列出所有 ScheduleSpec |
  | POST | `/pipeline/scheduler/tasks` | get_admin_user | 添加新调度任务（body: ScheduleSpec 字典） |
  | DELETE | `/pipeline/scheduler/tasks/{name}` | get_admin_user | 移除指定调度任务 |
- **实现要点**：
  - 使用 `from stockquant.ai.scheduler import get_scheduler, ScheduleSpec`
  - 所有端点用 `try/except Exception` 包裹，失败返回 500 + `{"detail": str(exc)}`
  - `start` 端点已运行时返回 `{"already_running": True, "status": ...}` 不报错
  - `add_task` 端点接收 JSON body，构造 `ScheduleSpec(**body)` 后调用 `scheduler.add_task(spec)`
- **验收**：`GET /api/pipeline/scheduler/status` 返回 200 + `{"is_running": bool, "task_count": int, "tasks": [...]}`

---

#### Task 8（Medium）：GAP-M6 — 新增 CollectorAuditLog 查询 API 路由

- **新文件**：`d:\projects\StockQuant\stockquant\api\routers\pipeline_audit.py`
- **目的**：让运维能查询采集器审计日志，定位采集失败、追踪数据来源
- **端点设计**：
  | 方法 | 路径 | 认证 | 说明 |
  |------|------|------|------|
  | GET | `/pipeline/audit` | get_current_user | 查询审计日志（支持 query 过滤 + 分页） |
  | GET | `/pipeline/audit/stats` | get_current_user | 返回统计 + 摘要 |
  | GET | `/pipeline/audit/by-collector` | get_current_user | 按采集器分组计数 |
  | GET | `/pipeline/audit/by-source` | get_current_user | 按数据源分组计数 |
  | DELETE | `/pipeline/audit` | get_admin_user | 清空审计日志（返回清除数量） |
- **Query 参数**（GET `/pipeline/audit`）：`limit=100`、`offset=0`、`collector`、`action`、`source`、`result`
- **实现要点**：
  - 使用 `from stockquant.ai.collectors.audit_log import get_audit_log`
  - 调用 `log.query(...)` / `log.stats()` / `log.summary()` / `log.count_by_collector()` / `log.count_by_source()` / `log.clear()`
  - 返回 `AuditEntry` 列表时用 `[e.to_dict() for e in entries]` 序列化
- **验收**：`GET /api/pipeline/audit?limit=10` 返回 200 + List[Dict]；`GET /api/pipeline/audit/stats` 返回 `{"total": N, "success": N, ...}`

---

#### Task 9（Medium）：GAP-M7 — 新增 ClaimVerifier/CrossValidator API 路由

- **新文件**：`d:\projects\StockQuant\stockquant\api\routers\hallucination_verify.py`
- **目的**：让前端/外部系统能调用反幻觉验证能力，对单条声明做六类分类 + 多模型交叉验证
- **端点设计**：
  | 方法 | 路径 | 认证 | 说明 |
  |------|------|------|------|
  | POST | `/hallucination/verify/classify` | get_current_user | 同步分类声明类型（classify_claim） |
  | POST | `/hallucination/verify/claim` | get_current_user | 异步验证单条声明（verify_claim） |
  | POST | `/hallucination/verify/claims-batch` | get_current_user | 异步批量验证（verify_claims_batch） |
  | POST | `/hallucination/verify/cross-validate` | get_current_user | 多模型交叉验证（CrossValidator.verify） |
- **Body Schema**（Pydantic 风格或 Dict[str, Any]）：
  - `classify` / `claim` / `cross-validate`：`{"text": "茅台2023年净利润同比增长30%"}`
  - `claims-batch`：`{"claims": ["...", "...", "..."]}`
- **实现要点**：
  - 使用 `from stockquant.ai.hallucination import ClaimVerifier, ClaimType, CrossValidator`
  - `classify` 端点同步调用 `ClaimVerifier.classify_claim(text)` → 返回 `{"claim_type": "numeric", ...}`
  - `claim` / `claims-batch` / `cross-validate` 端点用 `async def` 直接 `await` 调用（FastAPI 原生支持异步）
  - 返回 `ClaimVerification` / `VerifyResult` 用 `dataclasses.asdict()` 转字典
- **验收**：
  - `POST /api/hallucination/verify/classify` body=`{"text":"茅台2023年净利润同比增长30%"}` → 200 + `{"claim_type": "numeric"}`
  - `POST /api/hallucination/verify/cross-validate` body=`{"text":"..."}` → 200 + `{"consensus": ..., "verdict": ..., "confidence": ...}`

---

#### Task 10（Low）：GAP-L2 — 新增 ProfilingManager API 路由

- **新文件**：`d:\projects\StockQuant\stockquant\api\routers\profiling.py`
- **目的**：让前端能查询/更新用户风险偏好，查看历史转换记录
- **端点设计**：
  | 方法 | 路径 | 认证 | 说明 |
  |------|------|------|------|
  | GET | `/profiling/profile/{user_id}` | get_current_user | 返回当前 RiskProfile + ProfileParams |
  | PUT | `/profiling/profile/{user_id}` | get_admin_user | 更新偏好（body: risk_profile + trigger?） |
  | GET | `/profiling/params/{user_id}` | get_current_user | 仅返回 ProfileParams |
  | GET | `/profiling/history/{user_id}` | get_current_user | 返回 UserProfileHistory 列表 |
  | POST | `/profiling/evaluate/{user_id}` | get_admin_user | 评估自动转换（body: TransitionContext） |
- **Body Schema**：
  - `PUT /profile/{user_id}`：`{"risk_profile": "aggressive", "trigger": "manual"}`（trigger 可选，默认 manual）
  - `POST /evaluate/{user_id}`：`{"market_env": "crash", "recent_hit_rate": 0.2}`（TransitionContext 字段）
- **实现要点**：
  - 使用 `from stockquant.ai.profiling import ProfilingManager, RiskProfile, ProfileParams`
  - **注意**：`ProfilingManager` 构造时接受 `user_id` 参数，但所有方法都接受 `user_id: Optional[str]` 覆盖。每次请求应新建一个 `ProfilingManager(user_id=user_id)` 实例，或复用单例并传 `user_id` 参数。
  - 推荐方案：路由模块级单例 `_manager: Optional[ProfilingManager] = None`，通过 `init_manager()` 注入；首请求时惰性初始化（fallback 内存模式）
  - `update_profile` 调用签名：`manager.update_profile(RiskProfile(profile_str), user_id=user_id, trigger=trigger)`
  - 返回 ProfileParams 时用 `dataclasses.asdict()` 转字典
- **验收**：`GET /api/profiling/profile/u1` 返回 200 + `{"user_id": "u1", "risk_profile": "neutral", "params": {...}}`

---

### Batch 4：集成与验证（1 任务）

#### Task 11：main.py 注册 4 个新路由 + 全量回归测试

- **修改文件**：`d:\projects\StockQuant\stockquant\api\main.py`
- **修改内容**：
  1. 在第 30 行附近添加 4 个导入：
     ```python
     from stockquant.api.routers import pipeline_scheduler as pipeline_scheduler_router
     from stockquant.api.routers import pipeline_audit as pipeline_audit_router
     from stockquant.api.routers import hallucination_verify as hallucination_verify_router
     from stockquant.api.routers import profiling as profiling_router
     ```
  2. 在第 136 行 `app.include_router(pipeline_router.router, ...)` 之后添加 4 个 `include_router`：
     ```python
     app.include_router(pipeline_scheduler_router.router, prefix="/api", tags=["管线调度器"])
     app.include_router(pipeline_audit_router.router, prefix="/api", tags=["采集审计日志"])
     app.include_router(hallucination_verify_router.router, prefix="/api", tags=["反幻觉验证"])
     app.include_router(profiling_router.router, prefix="/api", tags=["用户风险偏好"])
     ```
- **验证步骤**：
  1. 启动 FastAPI 服务（`uvicorn stockquant.api.main:app`）
  2. 访问 `/docs` 确认 4 组新端点可见
  3. 调用 4 个代表性端点验证可用：
     - `GET /api/pipeline/scheduler/status` → 200
     - `GET /api/pipeline/audit/stats` → 200
     - `POST /api/hallucination/verify/classify` body=`{"text":"茅台2023年净利润同比增长30%"}` → 200
     - `GET /api/profiling/profile/u1` → 200
- **回归测试命令**：
  ```bash
  python -m pytest tests/ai/ -v --tb=short
  python -m pytest tests/api/ -v --tb=short
  python -m pytest tests/ --tb=short -q
  ```
- **预期**：所有原测试用例通过；无新增 ImportError；无 API 路由冲突。

---

## 四、Execution Order（执行顺序）

```
─── Batch 3（4 个新 API 路由，可并行创建） ───
Task 7 (GAP-M5, pipeline_scheduler)     ┐
Task 8 (GAP-M6, pipeline_audit)         ├─ 并行执行
Task 9 (GAP-M7, hallucination_verify)   │
Task 10 (GAP-L2, profiling)             ┘
   ↓
Task 11 (main.py 注册路由 + 全量回归验证)
```

**4 个路由文件相互独立**，可并行创建。Task 11 必须在 Task 7-10 全部完成后执行（依赖 4 个文件存在）。

---

## 五、Assumptions & Decisions（假设与决策）

1. **决策**：4 个新路由文件相互独立，可并行创建，但 main.py 注册路由放在 Task 11 统一进行（避免部分注册导致启动失败）。
2. **决策**：所有 API 端点使用 FastAPI APIRouter + `Depends(get_current_user/get_admin_user)` 认证，与现有 [api/routers/pipeline.py](file:///d:/projects/StockQuant/stockquant/api/routers/pipeline.py) 一致。
3. **决策**：异步调用（如 `ClaimVerifier.verify_claim()`、`CrossValidator.verify()`、`scheduler.start()`）在 FastAPI 路由中直接使用 `async def`，**不使用 `asyncio.run()` 包装**（FastAPI 原生支持 async，避免事件循环嵌套）。
4. **决策**：`hallucination_verify.py` 与现有 `hallucination.py` 共存，前者专注验证调用，后者管理配置/记录。
5. **决策**：`pipeline_scheduler.py` 与现有 `pipeline.py` 共存，前者管理调度器，后者管理管线运行。
6. **假设**：`ProfilingManager` 在 FastAPI 上下文中可正常工作（其内部 `asyncio.get_event_loop()` 检测 + `concurrent.futures.ThreadPoolExecutor` fallback 已处理运行中的事件循环）。
7. **决策**：Pydantic Schema 使用 `Dict[str, Any]` 接收 body，避免引入额外 Schema 类（与现有 [hallucination.py](file:///d:/projects/StockQuant/stockquant/api/routers/hallucination.py#L38) 一致风格）。
8. **决策**：返回 `dataclass` 实例时统一用 `dataclasses.asdict()` 转字典，确保 JSON 可序列化。
9. **决策**：所有端点用 `try/except Exception` 包裹核心逻辑，失败返回 `raise HTTPException(status_code=500, detail=str(exc))`，避免未捕获异常导致 500 裸堆栈。
10. **假设**：4 个新路由路径不与现有 20 个路由冲突（已通过 Grep 验证 `pipeline/scheduler`、`pipeline/audit`、`hallucination/verify`、`profiling` 均为新增前缀）。

---

## 六、Verification Steps（验证步骤）

### Batch 3 验证

1. **GAP-M5**：`GET /api/pipeline/scheduler/status` → 200 + `{"is_running": true, "task_count": N, "tasks": [...]}`
2. **GAP-M6**：`GET /api/pipeline/audit?limit=10` → 200 + List[Dict]；`GET /api/pipeline/audit/stats` → 200 + `{"total": N, "success": N, ...}`
3. **GAP-M7**：
   - `POST /api/hallucination/verify/classify` body=`{"text":"茅台2023年净利润同比增长30%"}` → 200 + `{"claim_type": "numeric"}`
   - `POST /api/hallucination/verify/cross-validate` body=`{"text":"..."}` → 200 + `{"consensus": ..., "verdict": ..., "confidence": ...}`
4. **GAP-L2**：`GET /api/profiling/profile/u1` → 200 + `{"user_id": "u1", "risk_profile": "neutral", "params": {...}}`

### Batch 4 验证

5. OpenAPI 文档 `/docs` 显示 4 组新端点
6. 全量回归测试：`python -m pytest tests/ --tb=short -q` 全部通过，无新增失败

---

## 七、Risk Assessment（风险评估）

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Task 7-10 路由路径冲突 | Medium | 已通过 Grep 验证现有 20 个路由，确认无 `/pipeline/scheduler`、`/pipeline/audit`、`/hallucination/verify`、`/profiling` 前缀 |
| Task 9 CrossValidator 异步调用失败 | Low | 直接使用 `async def` 路由，FastAPI 原生支持 |
| Task 10 ProfilingManager 事件循环冲突 | Medium | manager.py 已实现 `asyncio.get_event_loop().is_running()` 检测 + ThreadPoolExecutor fallback |
| Task 11 路由注册顺序影响 | Low | 4 个新路由独立，注册顺序无依赖 |
| dataclass 不可 JSON 序列化 | Low | 统一用 `dataclasses.asdict()` 或 `to_dict()` 方法转字典 |
| 现有测试可能依赖路由列表 | Low | 主要影响 `tests/api/test_main.py` 类测试，需检查是否需更新预期路由数 |

---

## 八、File Impact Summary（文件影响汇总）

### 修改文件（1 个）

1. `stockquant/api/main.py` — 注册 4 个新路由（Task 11）

### 新增文件（4 个）

1. `stockquant/api/routers/pipeline_scheduler.py` — PipelineScheduler API（Task 7）
2. `stockquant/api/routers/pipeline_audit.py` — CollectorAuditLog API（Task 8）
3. `stockquant/api/routers/hallucination_verify.py` — ClaimVerifier/CrossValidator API（Task 9）
4. `stockquant/api/routers/profiling.py` — UserProfileHistory API（Task 10）

---

## 九、Success Criteria（成功标准）

修复完成后应满足：

1. ✅ GAP-M5 已修复：`/api/pipeline/scheduler/*` 6 个端点可见且可用
2. ✅ GAP-M6 已修复：`/api/pipeline/audit/*` 5 个端点可见且可用
3. ✅ GAP-M7 已修复：`/api/hallucination/verify/*` 4 个端点可见且可用
4. ✅ GAP-L2 已修复：`/api/profiling/*` 5 个端点可见且可用
5. ✅ main.py 已注册 4 个新路由
6. ✅ 全量回归测试通过，无新增失败
7. ✅ F020 计划完成度从 88% 提升至 100%

---

**计划目标**：补齐 F020 公共 HTTP API → 让 FinMem 三模块架构（Profiling/Memory/Decision-making）的能力对运维、前端、外部系统完全可访问，完成 F020 增强计划的最后一公里。
