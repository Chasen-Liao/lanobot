#!/usr/bin/env python3
"""测试会话命令功能"""
import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from session.manager import SessionManager
from lanobot.cli.components.command import CommandHandler
from rich.console import Console

async def test_commands():
    """测试会话命令"""
    console = Console()

    # 创建临时工作空间
    workspace = Path("./test_workspace")
    workspace.mkdir(exist_ok=True)

    try:
        # 创建会话管理器
        session_manager = SessionManager(workspace=workspace)

        # 创建命令处理器
        cmd_handler = CommandHandler(session_manager=session_manager, console=console)

        # 创建一些测试会话
        session1 = session_manager.get_or_create("cli:test1")
        session1.add_message("user", "Hello")
        session1.add_message("assistant", "Hi there")
        session_manager.save(session1)

        session2 = session_manager.get_or_create("cli:test2")
        session2.add_message("user", "Another session")
        session_manager.save(session2)

        print("测试 /sessions 命令:")
        result = cmd_handler.handle("/sessions")
        print(f"结果: {result}")

        print("\n测试 /switch 命令（通过索引）:")
        result = cmd_handler.handle("/switch 0")
        print(f"结果: {result}")
        print(f"当前会话键: {cmd_handler.current_session_key}")

        print("\n测试 /new 命令:")
        result = cmd_handler.handle("/new test3")
        print(f"结果: {result}")
        print(f"当前会话键: {cmd_handler.current_session_key}")

        print("\n测试 /session 命令:")
        result = cmd_handler.handle("/session")
        print(f"结果: {result}")

        print("\n测试 /delete 命令（需要交互确认，跳过）")

    finally:
        # 清理
        import shutil
        if workspace.exists():
            shutil.rmtree(workspace)
        print("\n测试完成")

if __name__ == "__main__":
    asyncio.run(test_commands())