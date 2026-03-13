"""
交互式 REPL 组件
"""
import asyncio
import uuid
import logging
from typing import Optional, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.layout import Layout

from lanobot.cli.components import (
    BubblePanel,
    ThinkingSpinner,
    CommandHandler,
    CommandResult,
    FoldingState,
    MessageHistory,
)


class InteractiveREPL:
    """交互式 REPL"""

    # 欢迎信息
    WELCOME = """
[bold orange1]🟠 Lanobot v0.1.0[/bold orange1]
超轻量级个人AI助手

[dim]输入 /help 查看可用命令[/dim]
    """

    def __init__(
        self,
        agent,
        session_manager=None,
        config=None,
    ):
        """初始化 REPL

        Args:
            agent: AgentGraph 实例
            session_manager: 会话管理器（可选）
            config: 配置对象（可选）
        """
        self.agent = agent
        self.session_manager = session_manager
        self.config = config

        # Rich Console
        self.console = Console()

        # 组件
        self.command_handler = CommandHandler(session_manager=session_manager, console=self.console)
        self.folding_state = FoldingState()
        self.message_history = MessageHistory()

        # 设置回调
        self.command_handler.set_fold_callback(self.toggle_fold)
        self.command_handler.set_session_change_callback(self._on_session_change)

        # 状态
        self._running = False
        self._current_thread_id: Optional[str] = None
        self._is_thinking = False
        self._current_response = ""
        self.current_session_key = "cli:default"

        # 配置命令上下文
        if config:
            # 从会话键中提取会话名称
            session_name = "default"
            if self.current_session_key.startswith("cli:"):
                session_name = self.current_session_key[4:]
            self.command_handler.context.session_name = session_name
            self.command_handler.context.model = getattr(config.llm, "model", "")
        # 设置命令处理器的当前会话键
        self.command_handler.current_session_key = self.current_session_key

    def _get_current_session(self):
        """获取当前会话，如果不存在则创建"""
        if not self.session_manager:
            return None
        session = self.session_manager.get_or_create(self.current_session_key)
        return session

    def _save_session(self, session):
        """保存会话"""
        if not self.session_manager:
            return
        self.session_manager.save(session)

    def _on_session_change(self, new_session_key: str):
        """会话变更回调"""
        self.current_session_key = new_session_key
        # 更新命令上下文的会话名称
        if new_session_key.startswith("cli:"):
            self.command_handler.context.session_name = new_session_key[4:]
        else:
            self.command_handler.context.session_name = new_session_key

    def print_welcome(self):
        """打印欢迎信息"""
        self.console.print(Panel.fit(
            self.WELCOME.strip(),
            border_style="orange1",
            padding=(0, 2),
        ))

    async def run(self):
        """运行 REPL 主循环"""
        self._running = True
        self.print_welcome()

        while self._running:
            try:
                # 获取用户输入
                user_input = self.console.input("[bold green]你[/bold green] > ")

                if not user_input.strip():
                    continue

                # 添加到历史
                self.message_history.add_user(user_input)
                self.command_handler.context.history.append(user_input)

                # 处理命令
                result = self.command_handler.handle(user_input)

                if result == CommandResult.EXIT:
                    self.console.print("[dim]再见！[/dim]")
                    break
                elif result == CommandResult.SUCCESS:
                    continue
                elif result == CommandResult.SKIP:
                    continue
                elif result == CommandResult.UNKNOWN:
                    # 作为普通消息处理
                    pass
                else:
                    continue

                # 处理普通消息 - 调用 Agent
                await self.process_message(user_input)

            except KeyboardInterrupt:
                self.console.print("\n[dim]再见！[/dim]")
                break
            except EOFError:
                break
            except Exception as e:
                self.console.print(f"[red bold]错误: {e}[/red bold]")

    async def process_message(self, user_input: str):
        """处理用户消息并获取 Agent 响应

        Args:
            user_input: 用户输入的消息
        """
        # 获取当前会话键（从命令处理器同步）
        self.current_session_key = self.command_handler.current_session_key

        # 获取或创建当前会话
        session = self._get_current_session()
        if not session:
            self.console.print("[red]无法获取会话，会话管理器未初始化[/red]")
            return

        # 添加用户消息到会话
        session.add_message("user", user_input)
        self._save_session(session)

        # 显示用户消息气泡
        self.console.print(BubblePanel.user(user_input))
        self.console.print()  # 空行

        # 开始思考
        self._is_thinking = True

        # 用于存储思考内容
        thinking_content = []
        tool_calls_content = []
        final_response = ""

        # 显示思考中提示
        self.console.print("[dim]🐕 思考中... (按 Ctrl+O 收起)[/dim]")

        # 临时抑制 LangGraph 日志
        logger = logging.getLogger("langgraph")
        old_level = logger.level
        logger.setLevel(logging.ERROR)

        try:
            # 构建消息列表：使用会话中的历史消息（LangChain 格式）
            # 注意：Session.to_langchain_format() 返回完整的消息历史
            # 但我们只需要传递历史消息，新的用户消息已经包含在历史中
            langchain_messages = session.to_langchain_format()

            # 创建新的 thread_id
            self._current_thread_id = f"cli-{uuid.uuid4().hex[:8]}"

            # 使用 astream_events 实现流式输出
            async for event in self.agent.graph.astream_events(
                {"messages": langchain_messages},
                config=self.agent.get_config(self._current_thread_id),
                version="v2",
            ):
                kind = event.get("event")
                data = event.get("data", {})

                # LLM 流式输出（思考内容或最终回复）
                if kind == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    if chunk and hasattr(chunk, "content"):
                        content = chunk.content
                        if content:
                            thinking_content.append(content)
                            # 检查是否应该显示思考内容（未折叠时）
                            if self.folding_state.is_expanded(FoldableSection.THINKING):
                                self.console.print(f"[dim]{content}[/dim]", end="")

                # 工具调用开始
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})
                    # 显示工具调用（浅灰色）
                    if self.folding_state.is_expanded(FoldableSection.TOOL_CALLS):
                        self.console.print(f"\n[dim]→ 调用工具: {tool_name}[/dim]")
                    tool_calls_content.append(f"→ 调用工具: {tool_name}")

                # 工具调用结束
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    output = data.get("output")
                    # 显示工具完成（浅灰色）
                    if self.folding_state.is_expanded(FoldableSection.TOOL_CALLS):
                        self.console.print(f"[dim]✓ 工具完成: {tool_name}[/dim]")
                        if output:
                            self.console.print(f"[dim]  结果: {str(output)[:100]}[/dim]")
                    tool_calls_content.append(f"✓ 工具完成: {tool_name}")
                    if output:
                        tool_calls_content.append(f"  结果: {str(output)[:100]}")

            # 确保有换行
            self.console.print()

            # 构建最终响应
            final_response = "".join(thinking_content)

            # 添加助手消息到会话
            if final_response:
                session.add_message("assistant", final_response)
                self._save_session(session)

            # 添加到消息历史
            self.message_history.add_agent(final_response)

            # 显示最终回复气泡
            if final_response:
                self._display_agent_response(final_response)

        except UnicodeEncodeError as e:
            self.console.print(f"\n[red]编码错误: {e}[/red]")
        except Exception as e:
            error_msg = str(e)
            if "Deserializing" in error_msg:
                self.console.print("[red]会话状态冲突，请重试[/red]")
            else:
                self.console.print(f"[red]错误: {error_msg}[/red]")
        finally:
            logger.setLevel(old_level)
            self._is_thinking = False

    def _display_agent_response(self, response: str):
        """显示 Agent 回复气泡

        Args:
            response: Agent 回复内容
        """
        # 检查是否需要折叠（响应太长时）
        lines = response.split("\n")
        is_long = len(lines) > 10

        if is_long:
            # 长响应：显示折叠提示
            hint = self.folding_state.get_hint(FoldableSection.FINAL_RESPONSE)
            header = f"[bold cyan]💡[/bold cyan] [dim]{hint}[/dim] (用 /fold 切换)"
            self.console.print(header)

        # 显示气泡
        self.console.print(BubblePanel.agent(response))

    def toggle_fold(self):
        """切换思考过程的折叠状态"""
        self.folding_state.toggle(FoldableSection.THINKING)
        status = "展开" if self.folding_state.is_expanded(FoldableSection.THINKING) else "收起"
        self.console.print(f"[green]思考过程已{status}[/green]")
        self.console.print()

    def stop(self):
        """停止 REPL"""
        self._running = False


def create_repl(agent, session_manager=None, config=None) -> InteractiveREPL:
    """创建 REPL 实例的工厂函数

    Args:
        agent: AgentGraph 实例
        session_manager: 会话管理器
        config: 配置对象

    Returns:
        InteractiveREPL: REPL 实例
    """
    return InteractiveREPL(
        agent=agent,
        session_manager=session_manager,
        config=config,
    )


# 导入需要的枚举
from lanobot.cli.components.folding import FoldableSection