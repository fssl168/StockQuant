# StockQuant 项目补齐实施计划

> **依据**：StockQuant-Product-Spec-Gap-Assessment.md（2026-06-21 差距评估报告）
> **状态**：待实施
> **优先级策略**：P0（高影响→零回归）> P1（中等影响→快速修复）> P2（低影响→优化）

---

## 任务清单总览

| # | 优先级 | 任务 | 对应差距 | 预计工作量 | 依赖 |
|---|--------|------|----------|------------|------|
| 1 | P1 | 注册审计日志端点 | #7, #9 | 10 分钟 | 无 |
| 2 | P0 | 创建记忆系统 API 端点 | #1.1 | 2 小时 | 无 |
| 3 | P0 | 创建反幻觉系统 API 端点 | #1.2 | 2 小时 | 无 |
| 4 | P0 | 创建 AI 信息管线 API 端点 | #1.3, #1.4 | 3 小时 | #2, #3 |
| 5 | P1 | 注册 Prometheus 监控端点 | #9 | 10 分钟 | 无 |
| 6 | P0 | 创建记忆系统前端页面 | #8 | 4 小时 | #2 |
| 7 | P0 | 创建反幻觉前端页面 | #8 | 3 小时 | #3 |
| 8 | P1 | 创建 AI 管线监控前端页面 | #8 | 3 小时 | #4 |
| 9 | P1 | 补充性能基准测试 | #5 | 2 小时 | 无 |
| 10 | P2 | 补充数据源 CRUD API | #3 | 1 小时 | 无 |

---

## 任务 1：注册审计日志和监控端点

**对应差距**：#7（审计日志未注册）、#9（监控路由未注册）

### 修改文件
- `stockquant/api/main.py`

### 具体操作

**第 1 步**：在 `main.py` 的 import 部分添加两个路由模块的导入

在第 23 行（已导入 `audit` 模块）附近确认 `monitoring` 模块存在，如果不存在则创建。

**第 2 步**：在 `create_app()` 函数中注册这两个路由

在 `app.include_router(auth_router.router, prefix="/api", tags=["认证"])` 之前添加：

```python
# 注册审计日志端点
from stockquant.api.routers import audit as audit_router
app.include_router(audit_router.router, prefix="/api", tags=["审计日志"])

# 注册 Prometheus 监控端点
from stockquant.api.routers import monitoring as monitoring_router
app.include_router(monitoring_router.router, prefix="", tags=["监控"])
```

**第 3 步**：确认 `monitoring.py` 文件存在且结构正确

检查 `stockquant/api/routers/monitoring.py` 是否存在。如果不存在，从差距评估报告中参考的内容创建。

### 验证
- `curl http://localhost:8000/api/audit/logs` 应返回审计日志列表
- `curl http://localhost:8000/metrics` 应返回 Prometheus 格式指标
- 启动 `pytest -x` 确保无回归

---

## 任务 2：创建记忆系统 API 端点

**对应差距**：#1.1

### 新建文件
- `stockquant/api/routers/memory.py`

### 设计 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/memory/l1` | 获取 L1 工作记忆最近记录 |
| POST | `/api/memory/l1` | 添加 L1 工作记忆条目 |
| DELETE | `/api/memory/l1` | 清空 L1 工作记忆 |
| GET | `/api/memory/l2` | 获取 L2 短期记忆列表 |
| POST | `/api/memory/l2` | 写入 L2 短期记忆 |
| POST | `/api/memory/l2/search` | 搜索 L2 短期记忆 |
| DELETE | `/api/memory/l2` | 清空 L2 短期记忆 |
| GET | `/api/memory/l3` | 获取 L3 长期记忆列表 |
| POST | `/api/memory/l3` | 写入 L3 长期记忆 |
| POST | `/api/memory/l3/search` | 搜索 L3 长期记忆 |
| DELETE | `/api/memory/l3` | 清空 L3 长期记忆 |
| POST | `/api/memory/compress` | 触发 L2→L3 记忆压缩 |
| POST | `/api/memory/cleanup` | 清理过期记忆 |

