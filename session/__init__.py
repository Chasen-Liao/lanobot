"""会话管理模块 - 持久化会话管理（JSONL 存储 + LLM 摘要）。

支持：
- 会话创建、加载、保存、删除
- 多渠道会话隔离（key = channel:chat_id）
- 过期自动清理（30天）
- 消息摘要压缩（10万 tokens，LLM 生成）
- 标题管理（LLM 生成 + 用户自定义）
- 与 HistoryManager 集成
- JSONL 追加写入

使用示例:
    >>> from session import SessionManager, Session
    >>>
    >>> # 创建会话管理器
    >>> manager = SessionManager(workspace=Path("./workspace"))
    >>>
    >>> # 获取或创建会话
    >>> session = manager.get_or_create("telegram:123456789")
    >>>
    >>> # 添加消息
    >>> session.add_message("user", "你好")
    >>>
    >>> # 保存会话
    >>> manager.save(session)
    >>>
    >>> # 列出所有会话
    >>> sessions = manager.list_sessions()
    >>>
    >>> # 清理过期会话
    >>> manager.cleanup_expired()
    >>>
    >>> # 压缩检查（10万 tokens 触发 LLM 摘要）
    >>> await manager.compress_if_needed(session, llm)
"""

from .manager import SessionManager, SessionManagerType, create_session_manager
from .types import (
    DEFAULT_COMPRESSION_THRESHOLD,
    DEFAULT_EXPIRE_DAYS,
    Session,
    SessionMetadata,
    SessionMetadataType,
    SessionType,
)

__version__ = "0.1.0"

__all__ = [
    # 类型
    "Session",
    "SessionMetadata",
    "SessionType",
    "SessionMetadataType",
    "SessionManager",
    "SessionManagerType",
    # 便捷函数
    "create_session_manager",
    # 常量
    "DEFAULT_EXPIRE_DAYS",
    "DEFAULT_COMPRESSION_THRESHOLD",
    # 版本
    "__version__",
]