"""系统提示词加载器."""

from pathlib import Path
from typing import Optional


def load_system_prompt(templates_dir: Optional[Path] = None) -> str:
    """加载系统提示词（按优先级拼接多个模板文件）.

    按以下优先级加载模板文件：
    1. SOUL.md - 助手身份定义
    2. AGENTS.md - Agent 行为规范
    3. TOOLS.md - 工具约束说明
    4. USER.md - 用户信息

    Args:
        templates_dir: 模板目录路径，默认为 lanobot/templates

    Returns:
        拼接后的系统提示词字符串
    """
    if templates_dir is None:
        # 默认使用 lanobot/templates 目录
        templates_dir = Path(__file__).parent.parent / "templates"

    template_files = [
        "SOUL.md",  # 助手身份
        "AGENTS.md",  # 行为规范
        "TOOLS.md",  # 工具约束
        "USER.md",  # 用户信息
    ]

    prompts = []
    for filename in template_files:
        file_path = templates_dir / filename
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            prompts.append(f"<!-- {filename} -->\n{content}")

    return "\n\n".join(prompts)