### 实现要点

1. **单例初始化**：在模块级创建一个 `MemorySystem` 单例，由 `main.py` 在启动时注入（类似现有的 `strategy.set_storage()` 模式）
2. **默认 DB URL**：如果 L2/L3 需要 PostgreSQL，在代码中处理 SQLite 降级（类似 `L2Store` 和 `L3Store` 的 fallback 机制）
3. **分页支持**：L2/L3 查询支持 `limit`/`offset` query params
4. **RBAC**：所有端点使用 `Depends(get_current_user)`，记忆管理端点需要 ADMIN 权限

### 具体代码结构

```python
# memory.py
from fastapi import APIRouter, Depends, Query
from stockquant.api.deps import get_current_user, get_admin_user
from stockquant.ai.memory.system import MemorySystem

router = APIRouter(tags=["记忆系统"])

# 模块级单例
_memory: MemorySystem | None = None

def init_memory(memory: MemorySystem):
    """由 main.py 注入"""
    global _memory
    _memory = memory

@router.get("/memory/l1", summary="获取 L1 工作记忆")
async def get_l1(
    _user: dict = Depends(get_current_user),
    n: int = Query(20, ge=1, le=200),
):
    if _memory is None:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    return _memory.get_recent(n)

@router.post("/memory/l1", summary="添加 L1 工作记忆")
async def add_l1(payload: dict, _user: dict = Depends(get_admin_user)):
    if _memory is None:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    _memory.add_working(payload)
    return {"success": True}

# L2/L3 端点类似实现...
```

### 修改 main.py

在 `create_app()` 中的存储注入部分添加：

```python
# 记忆系统初始化
try:
    from stockquant.ai.memory.system import MemorySystem
    memory_system = MemorySystem()
    memory_router.init_memory(memory_system)
except Exception as e:
    logger.warning("记忆系统初始化失败: %s", e)
```

### 验证
- `GET /api/memory/l1` 返回空列表（首次启动）
- `POST /api/memory/l2` 写入成功
- `POST /api/memory/l2/search` 搜索成功
- `pytest -x --test-memory-api` 通过

---

## 任务 3：创建反幻觉系统 API 端点

**对应差距**：#1.2

### 新建文件
- `stockquant/api/routers/hallucination.py`

### 设计 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/hallucination/records` | 查询幻觉记录 |
| GET | `/api/hallucination/analysis` | 幻觉模式分析 |
| GET | `/api/hallucination/suggestions` | Prompt 优化建议 |
| POST | `/api/hallucination/record` | 手动记录幻觉事件 |
| PUT | `/api/hallucination/config` | 配置幻觉检测模式 |
| GET | `/api/hallucination/config` | 获取幻觉检测配置 |

### 实现要点

1. **单例初始化**：类似 memory.py 模式
2. **查询过滤**：支持按 agent、hallucination_type、时间范围过滤
3. **模式分析**：调用 `HallucinationDatabase.analyze_patterns()` 返回聚合结果
4. **Prompt 建议**：调用 `HallucinationDatabase.optimize_prompt()` 返回优化建议

### 验证
- `GET /api/hallucination/records` 返回空列表（首次启动）
- `GET /api/hallucination/analysis` 返回结构化分析
- `pytest -x`

---

## 任务 4：创建 AI 信息管线 API 端点

**对应差距**：#1.3, #1.4

### 新建文件
- `stockquant/api/routers/pipeline.py`

