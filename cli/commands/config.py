"""
lanobot config 命令 - 配置管理
"""
import typer
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

from ..wizard import ConfigWizard

console = Console()

app = typer.Typer(name="config", help="配置管理")


@app.command("init")
def config_init():
    """启动交互式配置向导"""
    wizard = ConfigWizard()
    wizard.run()


@app.command("show")
def config_show():
    """显示当前配置"""
    config_path = Path("config.json")
    if not config_path.exists():
        console.print("[error]配置文件不存在，请先运行 [cyan]lanobot init[/][/error]")
        raise typer.Exit(1)

    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))

        # 创建配置表格
        table = Table(title="Lanobot 当前配置", show_header=True, header_style="orange1")
        table.add_column("配置项", style="cyan")
        table.add_column("值", style="white")

        # LLM 配置
        llm = config_data.get("llm", {})
        table.add_row("[bold]LLM 配置[/bold]", "")
        table.add_row("  提供商", llm.get("provider", ""))
        table.add_row("  模型", llm.get("model", ""))
        table.add_row("  API Key", "***" if llm.get("api_key") else "")
        table.add_row("  Base URL", llm.get("base_url", ""))

        # 渠道配置
        channels = config_data.get("channels", [])
        table.add_row("[bold]渠道配置[/bold]", ", ".join(channels) if channels else "无")

        # 其他配置
        table.add_row("[bold]其他配置[/bold]", "")
        table.add_row("  Templates Dir", config_data.get("templates_dir", ""))
        table.add_row("  Workspace", config_data.get("workspace", ""))
        table.add_row("  Skills Dir", config_data.get("skills_dir", ""))

        console.print(table)
    except Exception as e:
        console.print(f"[error]读取配置失败: {e}[/error]")
        raise typer.Exit(1)


@app.command("set")
def config_set(
    key: str = typer.Argument(..., help="配置键 (支持点号分隔，如 llm.provider)"),
    value: str = typer.Argument(..., help="配置值"),
):
    """设置配置项"""
    config_path = Path("config.json")
    if not config_path.exists():
        console.print("[error]配置文件不存在，请先运行 [cyan]lanobot init[/][/error]")
        raise typer.Exit(1)

    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))

        # 支持嵌套键
        keys = key.split(".")
        current = config_data
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value

        # 写入配置
        config_path.write_text(
            json.dumps(config_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        console.print(f"[success]✓[/success] 设置 {key} = {value}")
    except Exception as e:
        console.print(f"[error]设置配置失败: {e}[/error]")
        raise typer.Exit(1)