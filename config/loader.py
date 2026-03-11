"""配置加载器"""
import json
from pathlib import Path
from typing import Optional

from config.schema import AppConfig


# 全局变量存储当前配置路径（支持多实例）
_current_config_path: Optional[Path] = None


def set_config_path(path: Path) -> None:
    """设置当前配置路径（用于派生数据目录）"""
    global _current_config_path
    _current_config_path = path


def get_config_path() -> Path:
    """获取配置文件路径"""
    if _current_config_path:
        return _current_config_path
    return Path.home() / ".lanobot" / "config.json"


def load_config(config_path: Optional[Path] = None) -> AppConfig:
    """加载配置文件

    Args:
        config_path: 配置文件路径，未提供时使用默认路径

    Returns:
        AppConfig: 加载的配置对象
    """
    path = config_path or get_config_path()

    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return AppConfig.model_validate(data)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"警告: 加载配置失败 {path}: {e}")
            print("使用默认配置")

    return AppConfig()


def save_config(config: AppConfig, config_path: Optional[Path] = None) -> None:
    """保存配置到文件

    Args:
        config: 要保存的配置
        config_path: 保存路径，未提供时使用默认路径
    """
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(by_alias=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)