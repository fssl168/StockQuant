# MVP 内存存储转数据库持久化计划

## 1. 问题分析

通过搜索代码库，发现以下内存存储变量需要迁移到数据库持久化：

| 文件 | 变量名 | 类型 | 当前状态 | 用途 |
|------|--------|------|----------|------|
| `backtest.py` | `_tasks` | `dict = {}` | 内存 | 回测任务存储 |
| `data.py` | `_collect_tasks` | `dict = {}` | 内存 | 数据收集任务 |
| `dashboard.py` | `_tasks` | `dict = {}` | 内存 | 仪表盘任务 |
| `comparison.py` | `_backtest_tasks` | `dict = {}` | 已处理 | 回测任务引用 |
| `comparison.py` | `_comparison_history` | `list[dict] = []` | 内存 | 策略对比历史 |
| `optimize.py` | `_optimize_tasks` | `dict = {}` | 内存 | 参数优化任务 |
| `strategy.py` | `_strategies` | `dict = {}` | 已处理 | 策略存储 |
| `trading.py` | `_pending_limit_orders` | `dict = {}` | 内存 | 待处理限价订单 |
| `trading.py` | `_orders_audit` | `dict = {}` | 内存 | 订单审计记录 |
| `trading.py` | `_idempotency_cache` | `dict = {}` | 保留 | 短期幂等缓存 |

**已处理项**: `_backtest_tasks`, `_strategies`（通过 `persistent_store.py`）

**保留内存**: `_idempotency_cache`（短期缓存，10分钟过期）

## 2. 实现计划

### 2.1 新增数据库模型

在 `stockquant/persistence/models.py` 中添加：

| 模型名 | 表名 | 主要字段 |
|--------|------|----------|
| `BacktestTask` | `backtest_tasks` | id, status, result, created_at, updated_at |
| `StrategyModel` | `strategies` | id, name, description, code, parameters, created_at, updated_at |
| `CollectTask` | `collect_tasks` | id, status, progress, created_at, updated_at |
| `OptimizeTask` | `optimize_tasks` | id, status, result, created_at, updated_at |
| `ComparisonHistory` | `comparison_history` | id, strategy_ids, result, created_at |
| `PendingOrder` | `pending_orders` | id, symbol, type, price, quantity, status, created_at |
| `OrderAudit` | `orders_audit` | id, order_id, action, details, created_at |

### 2.2 新增仓库方法

在 `stockquant/persistence/repository.py` 中添加各模型的 CRUD 操作。

### 2.3 扩展持久化存储包装器

在 `stockquant/persistence/persistent_store.py` 中添加：
- `CollectTaskStore`
- `OptimizeTaskStore`  
- `ComparisonHistoryStore`
- `PendingOrderStore`
- `OrderAuditStore`

### 2.4 修改各路由模块

| 文件 | 修改内容 |
|------|----------|
| `backtest.py` | 使用 `BacktestTaskStore` |
| `data.py` | 使用 `CollectTaskStore` |
| `dashboard.py` | 使用 `BacktestTaskStore` |
| `comparison.py` | 使用 `ComparisonHistoryStore` |
| `optimize.py` | 使用 `OptimizeTaskStore` |
| `trading.py` | 使用 `PendingOrderStore`, `OrderAuditStore` |

## 3. 风险评估

| 风险 | 等级 | 说明 | 缓解措施 |
|------|------|------|----------|
| 数据库连接失败 | 中 | 数据库不可用导致服务启动失败 | 添加异常处理，降级为内存存储 |
| 性能影响 | 低 | 每次操作都写数据库 | 使用内存缓存 + 异步写入 |
| 数据一致性 | 低 | 缓存与数据库不同步 | 定期同步机制 |

## 4. 实施步骤

1. **Step 1**: 新增数据库模型（models.py）
2. **Step 2**: 新增仓库方法（repository.py）
3. **Step 3**: 扩展持久化存储包装器（persistent_store.py）
4. **Step 4**: 创建数据库表
5. **Step 5**: 修改 backtest.py
6. **Step 6**: 修改 data.py
7. **Step 7**: 修改 dashboard.py
8. **Step 8**: 修改 comparison.py
9. **Step 9**: 修改 optimize.py
10. **Step 10**: 修改 trading.py
11. **Step 11**: 测试验证

## 5. 依赖关系

- `sqlalchemy` - ORM 框架
- `postgresql` - 数据库（或 SQLite）
- 现有 `persistent_store.py` - 存储包装器基础

## 6. 测试计划

1. 单元测试：验证各存储类的 CRUD 操作
2. 集成测试：验证路由模块与数据库的交互
3. 持久化测试：重启服务后验证数据恢复