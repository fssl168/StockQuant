# 修复后端 UserToken 类型误用问题

## Summary
回测提交 500 错误的根因是 `UserToken`（Pydantic 模型）被当作 dict 使用 `.get()` 方法。已修复 backtest.py，现需检查并修复其余路由中的同类问题。

## Current State Analysis

### 已修复
- [backtest.py:167](stockquant/api/routers/backtest.py#L167): `_user.get("sub", "")` → `_user.sub` ✅

### 待修复（确认的 Bug）

| 文件 | 行号 | 错误代码 | 正确代码 |
|------|------|---------|---------|
| [audit.py:28](stockquant/api/routers/audit.py#L28) | 28 | `_user.get("sub", "anonymous")` | `_user.sub or "anonymous"` |
| [audit.py:44](stockquant/api/routers/audit.py#L44) | 44 | `_user.get("role") != "ADMIN"` | `_user.role != "ADMIN"` |

### 非Bug（无需修改）

| 文件 | 行号 | 原因 |
|------|------|------|
| auth.py:87-103 | 87-103 | `user` 来自 `_init_users_db()` 返回的 dict，`.get()` 正确 |
| auth.py:139-140 | 139-140 | 死代码（135行 hasattr 检查始终为 True），不影响功能 |

### 全局搜索结论
在所有 router 文件中搜索 `_user.get(` / `_user[` / `current_user.get(` / `current_user[` 模式，仅发现上述 2 处真正的 Bug。

## Proposed Changes

### 修改 1：audit.py 第 28 行
```python
# Before
user_id = _user.get("sub", "anonymous")
# After
user_id = _user.sub or "anonymous"
```

### 修改 2：audit.py 第 44 行
```python
# Before
if _user.get("role") != "ADMIN":
# After
if _user.role != "ADMIN":
```

## Verification Steps
1. 后端自动热重载后，调用 `POST /api/backtest` 确认仍返回 200
2. 调用 `GET /api/audit/logs` 和 `GET /api/audit/logs/all` 确认审计接口正常
3. 无新的 AttributeError 或 500 错误
