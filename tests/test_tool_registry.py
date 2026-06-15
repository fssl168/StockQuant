# -*- coding: utf-8 -*-
"""Tool Registry 单元测试"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from stockquant.agent.tool_registry import ToolDefinition, ToolRegistry, tool


# ---- 测试用工具函数 ----

@tool
async def get_price(symbol: str, period: int = 1) -> dict:
    """获取股票价格数据。"""
    return {"symbol": symbol, "period": period, "price": 100.0}


@tool
async def calculate_indicator(
    indicator: str,
    prices: list,
    params: dict,
) -> dict:
    """计算技术指标。"""
    return {"indicator": indicator, "count": len(prices)}


class TestToolDecorator:
    """@tool 装饰器单元测试。"""

    def test_auto_generates_schema_from_signature(self):
        @tool
        def sample_tool(name: str, count: int = 1) -> dict:
            """A sample tool."""
            return {}

        definition = sample_tool._tool_definition  # type: ignore[attr-defined]

        assert definition.name == "sample_tool"
        assert definition.description == "A sample tool."
        assert "name" in definition.parameters["properties"]
        assert "count" in definition.parameters["properties"]
        assert definition.parameters["properties"]["name"]["type"] == "string"
        assert definition.parameters["properties"]["count"]["type"] == "integer"
        assert "name" in definition.parameters["required"]

    def test_optional_params_not_in_required(self):
        @tool
        def tool_with_optional(value: str, debug: bool = False) -> dict:
            """With optional param."""
            return {}

        definition = tool_with_optional._tool_definition  # type: ignore[attr-defined]
        assert "value" in definition.parameters["required"]
        assert "debug" not in definition.parameters["required"]

    def test_skips_self_parameter(self):
        class MyClass:
            @tool
            async def method(self, x: int) -> str:
                """Instance method tool."""
                return str(x)

        definition = MyClass.method._tool_definition  # type: ignore[attr-defined]
        assert "self" not in definition.parameters["properties"]
        assert "x" in definition.parameters["properties"]

    def test_empty_docstring_provides_empty_description(self):
        @tool
        def no_doc() -> None:
            pass

        definition = no_doc._tool_definition  # type: ignore[attr-defined]
        assert definition.description == ""

    def test_type_mapping(self):
        @tool
        def typed_tool(
            a: str,
            b: int,
            c: float,
            d: bool,
            e: list,
            f: dict,
        ) -> dict:
            """Typed tool."""
            return {}

        definition = typed_tool._tool_definition  # type: ignore[attr-defined]
        props = definition.parameters["properties"]
        assert props["a"]["type"] == "string"
        assert props["b"]["type"] == "integer"
        assert props["c"]["type"] == "number"
        assert props["d"]["type"] == "boolean"
        assert props["e"]["type"] == "array"
        assert props["f"]["type"] == "object"


class TestToolDefinition:
    """ToolDefinition 序列化测试。"""

    def test_to_openai_tool(self):
        definition = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "integer"}},
                "required": ["x"],
            },
        )

        result = definition.to_openai_tool()

        assert result["type"] == "function"
        assert result["function"]["name"] == "test_tool"
        assert result["function"]["description"] == "A test tool"
        assert result["function"]["parameters"] == definition.parameters


class TestToolRegistry:
    """ToolRegistry 功能测试。"""

    def test_register_and_get_all_definitions(self):
        reg = ToolRegistry()

        @tool
        def alpha(x: int) -> int:
            """Alpha tool."""
            return x * 2

        @tool
        def beta(y: str) -> str:
            """Beta tool."""
            return y.upper()

        reg.register(alpha)
        reg.register(beta)

        definitions = reg.get_all_definitions()
        names = [d.name for d in definitions]

        assert "alpha" in names
        assert "beta" in names
        assert len(definitions) == 2

    def test_get_definition_by_name(self):
        reg = ToolRegistry()

        @tool
        def my_tool(val: float) -> float:
            """My tool."""
            return val

        reg.register(my_tool)

        found = reg.get_definition("my_tool")
        assert found is not None
        assert found.name == "my_tool"

        missing = reg.get_definition("nonexistent")
        assert missing is None

    def test_to_openai_tools_format(self):
        reg = ToolRegistry()

        @tool
        def lookup(symbol: str) -> dict:
            """Look up a stock symbol."""
            return {}

        reg.register(lookup)

        tools = reg.to_openai_tools()

        assert len(tools) == 1
        tool_dict = tools[0]
        assert tool_dict["type"] == "function"
        assert "function" in tool_dict
        assert tool_dict["function"]["name"] == "lookup"
        assert "parameters" in tool_dict["function"]

    @pytest.mark.asyncio
    async def test_execute_calls_handler(self):
        reg = ToolRegistry()

        @tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        reg.register(add)

        result = await reg.execute("add", {"a": 3, "b": 5})

        assert "error" not in result
        assert result["content"] == "8"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        reg = ToolRegistry()
        result = await reg.execute("nonexistent", {})

        assert "error" in result
        assert result["error"] is True
        assert "nonexistent" in result["content"]

    @pytest.mark.asyncio
    async def test_execute_handler_error(self):
        reg = ToolRegistry()

        @tool
        def always_fail(x: int) -> int:
            """Always fails."""
            raise ValueError("intentional error")

        reg.register(always_fail)

        result = await reg.execute("always_fail", {"x": 42})

        assert "error" in result
        assert result["error"] is True
        assert "intentional error" in result["content"]

    def test_manual_register_without_decorator(self):
        """注册没有 @tool 装饰器的函数也能工作。"""
        reg = ToolRegistry()

        def manual_tool(value: str) -> str:
            """Manually registered tool."""
            return value[::-1]

        reg.register(manual_tool)

        definition = reg.get_definition("manual_tool")
        assert definition is not None
        assert definition.name == "manual_tool"
