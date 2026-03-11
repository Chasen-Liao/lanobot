"""Message bus queue tests"""
import asyncio
import pytest

from bus.queue import MessageBus
from bus.events import InboundMessage, OutboundMessage


class TestMessageBus:
    """消息总线测试"""

    @pytest.fixture
    def bus(self):
        """创建消息总线"""
        return MessageBus()

    @pytest.mark.asyncio
    async def test_initial_state(self, bus):
        """测试初始状态"""
        assert bus.inbound_size == 0
        assert bus.outbound_size == 0

    @pytest.mark.asyncio
    async def test_publish_and_consume_inbound(self, bus):
        """测试入站消息发布和消费"""
        msg = InboundMessage(
            channel="telegram",
            sender_id="user123",
            chat_id="chat456",
            content="Hello",
        )

        await bus.publish_inbound(msg)
        assert bus.inbound_size == 1

        consumed = await bus.consume_inbound()
        assert consumed.content == "Hello"
        assert bus.inbound_size == 0

    @pytest.mark.asyncio
    async def test_publish_and_consume_outbound(self, bus):
        """测试出站消息发布和消费"""
        msg = OutboundMessage(
            channel="telegram",
            chat_id="chat456",
            content="Response",
        )

        await bus.publish_outbound(msg)
        assert bus.outbound_size == 1

        consumed = await bus.consume_outbound()
        assert consumed.content == "Response"
        assert bus.outbound_size == 0

    @pytest.mark.asyncio
    async def test_multiple_messages(self, bus):
        """测试多条消息"""
        # 发布多条消息
        for i in range(5):
            msg = InboundMessage(
                channel="telegram",
                sender_id="user123",
                chat_id="chat456",
                content=f"Message {i}",
            )
            await bus.publish_inbound(msg)

        assert bus.inbound_size == 5

        # 按顺序消费
        for i in range(5):
            msg = await bus.consume_inbound()
            assert msg.content == f"Message {i}"

        assert bus.inbound_size == 0

    @pytest.mark.asyncio
    async def test_fair_queue(self, bus):
        """测试公平队列（先入先出）"""
        messages = [
            InboundMessage(channel="telegram", sender_id=f"user{i}", chat_id="chat", content=f"msg{i}")
            for i in range(3)
        ]

        for msg in messages:
            await bus.publish_inbound(msg)

        # 验证按顺序消费
        for expected in messages:
            actual = await bus.consume_inbound()
            assert actual.content == expected.content

    @pytest.mark.asyncio
    async def test_separate_queues(self, bus):
        """测试入站和出站队列分离"""
        inbound = InboundMessage(
            channel="telegram",
            sender_id="user",
            chat_id="chat",
            content="inbound",
        )
        outbound = OutboundMessage(
            channel="telegram",
            chat_id="chat",
            content="outbound",
        )

        await bus.publish_inbound(inbound)
        await bus.publish_outbound(outbound)

        assert bus.inbound_size == 1
        assert bus.outbound_size == 1

        consumed_inbound = await bus.consume_inbound()
        consumed_outbound = await bus.consume_outbound()

        assert consumed_inbound.content == "inbound"
        assert consumed_outbound.content == "outbound"