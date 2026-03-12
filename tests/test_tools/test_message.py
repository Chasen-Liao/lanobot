"""Tests for MessageTool."""

import pytest
from lanobot.tools.message import MessageTool, OutboundMessage


class TestMessageTool:
    """Test cases for MessageTool."""

    @pytest.mark.asyncio
    async def test_send_message_without_callback(self):
        """Test sending a message without callback returns mock result."""
        tool = MessageTool(default_channel="cli", default_chat_id="user123")

        result = await tool.execute(content="Hello, World!")

        assert "Message (mock)" in result
        assert "cli:user123" in result
        assert "Hello, World!" in result

    @pytest.mark.asyncio
    async def test_send_message_with_context(self):
        """Test sending a message from context."""
        tool = MessageTool()
        tool.set_context("telegram", "chat456")

        result = await tool.execute(content="Test message")

        assert "Message (mock)" in result
        assert "telegram:chat456" in result

    @pytest.mark.asyncio
    async def test_send_message_no_channel(self):
        """Test sending without channel returns error."""
        tool = MessageTool()

        result = await tool.execute(content="Test")

        assert "Error" in result
        assert "channel/chat" in result.lower()

    def test_set_context(self):
        """Test setting message context."""
        tool = MessageTool()
        tool.set_context("discord", "channel789", message_id="msg123")

        assert tool._default_channel == "discord"
        assert tool._default_chat_id == "channel789"
        assert tool._default_message_id == "msg123"

    def test_outbound_message_creation(self):
        """Test OutboundMessage creation."""
        msg = OutboundMessage(
            channel="telegram",
            chat_id="12345",
            content="Hello",
            media=["file1.jpg"],
            metadata={"reply_to": "msg_abc"},
        )

        assert msg.channel == "telegram"
        assert msg.chat_id == "12345"
        assert msg.content == "Hello"
        assert msg.media == ["file1.jpg"]
        assert msg.metadata["reply_to"] == "msg_abc"


class TestOutboundMessage:
    """Test cases for OutboundMessage."""

    def test_default_values(self):
        """Test default values."""
        msg = OutboundMessage(channel="a", chat_id="b", content="c")

        assert msg.media == []
        assert msg.metadata == {}

    def test_with_media(self):
        """Test with media attachments."""
        msg = OutboundMessage(
            channel="feishu",
            chat_id="abc",
            content="With files",
            media=["doc1.pdf", "img.png"],
        )

        assert len(msg.media) == 2
        assert "doc1.pdf" in msg.media