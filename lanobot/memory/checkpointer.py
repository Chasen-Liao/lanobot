"""Checkpointer 模块 - 状态持久化工厂.

支持 MemorySaver（内存）作为唯一后端。
"""

from typing import Optional

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver


def get_checkpointer(
    backend: str = "memory",
    **kwargs,
) -> BaseCheckpointSaver:
    """获取 Checkpointer 工厂函数.

    Args:
        backend: 存储后端类型，目前仅支持 "memory"
        **kwargs: 保留参数（忽略）

    Returns:
        BaseCheckpointSaver 实例

    Raises:
        ValueError: 当 backend 不是 "memory" 时

    Examples:
        # 使用内存后端（默认）
        >>> checkpointer = get_checkpointer()
    """
    if backend == "memory":
        return MemorySaver()

    raise ValueError(f"Unknown backend: {backend}. Supported: 'memory'")


def create_checkpointer(
    config: Optional[RunnableConfig] = None,
    **kwargs,
) -> BaseCheckpointSaver:
    """从配置字典创建 Checkpointer（兼容旧 API）。

    Args:
        config: LangGraph 配置字典（可选）
        **kwargs: 传递给 get_checkpointer 的参数

    Returns:
        BaseCheckpointSaver 实例
    """
    backend = kwargs.pop("backend", "memory")
    return get_checkpointer(backend, **kwargs)


# 类型别名
CheckpointerType = MemorySaver