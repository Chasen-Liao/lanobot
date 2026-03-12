"""历史管理模块 - 对话历史管理、Token 计数与压缩.

基于 nanobot 的 MemoryConsolidator 逻辑实现。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

try:
    import tiktoken
except ImportError:
    tiktoken = None

# tiktoken 编码器缓存
_ENCODING_CACHE = None


def _get_encoding():
    """获取 tiktoken 编码器（带缓存）."""
    global _ENCODING_CACHE
    if tiktoken is None:
        return None
    if _ENCODING_CACHE is None:
        _ENCODING_CACHE = tiktoken.get_encoding("cl100k_base")
    return _ENCODING_CACHE


# ==================== Token 估算 ====================


def estimate_message_tokens(message: dict[str, Any]) -> int:
    """估算单条消息的 token 数量.

    Args:
        message: 消息字典

    Returns:
        估算的 token 数量
    """
    content = message.get("content")
    parts: list[str] = []

    # 处理消息内容
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    text = part.get("text", "")
                    if text:
                        parts.append(text)
                else:
                    parts.append(json.dumps(part, ensure_ascii=False))
    elif content is not None:
        parts.append(json.dumps(content, ensure_ascii=False))

    # 处理 tool_calls 和元数据
    for key in ("name", "tool_call_id"):
        value = message.get(key)
        if isinstance(value, str) and value:
            parts.append(value)

    if message.get("tool_calls"):
        parts.append(json.dumps(message["tool_calls"], ensure_ascii=False))

    payload = "\n".join(parts)
    if not payload:
        return 1

    # 使用 tiktoken 或简单估算
    enc = _get_encoding()
    if enc:
        try:
            return max(1, len(enc.encode(payload)))
        except Exception:
            pass

    # 回退：按字符数/4 估算
    return max(1, len(payload) // 4)


def estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    """估算多条消息的总 token 数量.

    Args:
        messages: 消息列表

    Returns:
        估算的 token 总数
    """
    return sum(estimate_message_tokens(msg) for msg in messages)


# ==================== 历史记录 ====================


@dataclass
class ConversationHistory:
    """对话历史记录器.

    管理对话消息，支持 token 计数和自动压缩。
    """

    messages: list[dict[str, Any]] = field(default_factory=list)
    max_tokens: int = 32000  # 默认上下文窗口的一半
    last_consolidated: int = 0  # 上次整合的位置

    def add_message(self, message: dict[str, Any]) -> None:
        """添加消息到历史.

        Args:
            message: 消息字典
        """
        # 添加时间戳
        if "timestamp" not in message:
            message["timestamp"] = datetime.now().isoformat()
        self.messages.append(message)

    def get_messages(
        self,
        max_messages: Optional[int] = None,
        include_system: bool = True,
    ) -> list[dict[str, Any]]:
        """获取历史消息.

        Args:
            max_messages: 最大消息数（从后往前）
            include_system: 是否包含系统消息

        Returns:
            消息列表
        """
        # 过滤系统消息
        msgs = self.messages
        if not include_system:
            msgs = [m for m in msgs if m.get("role") != "system"]

        # 限制数量
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
        """估算当前消息历史的 token 数量.

        Returns:
            估算的 token 数
        """
        return estimate_messages_tokens(self.messages)

    def needs_compression(self) -> bool:
        """检查是否需要压缩.

        Returns:
            是否超过 token 限制
        """
        return self.estimate_tokens() > self.max_tokens

    def get_unconsolidated_count(self) -> int:
        """获取未整合的消息数量.

        Returns:
            未整合消息数
        """
        return len(self.messages) - self.last_consolidated

    def mark_consolidated(self, up_to_index: int) -> None:
        """标记已整合的消息位置.

        Args:
            up_to_index: 整合到哪个位置（不包含）
        """
        self.last_consolidated = max(self.last_consolidated, up_to_index)

    def compress(self, keep_recent: int = 20) -> list[dict[str, Any]]:
        """压缩历史，保留最近的 N 条消息.

        Args:
            keep_recent: 保留的最近消息数

        Returns:
            被压缩的消息列表（可用于整合到长期记忆）
        """
        if len(self.messages) <= keep_recent:
            return []

        # 保留系统消息 + 最近消息
        system_msgs = [m for m in self.messages if m.get("role") == "system"]
        recent_msgs = self.messages[-keep_recent:]

        # 被压缩的消息
        compressed = self.messages[:len(self.messages) - keep_recent + len(system_msgs)]

        # 更新消息列表
        self.messages = system_msgs + recent_msgs
        self.last_consolidated = len(self.messages)

        return compressed

    def clear(self) -> None:
        """清空历史记录."""
        self.messages.clear()
        self.last_consolidated = 0

    def to_langchain_format(self) -> list[dict[str, Any]]:
        """转换为 LangChain 消息格式.

        Returns:
            LangChain 格式的消息列表
        """
        result = []
        for msg in self.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # 处理工具调用
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                result.append({
                    "role": role,
                    "content": content,
                    "tool_calls": tool_calls,
                })
                # 添加工具结果
                if msg.get("tool_call_results"):
                    for result_msg in msg["tool_call_results"]:
                        result.append({
                            "role": "tool",
                            "content": result_msg.get("content", ""),
                            "tool_call_id": result_msg.get("tool_call_id"),
                        })
            else:
                result.append({"role": role, "content": content})

        return result


# ==================== 便捷函数 ====================


class HistoryManager:
    """历史管理器 - 封装 ConversationHistory 的便捷类.

    支持多会话管理，自动创建和清理历史记录。
    """

    def __init__(self, max_tokens: int = 32000):
        """初始化历史管理器.

        Args:
            max_tokens: 每个会话的最大 token 数
        """
        self._histories: dict[str, ConversationHistory] = {}
        self._max_tokens = max_tokens

    def get_or_create(self, thread_id: str) -> ConversationHistory:
        """获取或创建会话历史.

        Args:
            thread_id: 线程 ID

        Returns:
            对话历史对象
        """
        if thread_id not in self._histories:
            self._histories[thread_id] = ConversationHistory(
                max_tokens=self._max_tokens
            )
        return self._histories[thread_id]

    def add_message(
        self,
        thread_id: str,
        content: str,
        role: str = "user",
        **metadata,
    ) -> None:
        """添加消息到指定会话.

        Args:
            thread_id: 线程 ID
            content: 消息内容
            role: 消息角色
            **metadata: 额外元数据
        """
        history = self.get_or_create(thread_id)
        message = {
            "role": role,
            "content": content,
            **metadata,
        }
        history.add_message(message)

    def get_history(
        self,
        thread_id: str,
        max_messages: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """获取会话历史.

        Args:
            thread_id: 线程 ID
            max_messages: 最大消息数

        Returns:
            消息列表
        """
        if thread_id not in self._histories:
            return []
        return self._histories[thread_id].get_messages(max_messages=max_messages)

    def estimate_tokens(self, thread_id: str) -> int:
        """估算会话的 token 数量.

        Args:
            thread_id: 线程 ID

        Returns:
            估算的 token 数
        """
        if thread_id not in self._histories:
            return 0
        return self._histories[thread_id].estimate_tokens()

    def compress_if_needed(
        self,
        thread_id: str,
        keep_recent: int = 20,
    ) -> list[dict[str, Any]]:
        """如果需要则压缩历史.

        Args:
            thread_id: 线程 ID
            keep_recent: 保留的最近消息数

        Returns:
            被压缩的消息列表
        """
        if thread_id not in self._histories:
            return []
        history = self._histories[thread_id]
        if history.needs_compression():
            return history.compress(keep_recent)
        return []

    def delete(self, thread_id: str) -> bool:
        """删除指定会话的历史.

        Args:
            thread_id: 线程 ID

        Returns:
            是否成功删除
        """
        if thread_id in self._histories:
            del self._histories[thread_id]
            return True
        return False

    def clear_all(self) -> None:
        """清空所有会话历史."""
        self._histories.clear()

    def list_threads(self) -> list[str]:
        """列出所有会话 ID.

        Returns:
            会话 ID 列表
        """
        return list(self._histories.keys())


__all__ = [
    "ConversationHistory",
    "HistoryManager",
    "estimate_message_tokens",
    "estimate_messages_tokens",
]