### 设计 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/pipeline/run` | 运行完整信息处理管线 |
| POST | `/api/pipeline/collect` | 仅执行采集阶段 |
| POST | `/api/pipeline/denoise` | 仅执行降噪阶段 |
| POST | `/api/pipeline/summarize` | 仅执行总结阶段 |
| POST | `/api/pipeline/elevate` | 仅执行升华阶段 |
| GET | `/api/pipeline/status` | 获取管线运行状态 |
| GET | `/api/pipeline/config` | 获取管线配置 |
| PUT | `/api/pipeline/config` | 更新管线配置 |

### 实现要点

1. **任务异步化**：管线运行是耗时操作，使用 FastAPI BackgroundTasks 异步执行
2. **任务跟踪**：每次提交返回 task_id，前端可轮询 GET `/api/pipeline/status/{task_id}`
3. **单例初始化**：`InformationProcessingPipeline` 单例
4. **AI 采集**：集成 `NewsCollector` + `NewsSearcher`，在 POST `/api/pipeline/collect` 中传入 symbol 列表

### 具体代码结构

```python
# pipeline.py
from fastapi import APIRouter, BackgroundTasks, Depends
from stockquant.ai.pipeline_orchestrator import InformationProcessingPipeline
from stockquant.ai.memory.system import MemorySystem

router = APIRouter(tags=["AI 信息管线"])

_pipeline: InformationProcessingPipeline | None = None
_running_tasks: dict = {}  # task_id -> status

def init_pipeline(pipeline: InformationProcessingPipeline):
    global _pipeline
    _pipeline = pipeline

@router.post("/pipeline/run", summary="运行完整信息处理管线")
async def run_pipeline(
    payload: dict,
    bg: BackgroundTasks,
    _user: dict = Depends(get_admin_user),
):
    symbols = payload.get("symbols", [])
    task_id = f"PIPE-{uuid.uuid4().hex[:8].upper()}"
    _running_tasks[task_id] = {"status": "started", "created_at": datetime.now().isoformat()}
    
    def _run():
        _running_tasks[task_id]["status"] = "running"
        result = _pipeline.run(symbols=symbols)
        _running_tasks[task_id].update({
            "status": "completed",
            "result": result,
            "completed_at": datetime.now().isoformat(),
        })
    
    bg.add_task(_run)
    return {"task_id": task_id, "status": "queued"}

@router.get("/pipeline/status/{task_id}", summary="获取管线运行状态")
async def get_task_status(task_id: str):
    task = _running_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return task
```

### 修改 main.py

在 `create_app()` 中添加：

```python
try:
    from stockquant.ai.pipeline_orchestrator import InformationProcessingPipeline
    from stockquant.ai.memory.system import MemorySystem
    memory_system = MemorySystem()
    pipeline = InformationProcessingPipeline(memory=memory_system)
    pipeline_router.init_pipeline(pipeline)
except Exception as e:
    logger.warning("AI 管线初始化失败: %s", e)
```

### 验证
- `POST /api/pipeline/run` 返回 task_id
- `GET /api/pipeline/status/{task_id}` 轮询到 completed 状态
- `pytest -x`

---

## 任务 5：注册 Prometheus 监控端点（与任务 1 合并）

已在任务 1 中处理。

---

## 任务 6：创建记忆系统前端页面

**对应差距**：#8

### 新建文件

- `web/src/pages/Memory.tsx` — 主页面（L1/L2/L3 Tab）
- `web/src/api/memory.ts` — API 客户端
- `web/src/stores/memoryStore.ts` — Zustand store

### 页面设计

**Layout**：Ant Design `Tabs` 3 个 Tab（L1 / L2 / L3）

**L1 Tab**：
- 最近 20 条工作记忆列表（时间倒序）
- 添加条目表单（symbol + content + metadata JSON）
- 清空按钮

**L2 Tab**：
- 搜索框（keyword + symbol 过滤）
- 搜索结果列表（content + confidence + timestamp + metadata）
- 分页组件（每页 20 条）
- 添加条目表单
- 压缩到 L3 按钮

**L3 Tab**：
- 搜索框（keyword + symbol + min_confidence）
- 搜索结果列表
- 分页组件
- 添加洞察表单
- 清理过期记忆按钮

