"""
lanobot session 命令 - 会话管理
"""
import typer
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()

app = typer.Typer(name="session", help="会话管理")


def _get_session_dir() -> Path:
    """获取会话目录"""
    return Path("./data/sessions")


@app.command("list")
def session_list(
    limit: int = typer.Option(10, "--limit", "-n", help="显示数量"),
):
    """列出活跃会话"""
    session_dir = _get_session_dir()
    if not session_dir.exists():
        console.print("[warning]暂无会话记录[/warning]")
        return

    sessions = []
    for session_file in session_dir.glob("*.json"):
        try:
            data = json.loads(session_file.read_text(encoding="utf-8"))
            sessions.append({
                "key": session_file.stem,
                "messages": len(data.get("messages", [])),
                "updated": data.get("updated_at", ""),
            })
        except Exception:
            pass

    if not sessions:
        console.print("[warning]暂无会话记录[/warning]")
        return

    # 按更新时间排序
    sessions.sort(key=lambda x: x["updated"], reverse=True)
    sessions = sessions[:limit]

    table = Table(title="活跃会话", show_header=True, header_style="orange1")
    table.add_column("会话 Key", style="cyan")
    table.add_column("消息数", style="white", justify="right")
    table.add_column("最后更新", style="white")

    for s in sessions:
        table.add_row(s["key"], str(s["messages"]), s["updated"])

    console.print(table)


@app.command("history")
def session_history(
    key: str = typer.Argument(..., help="会话 Key"),
    limit: int = typer.Option(50, "--limit", "-n", help="显示消息数"),
):
    """查看会话历史"""
    session_dir = _get_session_dir()
    session_file = session_dir / f"{key}.json"

    if not session_file.exists():
        console.print(f"[error]会话不存在: {key}[/error]")
        raise typer.Exit(1)

    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
        messages = data.get("messages", [])[-limit:]

        console.print(f"[orange1]会话: {key}[/orange1]")
        console.print(f"[info]消息数: {len(messages)}[/info]\n")

        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:100]
            console.print(f"[{ 'cyan' if role == 'user' else 'green'}]{role}[/{'cyan' if role == 'user' else 'green'}]: {content}...")

    except Exception as e:
        console.print(f"[error]读取会话失败: {e}[/error]")
        raise typer.Exit(1)


@app.command("clear")
def session_clear(
    key: str = typer.Argument(None, help="会话 Key（不指定则清除所有）"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="确认清除"),
):
    """清除会话"""
    session_dir = _get_session_dir()

    if not confirm:
        console.print("[warning]请使用 --yes 确认清除操作[/warning]")
        return

    if key:
        session_file = session_dir / f"{key}.json"
        if session_file.exists():
            session_file.unlink()
            console.print(f"[success]✓[/success] 清除会话: {key}")
        else:
            console.print(f"[warning]会话不存在: {key}[/warning]")
    else:
        # 清除所有会话
        count = 0
        for session_file in session_dir.glob("*.json"):
            session_file.unlink()
            count += 1
        console.print(f"[success]✓[/success] 清除 {count} 个会话")