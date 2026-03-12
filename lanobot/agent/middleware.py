"""Agent 中间件 - 人工确认、人机协作."""

from typing import Optional
from langchain.agents.middleware import HumanInTheLoopMiddleware


# 需要人工确认的敏感操作列表
SENSITIVE_TOOLS = {
    "send_message": True,      # 发送消息
    "send_email": True,        # 发送邮件
    "write_file": True,        # 写文件
    "exec_command": True,      # 执行命令
    "delete_file": True,       # 删除文件
    "delete_database": True,   # 删除数据库
    "spawn_subagent": True,    # 创建子代理
}

# 安全操作，自动批准
SAFE_TOOLS = {
    "search": False,           # 搜索
    "web_fetch": False,        # 获取网页
    "read_file": False,        # 读取文件
    "list_directory": False,   # 列出目录
    "get_weather": False,      # 获取天气
    "calculator": False,       # 计算器
}


def create_human_middleware(
    interrupt_on: Optional[dict] = None,
    allow_approve: bool = True,
    allow_edit: bool = True,
    allow_reject: bool = True,
) -> HumanInTheLoopMiddleware:
    """创建人工确认中间件.

    Args:
        interrupt_on: 自定义需要中断的工具映射
        allow_approve: 是否允许批准
        allow_edit: 是否允许修改参数
        allow_reject: 是否允许拒绝

    Returns:
        HumanInTheLoopMiddleware 实例

    Examples:
        >>> middleware = create_human_middleware()
        >>> middleware = create_human_middleware({
        ...     "send_message": True,
        ...     "write_file": True
        ... })
    """
    # 合并配置
    tools_config = dict(SENSITIVE_TOOLS)  # 默认敏感操作
    tools_config.update(SAFE_TOOLS)       # 添加安全操作

    if interrupt_on:
        tools_config.update(interrupt_on)

    return HumanInTheLoopMiddleware(
        interrupt_on=tools_config,
        allow_accept=allow_approve,
        allow_edit=allow_edit,
        allow_respond=allow_reject,
    )


def build_approve_decision(
    action_id: str,
    suggestion: Optional[str] = None,
) -> dict:
    """构建批准决策（可附带建议）.

    Args:
        action_id: 中断动作的 ID
        suggestion: 额外建议（可选）

    Returns:
        批准决策字典
    """
    decision = {"type": "approve"}
    if suggestion:
        decision["message"] = suggestion
    return {action_id: {"decisions": [decision]}}


def build_edit_decision(
    action_id: str,
    edited_args: dict,
    suggestion: Optional[str] = None,
) -> dict:
    """构建修改决策（修改参数 + 附带建议）.

    Args:
        action_id: 中断动作的 ID
        edited_args: 修改后的参数
        suggestion: 额外建议（可选）

    Returns:
        修改决策字典
    """
    decision = {
        "type": "edit",
        "edited_action": {
            "args": edited_args,
        }
    }
    if suggestion:
        decision["message"] = suggestion
    return {action_id: {"decisions": [decision]}}


def build_reject_decision(
    action_id: str,
    reason: str,
) -> dict:
    """构建拒绝决策.

    Args:
        action_id: 中断动作的 ID
        reason: 拒绝原因

    Returns:
        拒绝决策字典
    """
    return {
        action_id: {
            "decisions": [
                {"type": "reject", "message": reason}
            ]
        }
    }