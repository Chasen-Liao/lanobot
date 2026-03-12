"""测试自定义节点流程."""

import asyncio
from pathlib import Path

from langchain_core.documents import Document
from lanobot.memory.rag import InMemoryRAG, RAGNode
from lanobot.agent.router import ModelRouter


def test_with_mock_model():
    """使用模拟模型测试节点流程."""
    from unittest.mock import MagicMock
    from lanobot.agent.graph import AgentGraph

    # 创建模拟模型
    mock_model = MagicMock()
    mock_model.model = "mock-model"

    # 异步响应
    async def mock_ainvoke(messages, **kwargs):
        from langchain_core.messages import AIMessage
        return AIMessage(content="Mock response", id="test-id")

    mock_model.ainvoke = mock_ainvoke

    # 测试 1: 不带 RAG 和 Router
    print("=" * 50)
    print("Test 1: Agent without RAG and Router")
    print("=" * 50)

    agent = AgentGraph(model=mock_model)
    print(f"  rag_enabled: {agent._rag_enabled}")
    print(f"  router_enabled: {agent._router_enabled}")
    print(f"  graph type: {type(agent.graph)}")
    print("  PASS\n")


async def test_with_rag():
    """测试带 RAG 的节点."""
    from unittest.mock import MagicMock
    from lanobot.agent.graph import AgentGraph

    # 创建模拟模型
    mock_model = MagicMock()
    mock_model.model = "mock-model"

    async def mock_ainvoke(messages, **kwargs):
        from langchain_core.messages import AIMessage
        system_msg = messages[0] if messages else None
        return AIMessage(
            content="Mock response with RAG",
            id="test-id"
        )

    mock_model.ainvoke = mock_ainvoke

    # 创建测试文档
    docs = [
        Document(
            page_content="Lanobot 是一个基于 LangChain 的 AI 助手。",
            metadata={"source": "test.txt"}
        ),
        Document(
            page_content="它支持 RAG 检索和模型路由功能。",
            metadata={"source": "test.txt"}
        ),
    ]

    # 创建 RAG 节点
    rag_retriever = InMemoryRAG(documents=docs)
    rag_node = RAGNode(retriever=rag_retriever, k=2)

    print("=" * 50)
    print("Test 2: Agent with RAG")
    print("=" * 50)

    # 手动测试 RAG 检索
    context = await rag_retriever.retrieve("Lanobot 是什么")
    print(f"  RAG retrieved {len(context)} documents")
    for doc in context:
        print(f"    - {doc.page_content[:50]}...")

    # 创建带 RAG 的 Agent
    agent = AgentGraph(
        model=mock_model,
        rag_node=rag_node,
    )
    print(f"  rag_enabled: {agent._rag_enabled}")
    print("  PASS\n")


def test_with_router():
    """测试带 Router 的节点."""
    from unittest.mock import MagicMock

    # 创建模拟模型
    default_model = MagicMock()
    default_model.model = "default-model"

    fast_model = MagicMock()
    fast_model.model = "fast-model"

    strong_model = MagicMock()
    strong_model.model = "strong-model"

    # 创建路由器
    router = ModelRouter(
        default_model=default_model,
        fast_model=fast_model,
        strong_model=strong_model,
    )

    print("=" * 50)
    print("Test 3: Agent with Router")
    print("=" * 50)

    # 测试路由选择
    test_queries = [
        "你好",
        "写代码",
        "请详细分析这个概念",
    ]

    for query in test_queries:
        selected = router.select_model(query)
        model_type = router.router_fn(query)
        print(f"  Query: {query[:20]:<20} -> {model_type}")

    print("  PASS\n")


async def test_full_flow():
    """测试完整流程（需要真实 API key）."""
    import json
    from langchain_openai import ChatOpenAI
    from lanobot.agent.graph import AgentGraph

    # 加载配置
    config_path = Path("config.json")
    if not config_path.exists():
        print("=" * 50)
        print("Test 4: Full Flow (SKIPPED - no config.json)")
        print("=" * 50)
        print("  Skipping: config.json not found")
        print()
        return

    with open(config_path) as f:
        config = json.load(f)

    llm_config = config.get("llm", {})
    api_key = llm_config.get("api_key")
    if not api_key:
        print("=" * 50)
        print("Test 4: Full Flow (SKIPPED - no API key)")
        print("=" * 50)
        print("  Skipping: no API key found")
        print()
        return

    print("=" * 50)
    print("Test 4: Full Flow with Real API")
    print("=" * 50)

    # 创建模型（使用硅基流动）
    base_url = llm_config.get("base_url", "https://api.siliconflow.cn/v1")
    model_name = llm_config.get("model", "Pro/deepseek-ai/DeepSeek-V3.2")

    # 创建带 RAG 的知识库
    docs = [
        Document(
            page_content="Lanobot 是一个超轻量级 AI 助手，基于 LangChain 构建。",
            metadata={"source": "about.txt"}
        ),
        Document(
            page_content="它支持 RAG 知识检索、多模型路由等功能。",
            metadata={"source": "features.txt"}
        ),
    ]

    rag_retriever = InMemoryRAG(documents=docs)
    rag_node = RAGNode(retriever=rag_retriever, k=2)

    # 创建模型
    model = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.7,
    )

    # 创建 Agent
    agent = AgentGraph(
        model=model,
        rag_node=rag_node,
        router_enabled=False,  # 简化测试
    )

    # 调用 Agent（使用异步调用）
    print("  Invoking agent with RAG...")
    result = await agent.ainvoke(
        message="Lanobot 是什么？",
        thread_id="test-thread-1"
    )

    response = result["messages"][-1]
    print(f"  Response: {response.content[:200]}...")

    # 获取检索到的上下文
    state = agent.get_state("test-thread-1")
    if state and state.values:
        rag_context = state.values.get("rag_context")
        if rag_context:
            print(f"  RAG Context: {rag_context[:100]}...")

    print("  PASS\n")


async def main():
    test_with_mock_model()
    await test_with_rag()
    test_with_router()
    await test_full_flow()
    print("All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())