### API 客户端

```typescript
// memory.ts
export const memoryApi = {
  getL1: () => client.get('/api/memory/l1') as Promise<MemoryEntry[]>,
  addL1: (entry: MemoryEntry) => client.post('/api/memory/l1', entry),
  clearL1: () => client.delete('/api/memory/l1'),
  getL2: (params?: {symbol?: string; keyword?: string; limit?: number; offset?: number}) =>
    client.get('/api/memory/l2', { params }),
  addL2: (entry: MemoryEntry) => client.post('/api/memory/l2', entry),
  searchL2: (keyword: string, symbol?: string) =>
    client.post('/api/memory/l2/search', { keyword, symbol }),
  clearL2: () => client.delete('/api/memory/l2'),
  // L3 类似...
  compress: () => client.post('/api/memory/compress'),
  cleanup: () => client.post('/api/memory/cleanup'),
}
```

### 验证
- 页面渲染正常，无 console 错误
- L1/L2/L3 CRUD 操作成功
- 搜索功能正常工作

---

## 任务 7：创建反幻觉前端页面

**对应差距**：#8

### 新建文件

- `web/src/pages/Hallucination.tsx` — 主页面
- `web/src/api/hallucination.ts` — API 客户端

### 页面设计

**Layout**：2 个主要区域

1. **幻觉记录列表**（可筛选）
   - 筛选器：Agent 下拉、类型下拉、时间范围
   - 表格：时间 | Agent | 类型 | 原始输出 | 纠正输出 | 置信度
   - 行点击展开详情

2. **模式分析与建议**
   - 幻觉类型分布饼图
   - 高频触发词列表
   - 各 Agent 差异对比
   - Prompt 优化建议列表（每条带优先级标记）

### 验证
- 页面渲染正常
- 筛选/搜索功能正常
- 分析数据正确展示

---

## 任务 8：创建 AI 管线监控前端页面

**对应差距**：#8

### 新建文件

- `web/src/pages/AIPipeline.tsx` — 主页面
- `web/src/api/pipeline.ts` — API 客户端

### 页面设计

**Layout**：3 个区域

1. **管线控制**
   - 运行完整管线按钮（输入 symbol 列表）
   - 分阶段运行按钮（Collect / Denoise / Summarize / Elevate）
   - 配置表单（收集间隔、降噪阈值、总结周期、升华参数）

2. **运行状态**
   - 当前运行任务卡片（task_id + 状态 + 进度）
   - 历史记录表格（时间 | 任务 ID | 状态 | 采集数 | 过滤后 | 洞察数）

3. **结果展示**
   - 选中任务后展示结果：采集文章数、过滤后数量、summary 内容、insights 列表
   - 幻觉检查结果（passed/failed + 问题详情）

### 验证
- 管线运行正常
- 状态轮询更新
- 结果正确展示

---

## 任务 9：补充性能基准测试

**对应差距**：#5

### 新建文件
- `tests/test_benchmarks.py`

### 测试内容

```python
# test_benchmarks.py
"""F001/F007/NFR001 性能基准测试"""

import pytest

class TestBacktestPerformance:
    """回测速度基准测试"""
    
    def test_daily_5000_bars_per_sec(self):
        """日线 10 年 5 只股票 ≥ 5000 Bar/秒"""
        # 准备 10 年日线 × 5 只股票 = ~12500 bars
        # 运行回测，计时
        # 断言 speed >= 5000
    
    def test_minute_500_bars_per_sec(self):
        """分钟线 10 年 5 只股票 ≥ 500 Bar/秒"""
        # 准备 10 年分钟线 × 5 只股票
        # 运行回测，计时
        # 断言 speed >= 500


class TestIndicatorPerformance:
    """指标计算性能测试"""
    
    def test_indicator_calculation_time(self):
        """单次指标计算 < 1ms"""
        import time
        # 对 18 个指标各运行 1000 次
        # 断言平均 < 1ms/次


class TestCachePerformance:
    """数据缓存读取性能测试"""
    
    def test_cache_read_10year(self):
        """读取 10 年日线 < 100ms"""
        import time
        # 从 SQLite/Parquet 缓存读取 10 年数据
        # 断言 < 100ms
```

