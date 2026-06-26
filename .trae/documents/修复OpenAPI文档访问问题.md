# 计划：修复 8000/#docs 无法访问问题

## 问题分析

访问 `http://localhost:8000/openapi.json` 或 `/docs` 时返回 500 错误：

```
PydanticUserError: `TypeAdapter[typing.Annotated[ForwardRef('Dict[str, Any]'), FieldInfo(annotation=NoneType, required=True)]]` is not fully defined
```

**根本原因**：Pydantic 2.x 在处理 `from __future__ import annotations` 与某些复杂类型声明（如返回类型 `Dict[str, Any]`）时存在兼容性问题，导致 OpenAPI 模式生成失败。

## 探索结果

已确认以下情况：
1. `main.py` 使用了 `from __future__ import annotations`（第4行）
2. 多个路由文件使用了 `response_model=dict` 或返回类型注解包含 `Dict[str, Any]`
3. 移除部分 `response_model=dict` 后问题仍然存在
4. 禁用 OpenAPI 端点（设置 `docs_url=None`）可以绕过问题，但用户希望保留文档访问

## 解决方案

有三种可选方案：

### 方案 A：禁用 OpenAPI 文档端点（推荐，最简单）
- 在 `main.py` 中设置 `docs_url=None` 和 `redoc_url=None`
- 优点：快速解决，不影响功能
- 缺点：无法使用 Swagger UI 文档

### 方案 B：移除 `from __future__ import annotations`（推荐）
- 从 `main.py` 移除 `from __future__ import annotations`
- 优点：保留完整的 OpenAPI 文档
- 缺点：可能影响代码的向后兼容性

### 方案 C：升级 Pydantic 并修复所有类型注解
- 升级 Pydantic 到最新版本
- 将所有 `response_model=dict` 改为 `response_model=Dict[str, Any]`
- 修复所有使用延迟注解的地方
- 优点：完整解决方案
- 缺点：工作量大，可能引入其他问题

## 实施步骤（方案 B）

1. **修改 `stockquant/api/main.py`**
   - 移除第4行的 `from __future__ import annotations`

2. **重启后端服务验证**
   - 访问 `http://localhost:8000/openapi.json` 确认返回 200
   - 访问 `http://localhost:8000/docs` 确认 Swagger UI 正常显示

## 验证步骤

1. 重启后端服务
2. 访问 `http://localhost:8000/openapi.json`，确认返回有效的 JSON
3. 访问 `http://localhost:8000/docs`，确认显示 Swagger 文档页面