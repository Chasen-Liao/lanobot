"""
lanobot init 命令 - 初始化项目
"""
import typer
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()

app = typer.Typer(name="init", help="初始化 Lanobot 项目")


@app.command(name="init")
def main(
    force: bool = typer.Option(False, "--force", "-f", help="强制覆盖已存在的文件"),
):
    """初始化 Lanobot 项目（创建目录和配置文件）"""
    console.print(Panel.fit(
        "[orange1]Lanobot 项目初始化[/orange1]",
        border_style="orange1",
    ))

    # 需要创建的目录
    dirs_to_create = [
        "./data",
        "./logs",
        "./workspace",
        "./skills",
    ]

    # 需要创建的配置文件
    config_content = """{
  "llm": {
    "provider": "siliconflow",
    "model": "Pro/deepseek-ai/DeepSeek-V3.2",
    "api_key": "",
    "base_url": "https://api.siliconflow.cn/v1",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "channels": [],
  "templates_dir": "./lanobot/templates",
  "workspace": "./workspace",
  "mcp_servers": [],
  "skills_dir": "./skills",
  "logging": {
    "level": "INFO"
  }
}
"""

    # 创建目录
    for dir_path in dirs_to_create:
        p = Path(dir_path)
        if p.exists() and not force:
            console.print(f"[warning]⏭  目录已存在: {dir_path}[/warning]")
        else:
            p.mkdir(parents=True, exist_ok=True)
            console.print(f"[success]✓[/success] 创建目录: {dir_path}")

    # 创建配置文件
    config_path = Path("config.json")
    if config_path.exists() and not force:
        console.print(f"[warning]⏭  配置文件已存在: config.json[/warning]")
    else:
        config_path.write_text(config_content, encoding="utf-8")
        console.print(f"[success]✓[/success] 创建配置文件: config.json")

    console.print("\n[success]初始化完成！[/success]")
    console.print("[info]运行 [cyan]lanobot config init[/] 开始配置向导[/info]")