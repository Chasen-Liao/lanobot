"""Lanobot 记忆系统模块.

包含：
- checkpointer: 状态持久化（MemorySaver）
- store: 长期记忆存储（InMemoryStore + 文件系统记忆）
- history: 对话历史管理（Token 计数与压缩）
- rag: RAG 检索（已在 Phase 2 完成）
"""

from lanobot.memory.checkpointer import (
    get_checkpointer,
    create_checkpointer,
)

from lanobot.memory.history import (
    ConversationHistory,
    HistoryManager,
    estimate_message_tokens,
    estimate_messages_tokens,
)

from lanobot.memory.rag import (
    RAGNode,
    InMemoryRAG,
    create_rag_node,
    load_knowledge_from_files,
)

from lanobot.memory.store import (
    MemoryStore,
    FileMemoryStore,
    MemoryFile,
    get_store,
    DEFAULT_MEMORY_PATH,
)

__all__ = [
    # checkpointer
    "get_checkpointer",
    "create_checkpointer",
    # store
    "MemoryStore",
    "FileMemoryStore",
    "MemoryFile",
    "get_store",
    "DEFAULT_MEMORY_PATH",
    # history
    "ConversationHistory",
    "HistoryManager",
    "estimate_message_tokens",
    "estimate_messages_tokens",
    # rag
    "RAGNode",
    "InMemoryRAG",
    "create_rag_node",
    "load_knowledge_from_files",
]