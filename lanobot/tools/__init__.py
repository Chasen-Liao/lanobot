"""Lanobot tools - A collection of agent tools for file operations, shell execution, and web access."""

from lanobot.tools.base import Tool
from lanobot.tools.registry import ToolRegistry
from lanobot.tools.filesystem import (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    ListDirTool,
)
from lanobot.tools.shell import ExecTool
from lanobot.tools.web import (
    WebSearchTool,
    WebFetchTool,
)
from lanobot.tools.message import (
    MessageTool,
    OutboundMessage,
)
from lanobot.tools.spawn import SpawnTool, SubagentManager
from lanobot.tools.cron import CronTool, CronSchedule, SimpleCronService
from lanobot.tools.mcp import (
    MCPToolWrapper,
    MCPConfig,
    connect_mcp_servers,
    create_mcp_tool_registry,
)

__all__ = [
    # Base classes
    "Tool",
    "ToolRegistry",
    # File system tools
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "ListDirTool",
    # Shell tools
    "ExecTool",
    # Web tools
    "WebSearchTool",
    "WebFetchTool",
    # Message tools
    "MessageTool",
    "OutboundMessage",
    # Spawn tools
    "SpawnTool",
    "SubagentManager",
    # Cron tools
    "CronTool",
    "CronSchedule",
    "SimpleCronService",
    # MCP tools
    "MCPToolWrapper",
    "MCPConfig",
    "connect_mcp_servers",
    "create_mcp_tool_registry",
]


def create_tool_registry(
    workspace: str | None = None,
    include_filesystem: bool = True,
    include_shell: bool = True,
    include_web: bool = False,
    include_message: bool = True,
    include_spawn: bool = False,
    include_cron: bool = False,
    **kwargs,
) -> ToolRegistry:
    """Create a pre-configured tool registry.

    Args:
        workspace: Working directory for file operations
        include_filesystem: Include file system tools (read, write, edit, list)
        include_shell: Include shell execution tool
        include_web: Include web search/fetch tools
        include_message: Include message sending tool
        include_spawn: Include subagent spawn tool
        include_cron: Include cron/schedule tool
        **kwargs: Additional configuration options

    Returns:
        Configured ToolRegistry instance
    """
    from pathlib import Path
    from lanobot.tools.shell import ExecTool
    from lanobot.tools.message import MessageTool
    from lanobot.tools.spawn import SpawnTool, SubagentManager
    from lanobot.tools.cron import CronTool, SimpleCronService

    registry = ToolRegistry()
    workspace_path = Path(workspace) if workspace else None

    # File system tools
    if include_filesystem:
        for tool_class in [ReadFileTool, WriteFileTool, EditFileTool, ListDirTool]:
            tool = tool_class(workspace=workspace_path)
            registry.register(tool)

    # Shell tool
    if include_shell:
        exec_tool = ExecTool(
            working_dir=workspace,
            deny_patterns=kwargs.get("deny_patterns"),
            allow_patterns=kwargs.get("allow_patterns"),
            restrict_to_workspace=kwargs.get("restrict_to_workspace", False),
        )
        registry.register(exec_tool)

    # Web tools
    if include_web:
        web_search = WebSearchTool(
            api_key=kwargs.get("brave_api_key"),
            max_results=kwargs.get("max_search_results", 5),
            proxy=kwargs.get("proxy"),
        )
        web_fetch = WebFetchTool(
            max_chars=kwargs.get("max_fetch_chars", 50000),
            proxy=kwargs.get("proxy"),
        )
        registry.register(web_search)
        registry.register(web_fetch)

    # Message tool
    if include_message:
        message_tool = MessageTool(
            default_channel=kwargs.get("default_channel", "cli"),
            default_chat_id=kwargs.get("default_chat_id", "direct"),
        )
        registry.register(message_tool)

    # Spawn tool
    if include_spawn:
        agent_factory = kwargs.get("agent_factory")
        spawn_tool = SpawnTool(manager=SubagentManager(agent_factory=agent_factory))
        registry.register(spawn_tool)

    # Cron tool
    if include_cron:
        cron_service = kwargs.get("cron_service") or SimpleCronService()
        cron_tool = CronTool(cron_service=cron_service)
        registry.register(cron_tool)

    return registry