"""Tests for Web tools."""

import pytest
from lanobot.tools.web import (
    WebSearchTool,
    WebFetchTool,
    _validate_url,
    _strip_tags,
    _normalize,
)


class TestWebSearchTool:
    """Test cases for WebSearchTool."""

    def test_missing_api_key(self):
        """Test that search fails without API key."""
        tool = WebSearchTool(api_key=None)

        result = tool.api_key
        assert result == ""

    @pytest.mark.asyncio
    async def test_search_without_api_key(self):
        """Test search execution without API key."""
        tool = WebSearchTool(api_key=None)

        result = await tool.execute(query="test")

        assert "Error" in result
        assert "API key" in result


class TestWebFetchTool:
    """Test cases for WebFetchTool."""

    def test_validate_url_valid(self):
        """Test URL validation with valid URLs."""
        assert _validate_url("https://example.com") == (True, "")
        assert _validate_url("http://example.com") == (True, "")

    def test_validate_url_invalid(self):
        """Test URL validation with invalid URLs."""
        # Invalid scheme
        valid, msg = _validate_url("ftp://example.com")
        assert valid is False

        # Missing domain
        valid, msg = _validate_url("http://")
        assert valid is False

        # Invalid URL
        valid, msg = _validate_url("not-a-url")
        assert valid is False

    def test_strip_tags(self):
        """Test HTML tag stripping."""
        text = _strip_tags("<p>Hello <b>World</b></p>")
        assert text == "Hello World"

    def test_strip_tags_script(self):
        """Test script tag removal."""
        text = _strip_tags("<script>alert('xss')</script><p>Hello</p>")
        assert "script" not in text.lower()
        assert "alert" not in text
        assert "Hello" in text

    def test_normalize(self):
        """Test whitespace normalization."""
        text = _normalize("Hello    World\n\n\n\nTest")
        assert "    " not in text
        assert "\n\n\n\n" not in text

    @pytest.mark.asyncio
    async def test_fetch_invalid_url(self):
        """Test fetching with invalid URL."""
        tool = WebFetchTool()

        result = await tool.execute(url="not-a-valid-url")

        assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_fetch_config(self):
        """Test fetch configuration."""
        tool = WebFetchTool(max_chars=30000, proxy="http://proxy:8080")
        assert tool.max_chars == 30000
        assert tool.proxy == "http://proxy:8080"

    @pytest.mark.asyncio
    async def test_fetch_invalid_schema(self):
        """Test fetch with invalid URL schema."""
        tool = WebFetchTool()

        # Test with invalid schema (file://)
        result = await tool.execute(url="file:///etc/passwd")

        # Should return error for non-http schema
        assert "error" in result.lower()