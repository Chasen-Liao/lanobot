"""Message events tests"""
import pytest
from datetime import datetime

from bus.events import InboundMessage, OutboundMessage


class TestInboundMessage:
    """入站消息测试"""

    def test_create_message(self):
        """测试创建消息"""
        msg = InboundMessage(
            channel="telegram",
            sender_id="user123",
            chat_id="chat456",
            content="Hello",
        )
        assert msg.channel == "telegram"
        assert msg.sender_id == "user123"
        assert msg.chat_id == "chat456"
        assert msg.content == "Hello"
        assert msg.timestamp is not None
        assert msg.media == []
        assert msg.metadata == {}

    def test_session_key(self):
        """测试会话键生成"""
        msg = InboundMessage(
            channel="telegram",
            sender_id="user123",
            chat_id="chat456",
            content="Hello",
        )
        assert msg.session_key == "telegram:chat456"

    def test_session_key_override(self):
        """测试会话键覆盖"""
        msg = InboundMessage(
            channel="telegram",
            sender_id="user123",
            chat_id="chat456",
            content="Hello",
            session_key_override="custom_session",
        )
        assert msg.session_key == "custom_session"

    def test_with_media(self):
        """测试带媒体的消息"""
        msg = InboundMessage(
            channel="telegram",
            sender_id="user123",
            chat_id="chat456",
            content="Check this",
            media=["https://example.com/image.jpg"],
        )
        assert msg.media == ["https://example.com/image.jpg"]

    def test_with_metadata(self):
        """测试带元数据的消息"""
        msg = InboundMessage(
            channel="telegram",
            sender_id="user123",
            chat_id="chat456",
            content="Hello",
            metadata={"message_id": 123, "reply_to": 456},
        )
        assert msg.metadata["message_id"] == 123
        assert msg.metadata["reply_to"] == 456


class TestOutboundMessage:
    """出站消息测试"""

    def test_create_message(self):
        """测试创建消息"""
        msg = OutboundMessage(
            channel="telegram",
            chat_id="chat456",
            content="Response",
        )
        assert msg.channel == "telegram"
        assert msg.chat_id == "chat456"
        assert msg.content == "Response"
        assert msg.reply_to is None
        assert msg.media == []
        assert msg.metadata == {}

    def test_reply_to(self):
        """测试回复功能"""
        msg = OutboundMessage(
            channel="telegram",
            chat_id="chat456",
            content="Reply",
            reply_to="message123",
        )
        assert msg.reply_to == "message123"

    def test_with_media(self):
        """测试带媒体的消息"""
        msg = OutboundMessage(
            channel="telegram",
            chat_id="chat456",
            content="Image",
            media=["https://example.com/photo.jpg"],
        )
        assert msg.media == ["https://example.com/photo.jpg"]