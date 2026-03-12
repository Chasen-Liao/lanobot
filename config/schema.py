"""Pydantic 配置模型定义"""
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings


class Base(BaseModel):
    """基础模型，支持 camelCase 和 snake_case 键名"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class LLMConfig(Base):
    """LLM 配置"""
    provider: str = "siliconflow"
    model: str = "Pro/deepseek-ai/DeepSeek-V3.2"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)


class DatabaseConfig(Base):
    """数据库配置"""
    url: str = "sqlite:///./data/lanobot.db"
    echo: bool = False


class MessageBusConfig(Base):
    """消息总线配置"""
    max_queue_size: int = Field(default=1000, gt=0)
    timeout: float = Field(default=30.0, gt=0)


class LoggingConfig(Base):
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None


class ChannelsConfig(Base):
    """聊天通道配置"""
    # 飞书/Lark
    feishu_enabled: bool = False
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_encrypt_key: str = ""
    feishu_verification_token: str = ""
    feishu_allow_from: list[str] = Field(default_factory=list)
    feishu_react_emoji: str = "THUMBSUP"

    # QQ
    qq_enabled: bool = False
    qq_app_id: str = ""
    qq_secret: str = ""
    qq_allow_from: list[str] = Field(default_factory=list)

    # Telegram
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_allow_from: list[str] = Field(default_factory=list)

    # Slack
    slack_enabled: bool = False
    slack_bot_token: str = ""
    slack_app_token: str = ""  # Socket Mode 需要
    slack_signing_secret: str = ""
    slack_allow_from: list[str] = Field(default_factory=list)

    # Discord
    discord_enabled: bool = False
    discord_bot_token: str = ""
    discord_allow_from: list[str] = Field(default_factory=list)

    # 钉钉
    dingtalk_enabled: bool = False
    dingtalk_app_key: str = ""
    dingtalk_app_secret: str = ""
    dingtalk_allow_from: list[str] = Field(default_factory=list)

    # 企业微信
    wecom_enabled: bool = False
    wecom_corp_id: str = ""
    wecom_corp_secret: str = ""
    wecom_agent_id: str = ""
    wecom_allow_from: list[str] = Field(default_factory=list)

    # WhatsApp (通过第三方 bridge 如 botigram/whatsapp-bot)
    whatsapp_enabled: bool = False
    whatsapp_webhook_url: str = ""  # WhatsApp webhook URL
    whatsapp_verify_token: str = ""
    whatsapp_allow_from: list[str] = Field(default_factory=list)


class AppConfig(BaseSettings):
    """应用配置"""
    version: str = "0.1.0"
    debug: bool = False
    llm: LLMConfig = Field(default_factory=LLMConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    message_bus: MessageBusConfig = Field(default_factory=MessageBusConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)

    model_config = ConfigDict(
        env_prefix="LANOBOT_",
        env_nested_delimiter="__",
    )

    @property
    def data_dir(self) -> Path:
        """获取数据目录路径"""
        return Path("./data")

    @property
    def config_dir(self) -> Path:
        """获取配置目录路径"""
        return Path("./config")