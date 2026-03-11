"""聊天平台通道基类接口"""
from abc import ABC, abstractmethod
from typing import Any

from bus.events import InboundMessage, OutboundMessage
from bus.queue import MessageBus


class BaseChannel(ABC):
    """
    聊天通道实现的抽象基类。

    每个通道（Telegram、Discord 等）应实现此接口
    以与 lanobot 消息总线集成。
    """

    name: str = "base"

    def __init__(self, config: Any, bus: MessageBus):
        """
        初始化通道。

        Args:
            config: 通道特定配置。
            bus: 用于通信的消息总线。
        """
        self.config = config
        self.bus = bus
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        """
        启动通道并开始监听消息。

        这应该是一个长时间运行的异步任务：
        1. 连接到聊天平台
        2. 监听传入消息
        3. 通过 _handle_message() 转发到总线
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止通道并清理资源。"""

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """
        通过此通道发送消息。

        Args:
            msg: 要发送的消息。
        """
        pass

    def is_allowed(self, sender_id: str) -> bool:
        """检查 *sender_id* 是否被允许。 空列表→拒绝所有； ``"*"`` →允许所有。"""
        allow_list = getattr(self.config, "allow_from", [])
        if not allow_list:
            # 默认拒绝所有
            return False
        if "*" in allow_list:
            return True
        return str(sender_id) in allow_list

    async def _handle_message(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        session_key: str | None = None,
    ) -> None:
        """
        处理来自聊天平台的传入消息。

        此方法检查权限并转发到总线。

        Args:
            sender_id: 发送者标识。
            chat_id: 聊天/通道标识。
            content: 消息文本内容。
            media: 可选的媒体 URLs 列表。
            metadata: 可选的通道特定元数据。
            session_key: 可选的会话键覆盖（如线程作用域会话）。
        """
        if not self.is_allowed(sender_id):
            print(f"[{self.name}] 拒绝访问: {sender_id}")
            return

        msg = InboundMessage(
            channel=self.name,
            sender_id=str(sender_id),
            chat_id=str(chat_id),
            content=content,
            media=media or [],
            metadata=metadata or {},
            session_key_override=session_key,
        )

        await self.bus.publish_inbound(msg)

    @property
    def is_running(self) -> bool:
        """检查通道是否正在运行。"""
        return self._running