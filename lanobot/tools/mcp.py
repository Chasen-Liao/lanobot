"""MCP client: connects to MCP servers and wraps their tools as native lanobot tools."""

import asyncio
from contextlib import AsyncExitStack
from typing import Any, Optional

from lanobot.tools.base import Tool
from lanobot.tools.registry import ToolRegistry


class MCPToolWrapper(Tool):
    """Wraps a single MCP server tool as a lanobot Tool."""

    def __init__(
        self,
        session: Any,
        server_name: str,
        tool_def: Any,
        tool_timeout: int = 30,
    ):
        self._session = session
        self._original_name = tool_def.name
        self._name = f"mcp_{server_name}_{tool_def.name}"
        self._description = tool_def.description or tool_def.name
        self._parameters = tool_def.inputSchema or {"type": "object", "properties": {}}
        self._tool_timeout = tool_timeout

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def execute(self, **kwargs: Any) -> str:
        try:
            result = await asyncio.wait_for(
                self._session.call_tool(self._original_name, arguments=kwargs),
                timeout=self._tool_timeout,
            )
        except asyncio.TimeoutError:
            return f"(MCP tool call timed out after {self._tool_timeout}s)"
        except asyncio.CancelledError:
            return "(MCP tool call was cancelled)"
        except Exception as exc:
            return f"(MCP tool call failed: {type(exc).__name__}: {exc})"

        # Parse result content
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts) or "(no output)"


class MCPConfig:
    """MCP server configuration."""

    def __init__(
        self,
        name: str,
        transport_type: str = "stdio",
        command: Optional[str] = None,
        args: Optional[list[str]] = None,
        env: Optional[dict[str, str]] = None,
        url: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        tool_timeout: int = 30,
    ):
        self.name = name
        self.type = transport_type
        self.command = command
        self.args = args or []
        self.env = env
        self.url = url
        self.headers = headers
        self.tool_timeout = tool_timeout


async def connect_mcp_servers(
    mcp_servers: dict[str, MCPConfig],
    registry: ToolRegistry,
    stack: Optional[AsyncExitStack] = None,
) -> list[str]:
    """Connect to configured MCP servers and register their tools.

    Args:
        mcp_servers: Dict of MCP server configs keyed by name
        registry: ToolRegistry to register MCP tools
        stack: Optional AsyncExitStack for lifecycle management

    Returns:
        List of connected server names
    """
    connected = []
    use_stack = stack is not None

    if not use_stack:
        stack = AsyncExitStack()
        await stack.__aenter__(None)

    for name, cfg in mcp_servers.items():
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.sse import sse_client
            from mcp.client.stdio import stdio_client
            from mcp.client.streamable_http import streamable_http_client
        except ImportError:
            return ["Error: mcp package not installed. Install with: pip install mcp"]

        try:
            transport_type = cfg.type
            if not transport_type:
                if cfg.command:
                    transport_type = "stdio"
                elif cfg.url:
                    transport_type = (
                        "sse" if cfg.url.rstrip("/").endswith("/sse") else "streamableHttp"
                    )
                else:
                    continue

            if transport_type == "stdio":
                params = StdioServerParameters(
                    command=cfg.command,
                    args=cfg.args,
                    env=cfg.env or None,
                )
                read, write = await stack.enter_async_context(stdio_client(params))
            elif transport_type == "sse":
                import httpx

                def httpx_client_factory(
                    headers: dict[str, str] | None = None,
                    timeout: httpx.Timeout | None = None,
                    auth: httpx.Auth | None = None,
                ) -> httpx.AsyncClient:
                    merged_headers = {**(cfg.headers or {}), **(headers or {})}
                    return httpx.AsyncClient(
                        headers=merged_headers or None,
                        follow_redirects=True,
                        timeout=timeout,
                        auth=auth,
                    )

                read, write = await stack.enter_async_context(
                    sse_client(cfg.url, httpx_client_factory=httpx_client_factory)
                )
            elif transport_type == "streamableHttp":
                import httpx

                http_client = await stack.enter_async_context(
                    httpx.AsyncClient(
                        headers=cfg.headers or None,
                        follow_redirects=True,
                        timeout=None,
                    )
                )
                read, write, _ = await stack.enter_async_context(
                    streamable_http_client(cfg.url, http_client=http_client)
                )
            else:
                continue

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools = await session.list_tools()
            for tool_def in tools.tools:
                wrapper = MCPToolWrapper(
                    session, name, tool_def, tool_timeout=cfg.tool_timeout
                )
                registry.register(wrapper)

            connected.append(name)
        except ImportError as e:
            return [f"Error: missing dependency for MCP '{name}': {e}"]
        except Exception as e:
            return [f"Error: failed to connect to MCP '{name}': {e}"]

    if not use_stack:
        await stack.__aexit__(None, None, None)

    return connected


def create_mcp_tool_registry(
    mcp_servers: Optional[dict[str, MCPConfig]] = None,
) -> tuple[ToolRegistry, list[str]]:
    """Create a tool registry with MCP tools pre-loaded.

    Args:
        mcp_servers: Dict of MCP server configs

    Returns:
        Tuple of (ToolRegistry, connected server names)
    """
    from lanobot.tools import ToolRegistry

    registry = ToolRegistry()
    connected = []

    if mcp_servers:
        try:
            import asyncio
            connected = asyncio.run(connect_mcp_servers(mcp_servers, registry))
        except Exception as e:
            connected = [f"Error: {e}"]

    return registry, connected