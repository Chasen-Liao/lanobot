"""完整测试：RAG + 多模型路由."""

import asyncio
import json
from pathlib import Path
from langchain_core.documents import Document

from lanobot.providers import create_llm
from lanobot.memory.rag import create_rag_node, load_knowledge_from_files, InMemoryRAG
from lanobot.agent.router import ModelRouter


async def test_rag():
    """测试 RAG 功能."""
    print("=" * 60)
    print("测试 RAG 检索增强")
    print("=" * 60)

    # 创建知识库目录（如果没有）
    knowledge_dir = Path("./knowledge")
    knowledge_dir.mkdir(exist_ok=True)

    # 创建示例知识文件
    sample_file = knowledge_dir / "lanobot_guide.txt"
    if not sample_file.exists():
        sample_file.write_text("""
Lanobot 配置指南
=================

1. API Key 配置
   在 config.json 中填写 siliconflow 的 API Key

2. 支持的模型
   - DeepSeek-V3.2 (默认)
   - Qwen-2.5
   - GLM-4

3. 渠道配置
   支持飞书、Telegram、QQ 等

4. 工具系统
   - 文件读写
   - 命令执行
   - Web 搜索
""", encoding="utf-8")

    # 创建 RAG 节点
    print("\n[1] 创建 RAG 节点...")
    rag_node = create_rag_node(knowledge_dir=knowledge_dir, k=2)
    print(f"    知识库文档数: {len(rag_node.retriever._documents) if rag_node.retriever else 0}")

    # 测试检索
    print("\n[2] 测试检索...")
    query = "如何配置 lanobot 的 API Key?"
    context = await rag_node.retrieve(query)
    print(f"    查询: {query}")
    print(f"    检索到上下文:\n{context[:200]}...")

    return rag_node, context


async def test_router():
    """测试多模型路由."""
    print("\n" + "=" * 60)
    print("测试多模型路由")
    print("=" * 60)

    # 加载配置
    config_path = Path("config.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    llm_config = config["llm"]

    # 创建不同级别的模型
    print("\n[1] 创建模型...")
    # 默认模型
    default_model = create_llm(
        provider=llm_config["provider"],
        model=llm_config["model"],
        api_key=llm_config["api_key"],
    )

    # 快速模型（可以用更小的模型）
    fast_model = create_llm(
        provider=llm_config["provider"],
        model="Qwen/Qwen2.5-7B-Instruct",  # 更小的模型
        api_key=llm_config["api_key"],
    )

    print(f"    默认模型: {llm_config['model']}")
    print(f"    快速模型: Qwen/Qwen2.5-7B-Instruct")

    # 创建路由器
    print("\n[2] 创建模型路由器...")
    router = ModelRouter(
        default_model=default_model,
        fast_model=fast_model,
    )

    # 测试路由
    test_queries = [
        ("你好", "简单问候"),
        ("今天天气怎么样?", "简单查询"),
        ("请帮我写一个排序算法", "代码请求"),
        ("分析一下量子计算的发展趋势", "复杂分析"),
    ]

    print("\n[3] 测试路由决策:")
    for query, desc in test_queries:
        model = router.select_model(query)
        info = router.get_model_info(query)
        print(f"    [{desc}] {query[:20]}...")
        print(f"         -> 选择: {info['selected_type']} ({info['model_name']})")

    return router


async def main():
    """主函数."""
    # 测试 RAG
    await test_rag()

    # 测试路由
    await test_router()

    print("\n" + "=" * 60)
    print("[完成] RAG 和路由测试成功!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())