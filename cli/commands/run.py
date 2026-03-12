"""
lanobot run 命令 - 启动 Lanobot 服务
"""
import asyncio
import os
import typer
from rich.console import Console

console = Console()

app = typer.Typer(name="run", help="启动 Lanobot 服务")


@app.command(name="agent")
def agent_cmd(
    log_level: str = typer.Option("INFO", "--log-level", "-l", help="日志级别"),
):
    """
    启动 Agent 核心（不含渠道）

    仅运行 Agent 核心功能（LLM、会话管理、Cron、Heartbeat），
    不启动任何通讯渠道。适合本地调试或作为后台进程。
    """
    console.print(f"[orange1]启动 Agent 核心...[/orange1]")
    console.print(f"[info]日志级别: {log_level}[/info]")

    # 设置日志级别
    if log_level:
        os.environ["LANOBOT_LOG_LEVEL"] = log_level

    from main import run_agent

    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        console.print("[info]服务已停止[/info]")
    except Exception as e:
        console.print(f"[error]服务启动失败: {e}[/error]")
        raise typer.Exit(code=1)


@app.command(name="gateway")
def gateway_cmd(
    log_level: str = typer.Option("INFO", "--log-level", "-l", help="日志级别"),
):
    """
    启动渠道网关

    仅运行通讯渠道（飞书、Slack、Telegram 等），
    需要配合 agent 模式使用。适合多进程部署。
    """
    console.print(f"[orange1]启动渠道网关...[/orange1]")
    console.print(f"[info]日志级别: {log_level}[/info]")

    if log_level:
        os.environ["LANOBOT_LOG_LEVEL"] = log_level

    from main import run_gateway

    try:
        asyncio.run(run_gateway())
    except KeyboardInterrupt:
        console.print("[info]服务已停止[/info]")
    except Exception as e:
        console.print(f"[error]服务启动失败: {e}[/error]")
        raise typer.Exit(code=1)


@app.command(name="start", hidden=True)
def start_cmd(
    log_level: str = typer.Option("INFO", "--log-level", "-l", help="日志级别"),
):
    """
    启动完整服务（默认）

    启动包含 Agent 核心和渠道的完整服务。
    """
    console.print(f"[orange1]启动完整服务...[/orange1]")
    console.print(f"[info]日志级别: {log_level}[/info]")

    if log_level:
        os.environ["LANOBOT_LOG_LEVEL"] = log_level

    from main import run_all

    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        console.print("[info]服务已停止[/info]")
    except Exception as e:
        console.print(f"[error]服务启动失败: {e}[/error]")
        raise typer.Exit(code=1)