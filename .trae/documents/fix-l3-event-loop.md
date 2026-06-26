# 修复 L3 PostgreSQL "event loop already running" 降级问题

## Summary
L3 长期记忆存储在初始化时因 `asyncio.get_event_loop().run_until_complete()` 在已有运行中的 event loop 环境下调用而失败，导致 PostgreSQL 后端无法启用，降级为内存存储。同一文件中其他方法（`write`、`search` 等）已正确处理此场景，唯独 `_check_pgvector()` 缺少该保护逻辑。

## Current State Analysis

### 根因
[l3_store.py:84-85](stockquant/ai/memory/l3_store.py#L84-L85) 的 `_check_pgvector()` 方法：
```python
def _check_pgvector(self) -> None:
    try:
        import asyncio
        asyncio.get_event_loop().run_until_complete(self._ensure_pgvector())  # ← 崩溃点
```

Uvicorn 启动时已有 async event loop 运行，此时调用 `run_until_complete()` 会抛出 `RuntimeError: This event loop is already running`。

### 已有正确实现参考
同文件 [l3_store.py:140-149](stockquant/ai/memory/l3_store.py#L140-L149) 的 `write()` 方法已正确处理：
```python
loop = __import__("asyncio").get_event_loop()
if loop.is_running():
    # 已在异步上下文中，用线程池 + 新 loop
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return pool.submit(self._write_sync, item).result()
return loop.run_until_complete(self._write_async(item))
```

### 调用链
`main.py:326` → `MemorySystem()` → `L3Store.__init__()` → `_init_backend()` → `_check_pgvector()` → **崩溃**

## Proposed Changes

### 修改文件：[l3_store.py](stockquant/ai/memory/l3_store.py)

**修改 `_check_pgvector()` 方法**（第 81-88 行），采用与 `write()/search()` 相同的 event loop 安全模式：

```python
def _check_pgvector(self) -> None:
    """检测 pgvector 扩展是否可用"""
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 已有 event loop 运行时（如 Uvicorn 环境），在线程池中执行
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(self._check_pgvector_sync).result()
        else:
            loop.run_until_complete(self._ensure_pgvector())
    except Exception as exc:
        logger.warning("PostgreSQL 表创建失败: %s，L3 降级为内存存储", exc)
        raise
```

**新增同步包装方法 `_check_pgvector_sync()`**：

```python
def _check_pgvector_sync(self) -> None:
    """同步包装：在新 event loop 中执行 _ensure_pgvector"""
    loop = __import__("asyncio").new_event_loop()
    try:
        loop.run_until_complete(self._ensure_pgvector())
    finally:
        loop.close()
```

## Assumptions & Decisions
- 不重构架构，仅修复 `_check_pgvector()` 一个方法
- 复用同文件已有的线程池+新 loop 模式
- PostgreSQL 服务本身可用（用户已创建 stockquant 数据库）

## Verification
1. 重启后端，日志应显示 `L3 使用 PostgreSQL 后端` 而非 `L3 降级为内存存储`
2. 日志不应出现 `This event loop is already running` 错误
3. `/api/health` 正常返回
