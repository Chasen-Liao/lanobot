"""
Lanobot CLI - 命令行界面
"""
import typer
import sys
import io
from typing import Optional
from rich.console import Console
from rich.theme import Theme

# 设置 UTF-8 输出
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from .commands import init, run, config, channel, tool, session, doctor

# 创建 Console 实例
console = Console()

# 创建 Typer 应用
app = typer.Typer(
    name="lanobot",
    help="Lanobot - 超轻量级个人AI助手",
    add_completion=False,
)

# 注册子命令
app.add_typer(init.app, name="init")
app.add_typer(run.app, name="run")
app.add_typer(config.app, name="config")
app.add_typer(channel.app, name="channel")
app.add_typer(tool.app, name="tool")
app.add_typer(session.app, name="session")
app.add_typer(doctor.app, name="doctor")


@app.command()
def version():
    """显示版本信息"""
    import toml
    from pathlib import Path
    # 从 pyproject.toml 读取版本
    pyproject = Path("pyproject.toml")
    if pyproject.exists():
        data = toml.loads(pyproject.read_text(encoding="utf-8"))
        ver = data.get("project", {}).get("version", "0.1.0")
    else:
        ver = "0.1.0"
    console.print(f"[orange1]Lanobot[/orange1] [info]v{ver}[/info]")


def main():
    """CLI 入口点"""
    app()


if __name__ == "__main__":
    main()