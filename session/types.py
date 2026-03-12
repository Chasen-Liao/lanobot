"""会话数据类型定义.

定义 Session 和 SessionMetadata 数据类，用于会话持久化管理。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

# 默认过期时间（天）
DEFAULT_EXPIRE_DAYS = 30

# 默认压缩阈值（token）
DEFAULT_COMPRESSION_THRESHOLD = 100_000  # 10万 tokens进行压缩


@dataclass
class SessionMetadata:
    """会话元数据.

    包含会话的标题、过期时间、固定标志等信息。
    """

    # 会话 key（channel:chat_id）
    key: str = ""

    # 会话标题（可选，LLM 生成或用户自定义）
    title: str = ""

    # 标题来源：auto=LLM生成，user=用户自定义
    title_source: str = "auto"

    # 创建时间
    created_at: datetime = field(default_factory=datetime.now)

    # 更新时间
    updated_at: datetime = field(default_factory=datetime.now)

    # 过期时间（当 is_pinned=False 时有效）
    expires_at: Optional[datetime] = None

    # 是否固定（固定会话不会被自动清理）
    is_pinned: bool = False

    # 消息总数
    message_count: int = 0

    # 预估 token 数
    estimated_tokens: int = 0

    # 上次摘要时间
    last_summarized_at: Optional[datetime] = None

    # 摘要 token 数
    summary_token_count: int = 0

    def should_expire(self) -> bool:
        """检查会话是否应该过期.

        Returns:
            如果会话已过期且未固定，返回 True
        """
        if self.is_pinned:
            return False
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def touch(self) -> None:
        """更新最后活跃时间."""
        self.updated_at = datetime.now()
        self.message_count += 1

    def pin(self) -> None:
        """固定会话."""
        self.is_pinned = True
        self.expires_at = None  # 固定会话永不过期

    def unpin(self) -> None:
        """取消固定会话."""
        self.is_pinned = False
        # 设置新的过期时间
        self.expires_at = datetime.now() + timedelta(days=DEFAULT_EXPIRE_DAYS)

    def set_title(self, title: str) -> None:
        """设置会话标题.

        Args:
            title: 会话标题
        """
        self.title = title

    def to_dict(self) -> dict[str, Any]:
        """转换为字典.

        Returns:
            字典表示
        """
        return {
            "key": self.key,
            "title": self.title,
            "title_source": self.title_source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_pinned": self.is_pinned,
            "message_count": self.message_count,
            "estimated_tokens": self.estimated_tokens,
            "last_summarized_at": self.last_summarized_at.isoformat() if self.last_summarized_at else None,
            "summary_token_count": self.summary_token_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMetadata:
        """从字典创建.

        Args:
            data: 字典数据

        Returns:
            SessionMetadata 实例
        """
        expires_at = None
        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"])

        last_summarized_at = None
        if data.get("last_summarized_at"):
            last_summarized_at = datetime.fromisoformat(data["last_summarized_at"])

        return cls(
            key=data.get("key", ""),
            title=data.get("title", ""),
            title_source=data.get("title_source", "auto"),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if data.get("updated_at")
            else datetime.now(),
            expires_at=expires_at,
            is_pinned=data.get("is_pinned", False),
            message_count=data.get("message_count", 0),
            estimated_tokens=data.get("estimated_tokens", 0),
            last_summarized_at=last_summarized_at,
            summary_token_count=data.get("summary_token_count", 0),
        )


@dataclass
class Session:
    """会话数据类.

    管理对话消息和元数据，支持 token 估算和自动压缩。
    """

    # 会话 key（channel:chat_id）
    key: str = ""

    # 会话元数据
    metadata: SessionMetadata = field(default_factory=SessionMetadata)

    # 消息列表
    messages: list[dict[str, Any]] = field(default_factory=list)

    # 上次整合位置
    last_consolidated: int = 0

    def add_message(
        self,
        role: str,
        content: Any,
        **extra_fields: Any,
    ) -> None:
        """添加消息到会话.

        Args:
            role: 消息角色 (user/assistant/system/tool)
            content: 消息内容
            **extra_fields: 额外字段
        """
        from lanobot.memory.history import estimate_message_tokens

        message: dict[str, Any] = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **extra_fields,
        }
        self.messages.append(message)
        self.metadata.touch()
        self.metadata.estimated_tokens += estimate_message_tokens(message)
        # 同步 key 到 metadata
        if self.key:
            self.metadata.key = self.key

    def get_history(
        self,
        max_messages: Optional[int] = None,
        include_system: bool = True,
    ) -> list[dict[str, Any]]:
        """获取历史消息.

        Args:
            max_messages: 最大消息数（从后往前），None 表示全部
            include_system: 是否包含系统消息

        Returns:
            消息列表
        """
        msgs = self.messages
        if not include_system:
            msgs = [m for m in msgs if m.get("role") != "system"]

        if max_messages and len(msgs) > max_messages:
            return msgs[-max_messages:]

        return msgs

    def get_recent(self, count: int = 10) -> list[dict[str, Any]]:
        """获取最近 N 条消息.

        Args:
            count: 消息数量

        Returns:
            最近的消息列表
        """
        return self.messages[-count:] if self.messages else []

    def estimate_tokens(self) -> int:
        """估算会话的 token 数量.

        Returns:
            预估 token 数
        """
        return self.metadata.estimated_tokens

    def needs_compression(self, threshold: int = DEFAULT_COMPRESSION_THRESHOLD) -> bool:
        """检查是否需要压缩.

        Args:
            threshold: 压缩阈值

        Returns:
            是否超过 token 阈值
        """
        return self.metadata.estimated_tokens > threshold

    def compress(self, keep_recent: int = 20) -> list[dict[str, Any]]:
        """压缩历史，保留最近的 N 条消息.

        Args:
            keep_recent: 保留的最近消息数

        Returns:
            被压缩的消息列表
        """
        if len(self.messages) <= keep_recent:
            return []

        # 保留系统消息 + 最近消息
        system_msgs = [m for m in self.messages if m.get("role") == "system"]
        recent_msgs = self.messages[-keep_recent:]

        # 被压缩的消息
        compressed = self.messages[: len(self.messages) - keep_recent + len(system_msgs)]

        # 重新计算 token
        from lanobot.memory.history import estimate_messages_tokens

        system_tokens = estimate_messages_tokens(system_msgs)
        recent_tokens = estimate_messages_tokens(recent_msgs)

        # 更新消息列表
        self.messages = system_msgs + recent_msgs
        self.metadata.estimated_tokens = system_tokens + recent_tokens

        return compressed

    def clear(self) -> None:
        """清空会话消息."""
        self.messages.clear()
        self.metadata.estimated_tokens = 0
        self.metadata.message_count = 0

    def mark_consolidated(self, up_to_index: int) -> None:
        """标记已整合的消息位置.

        Args:
            up_to_index: 整合到哪个位置（不包含）
        """
        # 保留的消息数量
        self.messages = self.messages[:up_to_index]

    def to_langchain_format(self) -> list[dict[str, Any]]:
        """转换为 LangChain 消息格式.

        Returns:
            LangChain 格式的消息列表
        """
        from lanobot.memory.history import ConversationHistory

        # 复用 ConversationHistory 的转换逻辑
        history = ConversationHistory(
            messages=self.messages,
            max_tokens=DEFAULT_COMPRESSION_THRESHOLD,
        )
        return history.to_langchain_format()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典.

        Returns:
            字典表示
        """
        return {
            "key": self.key,
            "messages": self.messages,
            "metadata": self.metadata.to_dict(),
            "last_consolidated": self.last_consolidated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        """从字典创建.

        Args:
            data: 字典数据

        Returns:
            Session 实例
        """
        metadata = SessionMetadata.from_dict(data.get("metadata", {}))
        # 兼容旧结构
        key = data.get("key") or data.get("session_id", "")
        return cls(
            key=key,
            metadata=metadata,
            messages=data.get("messages", []),
            last_consolidated=data.get("last_consolidated", 0),
        )


# 类型别名
SessionType = Session
SessionMetadataType = SessionMetadata

__all__ = [
    "Session",
    "SessionMetadata",
    "SessionType",
    "SessionMetadataType",
    "DEFAULT_EXPIRE_DAYS",
    "DEFAULT_COMPRESSION_THRESHOLD",
]