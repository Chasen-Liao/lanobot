"""Lanobot - 超轻量级个人AI助手"""
from config import load_config


def main() -> None:
    """应用入口点"""
    config = load_config()
    print(f"Lanobot v{config.version} 启动中...")


if __name__ == "__main__":
    main()