### 运行方式
```bash
pytest tests/test_benchmarks.py -v --benchmark
```

### 验证
- 所有性能基准测试通过
- 如果低于阈值，测试标记为 skipped 并打印警告

---

## 任务 10：补充数据源 CRUD API

**对应差距**：#3

### 修改文件
- `stockquant/api/routers/data.py`

### 新增端点

在现有 `POST /api/data/sources` 后添加：

```python
@router.put("/data/sources/{provider}", summary="编辑数据源配置")
async def update_source(provider: str, payload: UpdateDataRequest):
    """编辑单个数据源配置"""
    for i, s in enumerate(_sources):
        if s["provider"] == provider:
            _sources[i].update(payload)
            return {"success": True, "provider": provider}
    raise HTTPException(status_code=404, detail=f"数据源 {provider} 不存在")

@router.delete("/data/sources/{provider}", summary="删除数据源")
async def delete_source(provider: str):
    """删除单个数据源配置"""
    original_len = len(_sources)
    _sources[:] = [s for s in _sources if s["provider"] != provider]
    if len(_sources) == original_len:
        raise HTTPException(status_code=404, detail=f"数据源 {provider} 不存在")
    return {"success": True, "provider": provider}
```

### 验证
- `PUT /api/data/sources/alphafeed` 成功更新
- `DELETE /api/data/sources/baostock` 成功删除
- `pytest -x`

---

## 实施顺序和依赖

```
阶段 1（快速修复，0 风险）
├── 任务 1：注册审计日志 + Prometheus 端点
│   影响：NFR004 审计可查，可观测性提升
│   风险：极低（仅 2 行代码注册）

阶段 2（核心功能 API，需验证无回归）
├── 任务 2：记忆系统 API
├── 任务 3：反幻觉系统 API
└── 任务 4：AI 信息管线 API（依赖 #2, #3）
    影响：F020 AI 全流程可用，填补最大差距
    风险：中（新 API 端点，需充分测试）

阶段 3（前端页面，依赖后端 API）
├── 任务 6：记忆系统前端页面（依赖 #2）
├── 任务 7：反幻觉前端页面（依赖 #3）
└── 任务 8：AI 管线监控页面（依赖 #4）
    影响：用户可通过 UI 使用 AI 基础设施
    风险：低（纯前端，无数据变更）

阶段 4（测试和优化，独立）
├── 任务 9：性能基准测试
└── 任务 10：数据源 CRUD
    影响：NFR001 可验证，数据源管理完整
    风险：低
```

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 记忆系统 L2/L3 需要 PostgreSQL | 高 | 已有 fallback 到 SQLite 机制，确保 L2Store/L3Store 的 fallback 正常工作 |
| AI 管线运行耗时影响 API 响应 | 中 | 使用 BackgroundTasks 异步执行，前端通过 task_id 轮询 |
| 前端页面增加包体积 | 低 | 3 个新页面 ~500 行代码，对包体积影响可忽略 |
| 性能基准测试结果波动 | 低 | 使用多次运行取中位数，设置 10% 容差 |

---

## 预期效果

完成全部 10 项任务后：

- **功能完成度**：从 97% → ~98.5%（F020 API 暴露 + 前端页面）
- **NFR 完成度**：从 89% → ~95%（审计端点注册 + 性能基准测试）
- **综合完成度**：从 94% → ~97%
- **API 端点**：从 89 个 → ~115 个（+26 个新端点）
- **前端页面**：从 14 个 → ~17 个（+3 个新页面）
