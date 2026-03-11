"""异步消息队列，用于解耦通道与 Agent 核心的通信"""
import asyncio

from bus.events import InboundMessage, OutboundMessage


class MessageBus:
    """
    异步消息总线，解耦聊天通道与 Agent 核心。

    通道将消息推入入站队列，Agent 处理后
    将响应推入出站队列。
    """

    def __init__(self):
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """发布来自通道的消息到 Agent"""
        await self.inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        """消费下一条入站消息（阻塞直到可用）"""
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """发布 Agent 的响应到通道"""
        await self.outbound.put(msg)

    async def consume_outbound(self) -> OutboundMessage:
        """消费下一条出站消息（阻塞直到可用）"""
        return await self.outbound.get()

    @property
    def inbound_size(self) -> int:
        """待处理的入站消息数量"""
        return self.inbound.qsize()

    @property
    def outbound_size(self) -> int:
        """待处理的出站消息数量"""
        return self.outbound.qsize()