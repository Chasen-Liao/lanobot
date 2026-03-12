"""
lanobot channel 命令 - 渠道管理
"""
import typer
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()

app = typer.Typer(name="channel", help="渠道管理")

# 支持的渠道列表
AVAILABLE_CHANNELS = [
    {"id": "feishu", "name": "飞书", "enabled": False},
    {"id": "telegram", "name": "Telegram", "enabled": False},
    {"id": "slack", "name": "Slack", "enabled": False},
    {"id": "discord", "name": "Discord", "enabled": False},
    {"id": "dingtalk", "name": "钉钉", "enabled": False},
    {"id": "wecom", "name": "企业微信", "enabled": False},
    {"id": "whatsapp", "name": "WhatsApp", "enabled": False},
    {"id": "qq", "name": "QQ", "enabled": False},
]


def _load_config() -> dict:
    """加载配置文件"""
    config_path = Path("config.json")
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def _save_config(config_data: dict):
    """保存配置文件"""
    config_path = Path("config.json")
    config_path.write_text(
        json.dumps(config_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


@app.command("list")
def channel_list():
    """列出已配置渠道"""
    config_data = _load_config()
    enabled_channels = config_data.get("channels", [])

    table = Table(title="已配置的渠道", show_header=True, header_style="orange1")
    table.add_column("渠道", style="cyan")
    table.add_column("名称", style="white")
    table.add_column("状态", style="white")

    for ch in AVAILABLE_CHANNELS:
        status = "[success]✓ 已启用[/success]" if ch["id"] in enabled_channels else "[warning]未启用[/warning]"
        table.add_row(ch["id"], ch["name"], status)

    console.print(table)


@app.command("add")
def channel_add(
    name: str = typer.Argument(..., help="渠道名称 (feishu/telegram/slack/discord/dingtalk/wecom/whatsapp/qq)"),
):
    """添加渠道"""
    valid_channels = [ch["id"] for ch in AVAILABLE_CHANNELS]
    if name not in valid_channels:
        console.print(f"[error]无效的渠道名称: {name}[/error]")
        console.print(f"[info]支持的渠道: {', '.join(valid_channels)}[/info]")
        raise typer.Exit(1)

    config_data = _load_config()
    channels = config_data.get("channels", [])

    if name in channels:
        console.print(f"[warning]渠道 {name} 已存在[/warning]")
        return

    channels.append(name)
    config_data["channels"] = channels
    _save_config(config_data)

    console.print(f"[success]✓[/success] 添加渠道: {name}")


@app.command("remove")
def channel_remove(
    name: str = typer.Argument(..., help="渠道名称"),
):
    """移除渠道"""
    config_data = _load_config()
    channels = config_data.get("channels", [])

    if name not in channels:
        console.print(f"[warning]渠道 {name} 不存在[/warning]")
        return

    channels.remove(name)
    config_data["channels"] = channels
    _save_config(config_data)

    console.print(f"[success]✓[/success] 移除渠道: {name}")