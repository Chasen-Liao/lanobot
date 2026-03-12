"""快速测试 Agent 与 LLM 连接."""

import asyncio
import json
from pathlib import Path

from lanobot.providers import create_llm
from lanobot.agent.graph import AgentGraph
from lanobot.agent.prompt import load_system_prompt


async def test_agent():
    """测试 Agent 调用."""
    # 1. 加载配置
    config_path = Path("config.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    llm_config = config["llm"]

    print(f"Provider: {llm_config['provider']}")
    print(f"Model: {llm_config['model']}")

    # 2. 创建 LLM
    print("\n[1/3] 创建 LLM...")
    llm = create_llm(
        provider=llm_config["provider"],
        model=llm_config["model"],
        api_key=llm_config["api_key"],
        api_base=llm_config.get("base_url"),
        temperature=llm_config.get("temperature", 0.7),
        max_tokens=llm_config.get("max_tokens", 4096),
    )
    print("LLM 创建成功!")

    # 3. 加载系统提示词
    print("\n[2/3] 加载系统提示词...")
    system_prompt = load_system_prompt()
    print(f"提示词长度: {len(system_prompt)} 字符")

    # 4. 创建 Agent（无工具）
    print("\n[3/3] 创建 Agent...")
    agent = AgentGraph(
        model=llm,
        tools=[],  # 暂不传工具
        system_prompt=system_prompt,
    )
    print("Agent 创建成功!")

    # 5. 测试调用
    print("\n测试调用: '你好，请用一句话介绍自己'")
    print("-" * 50)

    result = await agent.ainvoke(
        message="你好，请用一句话介绍自己",
        thread_id="test-001",
    )

    # 输出结果
    messages = result.get("messages", [])
    if messages:
        last_message = messages[-1]
        content = last_message.content
        print(f"\n回复: {content}")
        print("-" * 50)
        print("\n[SUCCESS] Agent 测试成功!")
    else:
        print("\n[FAILED] 未收到回复")


if __name__ == "__main__":
    asyncio.run(test_agent())