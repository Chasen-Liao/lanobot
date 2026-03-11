"""事件类型定义"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class InboundMessage:
    """从聊天通道接收的消息"""

    channel: str  # telegram, discord, slack, whatsapp
    sender_id: str  # 用户标识
    chat_id: str  # 聊天/通道标识
    content: str  # 消息文本
    timestamp: datetime = field(default_factory=datetime.now)
    media: list[str] = field(default_factory=list)  # 媒体 URLs
    metadata: dict[str, Any] = field(default_factory=dict)  # 通道特定数据
    session_key_override: str | None = None  # 可选的会话作用域覆盖

    @property
    def session_key(self) -> str:
        """唯一会话标识键"""
        return self.session_key_override or f"{self.channel}:{self.chat_id}"


@dataclass
class OutboundMessage:
    """发送到聊天通道的消息"""

    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)