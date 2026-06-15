# -*- coding: utf-8 -*-
"""Tool Registry — 为 LLM 提供可调用工具的描述与执行引擎"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ToolDefinition:
    """单个工具的描述元数据，遵循 OpenAI function-calling schema。"""

    name: str
    description: str
    parameters: dict  # JSON Schema object

    def to_openai_tool(self) -> dict:
        """将定义序列化为 OpenAI tool 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _type_to_json_schema(annotation: type) -> dict:
    """将 Python 类型注解映射为 JSON Schema 类型。

    注意：在 ``from __future__ import annotations`` 下，
    ``int`` 等注解在运行时可能是字符串（如 ``"int"``），需要兼容。
    """
    # 兼容字符串形式的类型名（PEP 563 postponed evaluation）
    if isinstance(annotation, str):
        annotation = {"int": int, "float": float, "str": str, "bool": bool, "list": list, "dict": dict}.get(annotation, annotation)

    mapping = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array", "items": {"type": "string"}},
        dict: {"type": "object"},
    }
    return mapping.get(annotation, {"type": "string"})


def tool(func: Callable) -> Callable:
    """装饰器：从函数签名自动生成 ToolDefinition。

    在 func 上设置 ``_tool_definition`` 属性，供 ToolRegistry 使用。
    """
    sig = inspect.signature(func)
    properties: dict[str, dict] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        # 推导参数类型
        param_type: type = str  # 默认 string
        if param.annotation != inspect.Parameter.empty:
            param_type = param.annotation
        properties[param_name] = {
            "type": _type_to_json_schema(param_type).get("type", "string"),
        }
        if param.default == inspect.Parameter.empty:
            required.append(param_name)

    schema: dict = {
        "type": "object",
        "properties": properties,
        "required": required,
    }

    func._tool_definition = ToolDefinition(  # type: ignore[attr-defined]
        name=func.__name__,
        description=func.__doc__ or "",
        parameters=schema,
    )
    return func


class ToolRegistry:
    """工具注册表 — 管理 LLM 可调用的工具集合。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable] = {}

    def register(self, func: Callable) -> None:
        """注册一个工具函数。

        如果 ``func`` 有 ``_tool_definition`` 属性（由 ``@tool`` 装饰），
        则自动使用之；否则尝试手动构造一个简化定义。
        """
        if hasattr(func, "_tool_definition"):
            definition = func._tool_definition  # type: ignore[attr-defined]
        else:
            sig = inspect.signature(func)
            properties: dict[str, dict] = {}
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                param_type: type = str
                if param.annotation != inspect.Parameter.empty:
                    param_type = param.annotation
                properties[param_name] = _type_to_json_schema(param_type)
            definition = ToolDefinition(
                name=func.__name__,
                description=func.__doc__ or "",
                parameters={"type": "object", "properties": properties},
            )

        self._tools[definition.name] = definition
        self._handlers[definition.name] = func

    def get_definition(self, name: str) -> Optional[ToolDefinition]:
        """按名称获取工具定义，未找到返回 None。"""
        return self._tools.get(name)

    def get_all_definitions(self) -> list[ToolDefinition]:
        """返回所有已注册的工具定义。"""
        return list(self._tools.values())

    def to_openai_tools(self) -> list[dict]:
        """将所有工具转换为 OpenAI tool 列表。"""
        return [t.to_openai_tool() for t in self._tools.values()]

    async def execute(self, tool_name: str, arguments: dict) -> dict:
        """异步执行工具调用。

        Parameters
        ----------
        tool_name : str
            工具名称
        arguments : dict
            参数字典，将映射到 handler 的命名参数

        Returns
        -------
        dict — ``{"content": str(result)}`` 或 ``{"content": str(e), "error": True}``
        """
        handler = self._handlers.get(tool_name)
        if handler is None:
            return {
                "content": f"Unknown tool: {tool_name}",
                "error": True,
            }

        try:
            sig = inspect.signature(handler)
            # 过滤出 handler 接受的参数
            bound_args = {}
            for param_name in sig.parameters:
                if param_name == "self":
                    continue
                if param_name in arguments:
                    bound_args[param_name] = arguments[param_name]
            result = handler(**bound_args)
            return {"content": str(result)}
        except Exception as exc:
            return {"content": str(exc), "error": True}
