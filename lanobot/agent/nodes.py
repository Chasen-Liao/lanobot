"""自定义 LangGraph 节点 - RAG 检索、模型路由、LLM 调用."""

from typing import Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from lanobot.agent.state import AgentState
from lanobot.agent.router import ModelRouter
from lanobot.memory.rag import RAGNode


# ============== RAG 检索节点 ==============

def create_rag_node(rag_retriever: Optional[RAGNode] = None):
    """创建 RAG 检索节点.

    在 LLM 调用前自动检索知识库并注入上下文。

    Args:
        rag_retriever: RAG 检索器实例

    Returns:
        节点函数
    """
    async def rag_node(state: AgentState) -> dict[str, Any]:
        """RAG 检索节点.

        根据用户最新消息检索知识库，将结果存入状态。
        """
        if not rag_retriever:
            return {"rag_context": None}

        # 获取用户最新消息
        messages = state.get("messages", [])
        if not messages:
            return {"rag_context": None}

        latest_message = messages[-1]
        query = latest_message.content if hasattr(latest_message, "content") else str(latest_message)

        # 执行检索
        context = await rag_retriever.retrieve(query)
        return {"rag_context": context}

    return rag_node


# ============== 模型路由节点 ==============

def create_router_node(router: Optional[ModelRouter] = None):
    """创建模型路由节点.

    根据用户消息自动选择合适的模型。

    Args:
        router: ModelRouter 实例

    Returns:
        节点函数
    """
    def router_node(state: AgentState) -> dict[str, Any]:
        """模型路由节点.

        根据用户消息选择合适的模型，将选中的模型存入状态。
        """
        if not router:
            return {"selected_model": None}

        # 获取用户最新消息
        messages = state.get("messages", [])
        if not messages:
            return {"selected_model": None}

        latest_message = messages[-1]
        query = latest_message.content if hasattr(latest_message, "content") else str(latest_message)

        # 选择模型
        model = router.select_model(query)
        return {"selected_model": model}

    return router_node


# ============== LLM 调用节点 ==============

def create_llm_node(
    default_model: BaseChatModel,
    system_prompt: Optional[str] = None,
):
    """创建 LLM 调用节点.

    使用 Router 选择的模型（或默认模型）调用 LLM。

    Args:
        default_model: 默认模型
        system_prompt: 系统提示词

    Returns:
        节点函数
    """
    async def llm_node(state: AgentState) -> dict[str, Any]:
        """LLM 节点.

        执行 LLM 调用，返回新消息。
        """
        messages = state.get("messages", [])

        # 获取当前使用的模型
        model = state.get("selected_model") or default_model

        # 构建系统消息（带 RAG 上下文）
        system_parts = []

        # 添加基础系统提示
        if system_prompt:
            system_parts.append(system_prompt)

        # 添加 RAG 上下文
        rag_context = state.get("rag_context")
        if rag_context:
            context_msg = f"""<context>
{rag_context}
</context>

根据以上上下文回答用户问题。如果上下文不相关，请忽略并基于你自身的知识回答。"""
            system_parts.append(context_msg)

        # 构建最终消息列表
        if system_parts:
            system_message = SystemMessage(content="\n\n".join(system_parts))
            # 将 system message 插入到消息开头
            final_messages = [system_message] + list(messages)
        else:
            final_messages = list(messages)

        # 调用模型
        response = await model.ainvoke(final_messages)

        # 返回新消息（会被 add_messages 合并）
        return {"messages": [response]}

    return llm_node


# ============== 工具执行节点 ==============

def create_tool_node(tools: list[Runnable]):
    """创建工具执行节点.

    Args:
        tools: 工具列表

    Returns:
        节点函数
    """
    from langchain_core.utils.function_calling import convert_to_openai_function
    from langgraph.prebuilt import ToolNode as LangGraphToolNode

    # LangGraph 的 ToolNode
    tool_node = LangGraphToolNode(tools)
    return tool_node


# ============== 条件边函数 ==============

def should_continue_with_tools(state: AgentState) -> str:
    """判断是否继续执行工具.

    Args:
        state: 当前状态

    Returns:
        "tools" 表示继续执行工具，"end" 表示结束
    """
    messages = state.get("messages", [])
    if not messages:
        return "end"

    last_message = messages[-1]

    # 检查是否有工具调用
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # 检查 message 是否包含 additional_kwargs（可能包含工具调用）
    if hasattr(last_message, "additional_kwargs"):
        additional_kwargs = last_message.additional_kwargs or {}
        if "tool_calls" in additional_kwargs:
            return "tools"

    return "end"


# ============== 便捷构建函数 ==============

def build_system_message(
    base_prompt: Optional[str] = None,
    rag_context: Optional[str] = None,
) -> Optional[str]:
    """构建系统消息.

    Args:
        base_prompt: 基础系统提示词
        rag_context: RAG 检索的上下文

    Returns:
        格式化后的系统消息字符串
    """
    parts = []

    if base_prompt:
        parts.append(base_prompt)

    if rag_context:
        parts.append(f"""<context>
{rag_context}
</context>

根据以上上下文回答用户问题。如果上下文不相关，请忽略并基于你自身的知识回答。""")

    return "\n\n".join(parts) if parts else None