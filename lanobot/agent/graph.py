"""Agent Graph 构建器 - 基于 LangGraph StateGraph 自定义节点."""

from typing import Any, AsyncIterator, Optional, Union

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END

from lanobot.agent.state import AgentState
from lanobot.agent.nodes import (
    create_rag_node,
    create_router_node,
    create_llm_node,
    create_tool_node,
    should_continue_with_tools,
)
from lanobot.agent.router import ModelRouter
from lanobot.memory.checkpointer import get_checkpointer
from lanobot.memory.rag import RAGNode
from lanobot.memory.store import MemoryStore

# 支持的工具类型
ToolType = Union[Runnable, Any]  # LangChain Runnable 或 Lanobot Tool

# Checkpointer 类型
CheckpointerType = Optional[BaseCheckpointSaver]


class AgentGraph:
    """Lanobot Agent 构建器 - 基于 StateGraph 自定义节点.

    支持以下自定义节点：
    - RAG 检索节点：自动从知识库检索上下文
    - 模型路由节点：根据任务类型自动选择合适模型
    - LLM 调用节点：使用选中的模型执行推理
    - 工具执行节点：处理工具调用

    示例:
        >>> from lanobot.agent.graph import AgentGraph
        >>> from lanobot.memory.rag import create_rag_node as create_rag
        >>> from lanobot.tools import create_tool_registry
        >>> router = ModelRouter(default_model=model)
        >>> # 创建工具注册表
        >>> registry = create_tool_registry(workspace="./workspace")
        >>> # 或直接传入 LangChain 工具
        >>> tools = registry.get_langchain_tools()
        >>> agent = AgentGraph(
        ...     model=model,
        ...     tools=tools,
        ...     router=router,
        ...     rag_node=create_rag(knowledge_dir=Path("./knowledge")),
        ... )
        >>> result = agent.invoke("hello", thread_id="user-123")
    """

    def __init__(
        self,
        model: BaseChatModel,
        tools: Optional[list[ToolType]] = None,
        *,
        # RAG 配置
        rag_node: Optional[RAGNode] = None,
        rag_enabled: bool = True,
        # 路由配置
        router: Optional[ModelRouter] = None,
        router_enabled: bool = True,
        # 额外模型配置（会创建 Router）
        fast_model: Optional[BaseChatModel] = None,
        strong_model: Optional[BaseChatModel] = None,
        code_model: Optional[BaseChatModel] = None,
        # 系统提示词
        system_prompt: Optional[str] = None,
        # 状态持久化（Checkpointer）
        checkpointer: Optional[BaseCheckpointSaver] = None,
        checkpointer_backend: str = "memory",
        checkpointer_conn_string: Optional[str] = None,
        # 长期记忆（Store）
        store: Optional[MemoryStore] = None,
        store_workspace: Optional[str] = None,
    ):
        """初始化 AgentGraph.

        Args:
            model: 默认 LLM 模型
            tools: 工具列表，支持 LangChain Runnable 或 Lanobot Tool
            rag_node: RAG 检索节点（可选）
            rag_enabled: 是否启用 RAG（默认 True）
            router: 模型路由器（可选）
            router_enabled: 是否启用路由（默认 True）
            fast_model: 快速模型（简单任务）
            strong_model: 强力模型（复杂任务）
            code_model: 代码专用模型
            system_prompt: 系统提示词
            checkpointer: 状态持久化检查点，直接传入实例
            checkpointer_backend: 检查点后端类型，"memory" 或 "postgres"
            checkpointer_conn_string: PostgreSQL 连接字符串
            store: 长期记忆存储（可选）
            store_workspace: 记忆存储的工作空间路径（用于文件记忆）

        示例:
            # 使用 Lanobot 工具注册表
            >>> from lanobot.tools import create_tool_registry
            >>> registry = create_tool_registry(workspace="./workspace", include_filesystem=True)
            >>> tools = registry.get_langchain_tools()
            >>> agent = AgentGraph(model=model, tools=tools)

            # 使用 PostgreSQL 持久化
            >>> from lanobot.memory import get_checkpointer
            >>> checkpointer = get_checkpointer("postgres", conn_string="...")
            >>> agent = AgentGraph(model=model, checkpointer=checkpointer)
"""
        self._model = model
        self._tools = tools or []
        self._rag_node = rag_node
        self._rag_enabled = rag_enabled and rag_node is not None
        self._router = router
        self._router_enabled = router_enabled and router is not None

        # 如果提供了额外模型但没有 router，自动创建
        if not self._router and any([fast_model, strong_model, code_model]):
            self._router = ModelRouter(
                default_model=model,
                fast_model=fast_model,
                strong_model=strong_model,
                code_model=code_model,
            )
            self._router_enabled = True

        self._system_prompt = system_prompt

        # 初始化 checkpointer
        if checkpointer is not None:
            self._checkpointer = checkpointer
        elif checkpointer_backend == "postgres":
            self._checkpointer = get_checkpointer(
                "postgres",
                conn_string=checkpointer_conn_string,
            )
        else:
            self._checkpointer = MemorySaver()

        # 初始化 store（长期记忆）
        if store is not None:
            self._store = store
        elif store_workspace:
            from pathlib import Path
            self._store = MemoryStore(workspace=Path(store_workspace))
        else:
            self._store = None

        # 构建图
        self._graph: Runnable = self._build_graph()

    def _build_graph(self) -> Runnable:
        """构建 LangGraph StateGraph.

        流程：
        START -> rag_node -> router_node -> llm_node -> should_continue
                     |                                    |
                     +----------- tools ------------------+
                                                      |
                                                     END
        Returns:
            编译后的 LangGraph 可运行对象
        """
        workflow = StateGraph(AgentState)

        # 添加节点
        # 1. RAG 检索节点（需要异步处理）
        if self._rag_enabled and self._rag_node:
            # RAG 节点必须是异步的
            async def rag_node_wrapper(state: AgentState) -> dict[str, Any]:
                return await create_rag_node(self._rag_node)(state)
            workflow.add_node("rag", rag_node_wrapper)
        else:
            # 空节点，直接传递状态
            workflow.add_node("rag", lambda state: state)

        # 2. 模型路由节点（同步）
        if self._router_enabled and self._router:
            router_fn = create_router_node(self._router)
            workflow.add_node("router", router_fn)
        else:
            # 空节点，设置默认模型
            workflow.add_node(
                "router",
                lambda state: {"selected_model": self._model}
            )

        # 3. LLM 调用节点（异步）
        llm_fn = create_llm_node(self._model, self._system_prompt)
        workflow.add_node("llm", llm_fn)

        # 4. 工具执行节点
        if self._tools:
            workflow.add_node("tools", create_tool_node(self._tools))
        else:
            # 无工具时，tools 节点是一个空操作
            workflow.add_node("tools", lambda state: state)

        # 添加边

        # START -> rag
        workflow.add_edge(START, "rag")

        # rag -> router
        workflow.add_edge("rag", "router")

        # router -> llm
        workflow.add_edge("router", "llm")

        # llm -> should_continue (条件边)
        if self._tools:
            workflow.add_conditional_edges(
                "llm",
                should_continue_with_tools,
                {
                    "tools": "tools",
                    "end": END,
                }
            )
            # tools -> llm (循环)
            workflow.add_edge("tools", "llm")
        else:
            # 无工具时，直接结束
            workflow.add_edge("llm", END)

        # 编译图（支持 Store 长期记忆注入）
        compile_kwargs = {"checkpointer": self._checkpointer}
        if self._store and self._store.store:
            compile_kwargs["store"] = self._store.store

        return workflow.compile(**compile_kwargs)

    @property
    def graph(self) -> Runnable:
        """返回底层 LangGraph 可运行对象."""
        return self._graph

    @property
    def router(self) -> Optional[ModelRouter]:
        """返回模型路由器."""
        return self._router

    @property
    def rag_node(self) -> Optional[RAGNode]:
        """返回 RAG 节点."""
        return self._rag_node

    @property
    def store(self) -> Optional[MemoryStore]:
        """返回长期记忆存储."""
        return self._store

    @property
    def checkpointer(self) -> BaseCheckpointSaver:
        """返回状态持久化检查点."""
        return self._checkpointer

    def get_config(self, thread_id: str, **kwargs) -> dict[str, Any]:
        """生成调用配置.

        Args:
            thread_id: 会话线程ID
            **kwargs: 额外配置

        Returns:
            LangGraph 配置字典
        """
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": kwargs.get("recursion_limit", 15),
        }
        if kwargs:
            config.update(kwargs)
        return config

    def invoke(
        self,
        message: str,
        thread_id: str,
        *,
        recursion_limit: int = 15,
    ) -> dict[str, Any]:
        """同步调用 Agent.

        Args:
            message: 用户消息
            thread_id: 会话线程ID，用于状态持久化
            recursion_limit: 最大迭代次数，防止无限循环

        Returns:
            包含 messages 的字典
        """
        config = self.get_config(thread_id, recursion_limit=recursion_limit)
        return self._graph.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
        )

    async def ainvoke(
        self,
        message: str,
        thread_id: str,
        *,
        recursion_limit: int = 15,
    ) -> dict[str, Any]:
        """异步调用 Agent.

        Args:
            message: 用户消息
            thread_id: 会话线程ID，用于状态持久化
            recursion_limit: 最大迭代次数，防止无限循环

        Returns:
            包含 messages 的字典
        """
        config = self.get_config(thread_id, recursion_limit=recursion_limit)
        return await self._graph.ainvoke(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
        )

    def stream(
        self,
        message: str,
        thread_id: str,
        *,
        recursion_limit: int = 15,
    ) -> AsyncIterator[dict[str, Any]]:
        """流式响应.

        Args:
            message: 用户消息
            thread_id: 会话线程ID
            recursion_limit: 最大迭代次数

        Yields:
            每个事件的字典
        """
        config = self.get_config(thread_id, recursion_limit=recursion_limit)
        return self._graph.astream(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
        )

    async def astream(
        self,
        message: str,
        thread_id: str,
        *,
        recursion_limit: int = 15,
    ) -> AsyncIterator[dict[str, Any]]:
        """异步流式响应.

        Args:
            message: 用户消息
            thread_id: 会话线程ID
            recursion_limit: 最大迭代次数

        Yields:
            每个事件的字典
        """
        config = self.get_config(thread_id, recursion_limit=recursion_limit)
        async for event in self._graph.astream(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
        ):
            yield event

    def get_state(self, thread_id: str) -> Optional[dict[str, Any]]:
        """获取当前状态.

        Args:
            thread_id: 会话线程ID

        Returns:
            状态字典
        """
        config = self.get_config(thread_id)
        return self._graph.get_state(config)

    async def get_state_history(
        self,
        thread_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """获取状态历史.

        Args:
            thread_id: 会话线程ID
            limit: 返回数量限制

        Returns:
            状态历史列表
        """
        config = self.get_config(thread_id)
        states = []
        async for state in self._graph.astream_events(None, config, version="v2"):
            # 只收集最终状态
            if state.get("event") == "on_chain_end":
                states.append(state)
            if len(states) >= limit:
                break
        return states