"""
lanobot doctor 命令 - 系统检查
"""
import typer
import sys
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

console = Console()

app = typer.Typer(name="doctor", help="系统检查")


def _check_python() -> bool:
    """检查 Python 版本"""
    version = sys.version_info
    return version.major >= 3 and version.minor >= 11


def _check_config() -> bool:
    """检查配置文件"""
    config_path = Path("config.json")
    if not config_path.exists():
        return False
    try:
        json.loads(config_path.read_text(encoding="utf-8"))
        return True
    except Exception:
        return False


def _check_dirs() -> bool:
    """检查必要目录"""
    required_dirs = ["./data", "./logs", "./workspace"]
    return all(Path(d).exists() for d in required_dirs)


def _check_dependencies() -> bool:
    """检查依赖包"""
    required_packages = ["pydantic", "langchain", "httpx", "loguru"]
    for pkg in required_packages:
        try:
            __import__(pkg)
        except ImportError:
            return False
    return True


def _check_channels() -> dict:
    """检查渠道配置"""
    config_path = Path("config.json")
    if not config_path.exists():
        return {"enabled": [], "missing": []}

    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        channels = config_data.get("channels", [])
        return {"enabled": channels, "missing": []}
    except Exception:
        return {"enabled": [], "missing": []}


@app.command()
def check():
    """检查系统状态"""
    console.print(Panel.fit(
        "[orange1]Lanobot 系统检查[/orange1]",
        border_style="orange1",
    ))

    checks = [
        ("Python 版本 (>=3.11)", _check_python),
        ("配置文件", _check_config),
        ("必要目录", _check_dirs),
        ("依赖包", _check_dependencies),
    ]

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for name, check_fn in checks:
            task = progress.add_task(name, total=None)
            result = check_fn()
            results.append((name, result))
            progress.update(task, completed=True)

    # 显示检查结果表格
    table = Table(title="检查结果", show_header=True, header_style="orange1")
    table.add_column("检查项", style="cyan")
    table.add_column("状态", style="white")

    all_passed = True
    for name, result in results:
        status = "[success]✓ 通过[/success]" if result else "[error]✗ 失败[/error]"
        table.add_row(name, status)
        if not result:
            all_passed = False

    console.print(table)

    # 渠道配置检查
    channel_info = _check_channels()
    if channel_info["enabled"]:
        console.print(f"\n[info]已启用渠道: {', '.join(channel_info['enabled'])}[/info]")
    else:
        console.print("\n[warning]尚未配置任何渠道[/warning]")

    # 总结
    console.print()
    if all_passed:
        console.print(Panel.fit(
            "[success]✓ 系统检查通过！[/success]",
            border_style="green",
        ))
    else:
        console.print(Panel.fit(
            "[error]✗ 存在失败项，请修复后重试[/error]",
            border_style="red",
        ))