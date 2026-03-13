"""
气泡框组件 - 用户和 Agent 消息显示
"""
from rich.panel import Panel
from rich.text import Text
from rich.box import ROUNDED

# 使用圆角边框（直接使用 Rich 内置的 ROUNDED）
ROUNDED_BOX = ROUNDED


class BubblePanel:
    """消息气泡框组件"""

    # 颜色配置
    USER_BORDER_COLOR = "green"      # 用户消息边框颜色
    AGENT_BORDER_COLOR = "cyan"       # Agent 消息边框颜色

    @staticmethod
    def user(message: str, show_label: bool = True) -> Panel:
        """用户消息气泡

        Args:
            message: 消息内容
            show_label: 是否显示 "你" 标签

        Returns:
            Panel: 用户消息气泡框
        """
        # 添加用户标签
        if show_label:
            content = f"[bold green]你[/bold green]\n\n{message}"
        else:
            content = message

        return Panel(
            content,
            border_style=BubblePanel.USER_BORDER_COLOR,
            box=ROUNDED_BOX,
            padding=(0, 1),
            width=None,  # 自动宽度
            title=None,
        )

    @staticmethod
    def agent(message: str, title: str = "💡", collapsed: bool = False) -> Panel:
        """Agent 消息气泡

        Args:
            message: 消息内容
            title: 气泡标题
            collapsed: 是否折叠状态

        Returns:
            Panel: Agent 消息气泡框
        """
        panel_title = "点击展开" if collapsed else title

        return Panel(
            message,
            border_style=BubblePanel.AGENT_BORDER_COLOR,
            box=ROUNDED_BOX,
            padding=(0, 1),
            width=None,
                        title=panel_title if collapsed else None,
        )

    @staticmethod
    def thinking(message: str = "") -> Panel:
        """思考中气泡（浅灰色）

        Args:
            message: 思考内容

        Returns:
            Panel: 思考中的气泡框
        """
        content = f"[dim]{message}[/dim]" if message else "[dim]思考中...[/dim]"

        return Panel(
            content,
            border_style="white",
            box=ROUNDED_BOX,
            padding=(0, 1),
            width=None,
                        title=None,
        )

    @staticmethod
    def tool_call(tool_name: str, args: str = "") -> Panel:
        """工具调用气泡（浅灰色）

        Args:
            tool_name: 工具名称
            args: 工具参数（可选）

        Returns:
            Panel: 工具调用气泡框
        """
        content = f"[dim]→ 调用工具: {tool_name}[/dim]"
        if args:
            content += f"\n\n[dim]{args}[/dim]"

        return Panel(
            content,
            border_style="white",
            box=ROUNDED_BOX,
            padding=(0, 1),
            width=None,
                        title=None,
        )

    @staticmethod
    def tool_result(result: str) -> Panel:
        """工具结果气泡（浅灰色）

        Args:
            result: 工具执行结果

        Returns:
            Panel: 工具结果气泡框
        """
        return Panel(
            f"[dim]{result}[/dim]",
            border_style="white",
            box=ROUNDED_BOX,
            padding=(0, 1),
            width=None,
                        title=None,
        )