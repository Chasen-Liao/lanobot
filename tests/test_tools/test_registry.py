"""Tests for ToolRegistry."""

import pytest
from lanobot.tools.base import Tool
from lanobot.tools.registry import ToolRegistry


class EchoTool(Tool):
    """A simple echo tool for testing."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echoes back the input."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message to echo"}
            },
            "required": ["message"],
        }

    async def execute(self, message: str, **kwargs) -> str:
        return f"Echo: {message}"


class AddTool(Tool):
    """A simple add tool for testing."""

    @property
    def name(self) -> str:
        return "add"

    @property
    def description(self) -> str:
        return "Adds two numbers."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "a": {"type": "integer", "description": "First number"},
                "b": {"type": "integer", "description": "Second number"}
            },
            "required": ["a", "b"],
        }

    async def execute(self, a: int, b: int, **kwargs) -> str:
        return str(a + b)


class TestToolRegistry:
    """Test cases for ToolRegistry."""

    def test_register_tool(self):
        """Test registering a tool."""
        registry = ToolRegistry()
        tool = EchoTool()

        registry.register(tool)

        assert "echo" in registry
        assert registry.get("echo") is tool

    def test_unregister_tool(self):
        """Test unregistering a tool."""
        registry = ToolRegistry()
        tool = EchoTool()
        registry.register(tool)

        registry.unregister("echo")

        assert "echo" not in registry
        assert registry.get("echo") is None

    def test_get_definitions(self):
        """Test getting tool definitions."""
        registry = ToolRegistry()
        registry.register(EchoTool())
        registry.register(AddTool())

        definitions = registry.get_definitions()

        assert len(definitions) == 2
        names = [d["function"]["name"] for d in definitions]
        assert "echo" in names
        assert "add" in names

    @pytest.mark.asyncio
    async def test_execute_tool(self):
        """Test executing a tool."""
        registry = ToolRegistry()
        registry.register(EchoTool())

        result = await registry.execute("echo", {"message": "hello"})

        assert result == "Echo: hello"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self):
        """Test executing a non-existent tool."""
        registry = ToolRegistry()

        result = await registry.execute("nonexistent", {})

        assert "Error" in result
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_execute_with_invalid_params(self):
        """Test executing a tool with invalid parameters."""
        registry = ToolRegistry()
        registry.register(AddTool())

        result = await registry.execute("add", {"a": "not_an_int", "b": 2})

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_execute_with_param_casting(self):
        """Test parameter casting during execution."""
        registry = ToolRegistry()
        registry.register(AddTool())

        # String to int casting
        result = await registry.execute("add", {"a": "5", "b": "10"})

        assert result == "15"

    def test_len(self):
        """Test __len__ method."""
        registry = ToolRegistry()
        assert len(registry) == 0

        registry.register(EchoTool())
        assert len(registry) == 1

        registry.register(AddTool())
        assert len(registry) == 2

    def test_iter(self):
        """Test __iter__ method."""
        registry = ToolRegistry()
        tool1 = EchoTool()
        tool2 = AddTool()
        registry.register(tool1)
        registry.register(tool2)

        tools = list(registry)

        assert tool1 in tools
        assert tool2 in tools

    def test_get_langchain_tools(self):
        """Test getting LangChain tools."""
        registry = ToolRegistry()
        registry.register(EchoTool())

        lc_tools = registry.get_langchain_tools()

        assert len(lc_tools) == 1
        assert lc_tools[0].name == "echo"