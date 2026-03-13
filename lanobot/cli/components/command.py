"""
命令处理器组件
"""
import re
from enum import Enum
from typing import Optional, Callable, Any, List, Dict
from dataclasses import dataclass, field


class CommandResult(Enum):
    """命令执行结果"""
    SUCCESS = "success"
    EXIT = "exit"           # 退出程序
    ERROR = "error"         # 命令执行错误
    UNKNOWN = "unknown"     # 未知命令
    SKIP = "skip"           # 跳过（不发送消息）


@dataclass
class Command:
    """命令定义"""
    names: List[str]              # 命令名称列表（主名称 + 别名）
    description: str              # 命令描述
    usage: str                    # 使用示例
    handler: Optional[Callable] = None  # 命令处理函数


@dataclass
class CommandContext:
    """命令执行上下文"""
    session_name: str = "default"     # 当前会话名称
    model: str = ""                    # 当前模型
    show_thinking: bool = True         # 是否显示思考过程
    history: List[str] = field(default_factory=list)  # 消息历史


class CommandHandler:
    """命令处理器"""

    # 内置命令定义
    COMMANDS: Dict[str, Command] = {
        "help": Command(
            names=["/help", "/h", "help"],
            description="显示帮助信息",
            usage="/help [command]",
        ),
        "exit": Command(
            names=["/exit", "/quit", "/q", "exit", "quit"],
            description="退出程序",
            usage="/exit",
        ),
        "clear": Command(
            names=["/clear", "/cls", "clear", "cls"],
            description="清空屏幕",
            usage="/clear",
        ),
        "resume": Command(
            names=["/resume", "/r", "resume"],
            description="恢复中断的对话（暂不支持）",
            usage="/resume",
        ),
        "rename": Command(
            names=["/rename", "/name", "rename", "name"],
            description="重命名当前会话",
            usage="/rename <新名称>",
        ),
        "session": Command(
            names=["/session", "/sess", "session"],
            description="显示当前会话信息",
            usage="/session",
        ),
        "sessions": Command(
            names=["/sessions", "/list", "sessions", "list"],
            description="列出所有可用会话",
            usage="/sessions",
        ),
        "switch": Command(
            names=["/switch", "/sw", "switch"],
            description="切换到指定会话",
            usage="/switch <会话key或索引>",
        ),
        "new": Command(
            names=["/new", "/n", "new"],
            description="创建新会话",
            usage="/new [会话名称]",
        ),
        "delete": Command(
            names=["/delete", "/del", "delete", "del"],
            description="删除指定会话",
            usage="/delete <会话key或索引>",
        ),
        "model": Command(
            names=["/model", "/m", "model"],
            description="显示/切换当前模型",
            usage="/model [模型名]",
        ),
        "think": Command(
            names=["/think", "/t", "think"],
            description="切换思考过程显示",
            usage="/think",
        ),
        "fold": Command(
            names=["/fold", "/f", "fold"],
            description="切换折叠状态",
            usage="/fold",
        ),
    }

    def __init__(self, session_manager=None, console=None):
        """初始化命令处理器

        Args:
            session_manager: 会话管理器实例（可选）
            console: Rich Console 实例（可选）
        """
        self._context = CommandContext()
        self._custom_commands: Dict[str, Command] = {}
        # 构建名称到命令的映射
        self._name_map: Dict[str, Command] = {}
        for cmd in self.COMMANDS.values():
            for name in cmd.names:
                self._name_map[name] = cmd
        # 回调函数
        self._fold_callback = None
        self._session_change_callback = None
        # 会话管理器
        self._session_manager = session_manager
        # 当前会话键（cli:session_name）
        self._current_session_key = "cli:default"
        # Rich Console
        if console is None:
            from rich.console import Console
            console = Console()
        self.console = console

    def set_fold_callback(self, callback):
        """设置折叠回调函数

        Args:
            callback: 回调函数，无返回值
        """
        self._fold_callback = callback

    def set_session_change_callback(self, callback):
        """设置会话变更回调函数

        Args:
            callback: 回调函数，参数为新的会话键
        """
        self._session_change_callback = callback

    @property
    def session_manager(self):
        """获取会话管理器"""
        return self._session_manager

    @session_manager.setter
    def session_manager(self, value):
        """设置会话管理器"""
        self._session_manager = value

    @property
    def current_session_key(self):
        """获取当前会话键"""
        return self._current_session_key

    @current_session_key.setter
    def current_session_key(self, value):
        """设置当前会话键"""
        self._current_session_key = value

    def _build_session_key(self, session_name: str) -> str:
        """构建会话键

        Args:
            session_name: 会话名称

        Returns:
            会话键 (cli:session_name)
        """
        return f"cli:{session_name}"

    @property
    def context(self) -> CommandContext:
        """获取命令上下文"""
        return self._context

    @context.setter
    def context(self, value: CommandContext):
        """设置命令上下文"""
        self._context = value

    def register_command(self, name: str, command: Command):
        """注册自定义命令

        Args:
            name: 命令名称
            command: 命令定义
        """
        self._custom_commands[name] = command
        for cmd_name in command.names:
            self._name_map[cmd_name] = command

    def handle(self, user_input: str) -> CommandResult:
        """处理用户输入

        Args:
            user_input: 用户输入的文本

        Returns:
            CommandResult: 命令执行结果
        """
        # 去除首尾空白
        user_input = user_input.strip()

        if not user_input:
            return CommandResult.SKIP

        # 检查是否为命令
        if not user_input.startswith("/"):
            return CommandResult.UNKNOWN  # 不是命令，作为普通消息处理

        # 解析命令
        parts = user_input.split(maxsplit=1)
        cmd_name = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        # 查找命令
        command = self._name_map.get(cmd_name.lower())
        if not command:
            return CommandResult.UNKNOWN

        # 执行命令
        return self._execute_command(command, args)

    def _execute_command(self, command: Command, args: str) -> CommandResult:
        """执行命令

        Args:
            command: 命令定义
            args: 命令参数

        Returns:
            CommandResult: 命令执行结果
        """
        cmd_name = command.names[0].lstrip("/")

        try:
            # 根据命令名称分发处理
            if cmd_name in ("help", "h"):
                return self._handle_help(args)
            elif cmd_name in ("exit", "quit", "q"):
                return CommandResult.EXIT
            elif cmd_name in ("clear", "cls"):
                return self._handle_clear()
            elif cmd_name in ("resume", "r"):
                return self._handle_resume()
            elif cmd_name in ("rename", "name"):
                return self._handle_rename(args)
            elif cmd_name in ("session", "sess"):
                return self._handle_session()
            elif cmd_name in ("sessions", "list"):
                return self._handle_sessions()
            elif cmd_name in ("switch", "sw"):
                return self._handle_switch(args)
            elif cmd_name in ("new", "n"):
                return self._handle_new(args)
            elif cmd_name in ("delete", "del"):
                return self._handle_delete(args)
            elif cmd_name in ("model", "m"):
                return self._handle_model(args)
            elif cmd_name in ("think", "t"):
                return self._handle_think()
            elif cmd_name in ("fold", "f"):
                return self._handle_fold()
            else:
                return CommandResult.UNKNOWN

        except Exception as e:
            print(f"[red]命令执行错误: {e}[/red]")
            return CommandResult.ERROR

    def _handle_help(self, args: str = "") -> CommandResult:
        """处理 help 命令"""
        if args:
            # 显示特定命令的帮助
            cmd = self._name_map.get(args)
            if cmd:
                self.console.print(f"\n[bold]{cmd.names[0]}[/bold]: {cmd.description}")
                self.console.print(f"用法: {cmd.usage}")
            else:
                self.console.print(f"[red]未知命令: {args}[/red]")
        else:
            # 显示所有命令帮助
            self.console.print("\n[bold cyan]可用命令:[/bold cyan]\n")
            for cmd in self.COMMANDS.values():
                names = ", ".join(cmd.names)
                self.console.print(f"  [magenta]{names}[/magenta]  -  {cmd.description}")
                self.console.print(f"    用法: [dim]{cmd.usage}[/dim]\n")

        return CommandResult.SUCCESS

    def _handle_clear(self) -> CommandResult:
        """处理 clear 命令"""
        # 跨平台的清屏方法
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
        return CommandResult.SUCCESS

    def _handle_resume(self) -> CommandResult:
        """处理 resume 命令"""
        self.console.print("[yellow]暂不支持恢复中断的对话功能[/yellow]")
        return CommandResult.SUCCESS

    def _handle_rename(self, args: str = "") -> CommandResult:
        """处理 rename 命令"""
        if not args:
            self.console.print("[red]请提供新会话名称[/red]")
            self.console.print("用法: /rename <新名称>")
            return CommandResult.ERROR

        self._context.session_name = args
        self.console.print(f"[green]会话已重命名为: {args}[/green]")
        return CommandResult.SUCCESS

    def _handle_session(self) -> CommandResult:
        """处理 session 命令"""
        self.console.print(f"\n[bold]会话信息:[/bold]")
        self.console.print(f"  会话名称: {self._context.session_name}")
        self.console.print(f"  当前模型: {self._context.model or '默认'}")
        self.console.print(f"  消息历史: {len(self._context.history)} 条")
        self.console.print(f"  显示思考: {'是' if self._context.show_thinking else '否'}")
        return CommandResult.SUCCESS

    def _handle_model(self, args: str = "") -> CommandResult:
        """处理 model 命令"""
        if args:
            self._context.model = args
            self.console.print(f"[green]模型已切换为: {args}[/green]")
            return CommandResult.SUCCESS
        else:
            self.console.print(f"当前模型: {self._context.model or '默认'}")
            return CommandResult.SUCCESS

    def _handle_think(self) -> CommandResult:
        """处理 think 命令"""
        self._context.show_thinking = not self._context.show_thinking
        status = "开启" if self._context.show_thinking else "关闭"
        self.console.print(f"[green]思考显示已{status}[/green]")
        return CommandResult.SUCCESS

    def _handle_fold(self) -> CommandResult:
        """处理 fold 命令"""
        if self._fold_callback:
            self._fold_callback()
        else:
            # 如果没有回调，执行默认的切换逻辑
            self._context.show_thinking = not self._context.show_thinking
            status = "收起" if self._context.show_thinking else "展开"
            self.console.print(f"[green]思考过程已{status}[/green]")
        return CommandResult.SUCCESS

    def _handle_sessions(self) -> CommandResult:
        """处理 sessions 命令 - 列出所有会话"""
        if not self._session_manager:
            self.console.print("[red]会话管理器未初始化[/red]")
            return CommandResult.ERROR

        sessions = self._session_manager.list_sessions()
        if not sessions:
            self.console.print("[yellow]没有找到任何会话[/yellow]")
            return CommandResult.SUCCESS

        self.console.print(f"\n[bold cyan]可用会话 ({len(sessions)})[/bold cyan]")
        self.console.print("[dim]索引 | 会话键 | 标题 | 消息数 | 更新时间[/dim]")
        for i, meta in enumerate(sessions):
            # 简短的键显示
            key_display = meta.key
            if len(key_display) > 30:
                key_display = key_display[:27] + "..."
            title = meta.title or "(无标题)"
            if len(title) > 20:
                title = title[:17] + "..."
            updated = meta.updated_at.strftime("%Y-%m-%d %H:%M") if hasattr(meta.updated_at, 'strftime') else str(meta.updated_at)
            self.console.print(f" {i:3} | {key_display:30} | {title:20} | {meta.message_count:6} | {updated}")

        return CommandResult.SUCCESS

    def _handle_switch(self, args: str = "") -> CommandResult:
        """处理 switch 命令 - 切换到指定会话"""
        if not self._session_manager:
            self.console.print("[red]会话管理器未初始化[/red]")
            return CommandResult.ERROR

        if not args:
            self.console.print("[red]请指定要切换的会话键或索引[/red]")
            self.console.print("用法: /switch <会话key或索引>")
            return CommandResult.ERROR

        # 获取所有会话
        sessions = self._session_manager.list_sessions()
        if not sessions:
            self.console.print("[yellow]没有找到任何会话[/yellow]")
            return CommandResult.ERROR

        target_key = None
        # 检查是否是数字索引
        if args.isdigit():
            idx = int(args)
            if 0 <= idx < len(sessions):
                target_key = sessions[idx].key
            else:
                self.console.print(f"[red]索引超出范围 (0-{len(sessions)-1})[/red]")
                return CommandResult.ERROR
        else:
            # 作为会话键处理
            target_key = args
            # 验证会话是否存在
            session = self._session_manager.get(target_key)
            if not session:
                self.console.print(f"[red]会话不存在: {target_key}[/red]")
                return CommandResult.ERROR

        # 切换到新会话
        old_key = self._current_session_key
        self._current_session_key = target_key
        self.console.print(f"[green]已切换到会话: {target_key}[/green]")

        # 更新上下文会话名称（从键中提取）
        if target_key.startswith("cli:"):
            self._context.session_name = target_key[4:]
        else:
            # 如果是其他渠道的会话，只显示键
            self._context.session_name = target_key

        # 调用会话变更回调
        if self._session_change_callback:
            self._session_change_callback(target_key)

        return CommandResult.SUCCESS

    def _handle_new(self, args: str = "") -> CommandResult:
        """处理 new 命令 - 创建新会话"""
        if not self._session_manager:
            self.console.print("[red]会话管理器未初始化[/red]")
            return CommandResult.ERROR

        session_name = args.strip() if args else "default"
        session_key = self._build_session_key(session_name)

        # 检查是否已存在
        existing = self._session_manager.get(session_key)
        if existing:
            self.console.print(f"[yellow]会话已存在: {session_key}[/yellow]")
            # 直接切换到该会话
            self._current_session_key = session_key
            self._context.session_name = session_name
            self.console.print(f"[green]已切换到现有会话[/green]")
            # 调用会话变更回调
            if self._session_change_callback:
                self._session_change_callback(session_key)
            return CommandResult.SUCCESS

        # 创建新会话
        session = self._session_manager.get_or_create(session_key)
        self._current_session_key = session_key
        self._context.session_name = session_name
        self.console.print(f"[green]已创建新会话: {session_key}[/green]")
        # 调用会话变更回调
        if self._session_change_callback:
            self._session_change_callback(session_key)
        return CommandResult.SUCCESS

    def _handle_delete(self, args: str = "") -> CommandResult:
        """处理 delete 命令 - 删除指定会话"""
        if not self._session_manager:
            self.console.print("[red]会话管理器未初始化[/red]")
            return CommandResult.ERROR

        if not args:
            self.console.print("[red]请指定要删除的会话键或索引[/red]")
            self.console.print("用法: /delete <会话key或索引>")
            return CommandResult.ERROR

        # 获取所有会话
        sessions = self._session_manager.list_sessions()
        if not sessions:
            self.console.print("[yellow]没有找到任何会话[/yellow]")
            return CommandResult.ERROR

        target_key = None
        # 检查是否是数字索引
        if args.isdigit():
            idx = int(args)
            if 0 <= idx < len(sessions):
                target_key = sessions[idx].key
            else:
                self.console.print(f"[red]索引超出范围 (0-{len(sessions)-1})[/red]")
                return CommandResult.ERROR
        else:
            # 作为会话键处理
            target_key = args

        # 防止删除当前会话
        if target_key == self._current_session_key:
            self.console.print("[red]不能删除当前活跃会话[/red]")
            self.console.print("请先切换到其他会话再删除此会话")
            return CommandResult.ERROR

        # 确认删除
        confirm = input(f"确认删除会话 '{target_key}'? (y/N): ")
        if confirm.lower() != 'y':
            self.console.print("[yellow]取消删除[/yellow]")
            return CommandResult.SUCCESS

        # 执行删除
        success = self._session_manager.delete(target_key)
        if success:
            self.console.print(f"[green]已删除会话: {target_key}[/green]")
        else:
            self.console.print(f"[red]删除会话失败: {target_key}[/red]")

        return CommandResult.SUCCESS

    def get_commands(self) -> List[str]:
        """获取所有可用命令名称"""
        return list(self._name_map.keys())

    def get_command(self, name: str) -> Optional[Command]:
        """获取指定命令"""
        return self._name_map.get(name)