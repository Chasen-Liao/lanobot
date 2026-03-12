"""Agent Graph 测试."""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock
from langchain_core.tools import tool

from lanobot.agent.graph import AgentGraph
from lanobot.agent.state import AgentState


class TestAgentGraph:
    """测试 AgentGraph 类."""

    @pytest.fixture
    def mock_model(self):
        """创建 mock LLM 模型用于测试.

        创建一个模拟 LangChain Runnable 的模型
        """
        mock_model = MagicMock()
        # 设置模型支持 bind_tools 并返回可调用的 mock
        bound_mock = MagicMock()
        mock_model.bind_tools.return_value = bound_mock
        return mock_model

    @pytest.fixture
    def sample_tool(self):
        """创建示例工具."""
        @tool
        def echo(message: str) -> str:
            """Echo back the input message.

            Args:
                message: The message to echo
            """
            return f"Echo: {message}"
        return echo

    def test_agent_creation(self, mock_model, sample_tool):
        """测试 Agent 创建."""
        agent = AgentGraph(
            model=mock_model,
            tools=[sample_tool],
            system_prompt="You are a test agent.",
        )
        assert agent is not None
        assert agent.graph is not None

    def test_agent_without_system_prompt(self, mock_model, sample_tool):
        """测试无系统提示词的 Agent 创建."""
        agent = AgentGraph(
            model=mock_model,
            tools=[sample_tool],
        )
        assert agent is not None

    def test_agent_with_custom_checkpointer(self, mock_model, sample_tool):
        """测试自定义 checkpointer."""
        from langgraph.checkpoint.memory import InMemorySaver

        checkpointer = InMemorySaver()
        agent = AgentGraph(
            model=mock_model,
            tools=[sample_tool],
            checkpointer=checkpointer,
        )
        assert agent is not None

    def test_agent_graph_property(self, mock_model, sample_tool):
        """测试 graph 属性返回正确的对象."""
        agent = AgentGraph(
            model=mock_model,
            tools=[sample_tool],
        )
        # graph 属性应该是可运行的
        assert hasattr(agent.graph, 'invoke')
        assert hasattr(agent.graph, 'ainvoke')


class TestAgentState:
    """测试 AgentState 类型定义."""

    def test_agent_state_definition(self):
        """测试 AgentState 可以正常实例化."""
        state: AgentState = {
            "messages": [],
            "session_id": "test-session",
            "user_id": "test-user",
            "context": {"key": "value"},
        }
        assert state["session_id"] == "test-session"
        assert state["user_id"] == "test-user"
        assert state["context"]["key"] == "value"

    def test_agent_state_optional_fields(self):
        """测试可选字段可以为空."""
        state: AgentState = {
            "messages": [],
        }
        assert state.get("session_id") is None
        assert state.get("user_id") is None
        assert state.get("context") is None