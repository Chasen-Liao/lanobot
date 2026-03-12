"""Tests for Tool base class."""

import pytest
from lanobot.tools.base import Tool


class DummyTool(Tool):
    """A dummy tool for testing."""

    @property
    def name(self) -> str:
        return "dummy_tool"

    @property
    def description(self) -> str:
        return "A dummy tool for testing."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input text"},
                "count": {"type": "integer", "description": "Count", "minimum": 1, "maximum": 10},
            },
            "required": ["text"],
        }

    async def execute(self, text: str, count: int = 1, **kwargs) -> str:
        return f"{text}x{count}"


class TestTool:
    """Test cases for Tool base class."""

    def test_tool_schema(self):
        """Test tool schema generation."""
        tool = DummyTool()
        schema = tool.to_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "dummy_tool"
        assert schema["function"]["description"] == "A dummy tool for testing."
        assert schema["function"]["parameters"]["type"] == "object"

    def test_validate_params_valid(self):
        """Test parameter validation with valid params."""
        tool = DummyTool()
        errors = tool.validate_params({"text": "hello", "count": 5})
        assert errors == []

    def test_validate_params_missing_required(self):
        """Test parameter validation with missing required param."""
        tool = DummyTool()
        errors = tool.validate_params({"count": 5})
        assert len(errors) > 0
        assert "text" in errors[0]

    def test_validate_params_invalid_type(self):
        """Test parameter validation with invalid type."""
        tool = DummyTool()
        errors = tool.validate_params({"text": "hello", "count": "invalid"})
        assert len(errors) > 0

    def test_validate_params_out_of_range(self):
        """Test parameter validation with out of range value."""
        tool = DummyTool()
        errors = tool.validate_params({"text": "hello", "count": 100})
        assert len(errors) > 0

    def test_cast_params_string_to_int(self):
        """Test casting string to int."""
        tool = DummyTool()
        params = tool.cast_params({"text": "hello", "count": "5"})
        assert params["count"] == 5
        assert isinstance(params["count"], int)

    def test_cast_params_string_to_bool(self):
        """Test casting string to boolean."""

        class BoolTool(Tool):
            @property
            def name(self) -> str:
                return "bool_tool"

            @property
            def description(self) -> str:
                return "Bool tool"

            @property
            def parameters(self) -> dict:
                return {
                    "type": "object",
                    "properties": {
                        "flag": {"type": "boolean"}
                    },
                    "required": ["flag"],
                }

            async def execute(self, flag: bool = False, **kwargs) -> str:
                return str(flag)

        tool = BoolTool()
        params = tool.cast_params({"flag": "true"})
        assert params["flag"] is True

        params = tool.cast_params({"flag": "false"})
        assert params["flag"] is False