"""路径工具函数"""
from pathlib import Path

from config.loader import get_config_path


def get_data_dir() -> Path:
    """获取运行时数据目录"""
    return get_config_path().parent


def get_runtime_subdir(name: str) -> Path:
    """获取命名运行时子目录"""
    path = get_data_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_logs_dir() -> Path:
    """获取日志目录"""
    return get_runtime_subdir("logs")


def get_workspace_path(workspace: str | None = None) -> Path:
    """解析并确保工作区路径存在"""
    path = Path(workspace).expanduser() if workspace else Path.home() / ".lanobot" / "workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_dir() -> Path:
    """获取配置目录"""
    return get_config_path().parent