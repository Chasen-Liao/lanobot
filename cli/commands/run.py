"""
lanobot run 命令 - 启动 Lanobot 服务
"""
import asyncio
import os
import sys

# 必须在任何其他导入之前设置 UTF-8 模式
os.environ["PYTHONUTF8"] = "1"

import typer
from rich.console import Console

console = Console()

app = typer.Typer(name="run", help="启动 Lanobot 服务")

# 设置 UTF-8 编码
if sys.platform == "win32":
    # Windows 上需要设置正确的事件循环策略以支持信号处理
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # 强制 UTF-8 输出
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


@app.command(name="agent")
def agent_cmd(
    log_level: str = typer.Option("INFO", "--log-level", "-l", help="日志级别"),
):
    """
    启动 Agent 核心（不含渠道）

    仅运行 Agent 核心功能（LLM、会话管理、Cron、Heartbeat），
    不启动任何通讯渠道。适合本地调试或作为后台进程。
    """
    console.print("[orange1]启动 Agent 核心...[/orange1]")

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
    console.print("[orange1]启动渠道网关...[/orange1]")

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
    console.print("[orange1]启动完整服务...[/orange1]")

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