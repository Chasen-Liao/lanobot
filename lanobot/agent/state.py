"""Agent 状态定义."""

from typing import TypedDict, Annotated, Optional, Any

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class AgentState(TypedDict):
    """Lanobot Agent 状态类型定义.

    使用 add_messages 注释器自动合并消息列表，
    便于 LangGraph 状态管理。
    """

    messages: Annotated[list[BaseMessage], add_messages]
    """对话消息历史"""

    session_id: Optional[str] = None
    """会话ID，用于状态持久化"""

    user_id: Optional[str] = None
    """用户ID"""

    context: Optional[dict] = None
    """额外的上下文信息"""

    # === 新增字段：支持自定义节点流程 ===

    rag_context: Optional[str] = None
    """RAG 检索到的上下文，会自动注入到 system message"""

    selected_model: Optional[Any] = None
    """Router 选择的模型实例"""

    tool_calls: Optional[list[Any]] = None
    """待执行的工具调用列表"""